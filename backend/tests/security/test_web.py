"""CSRF, XSS, CORS, security headers and what the frontend file server exposes."""
import re
from pathlib import Path

from unittest import mock

from django.conf import settings
from rest_framework.renderers import BrowsableAPIRenderer, JSONRenderer

from students.models import Student
from students.views import StudentDetailView

from .base import PASSWORD, SecurityTestCase

REPO_ROOT = Path(settings.BASE_DIR).parent
FRONTEND = REPO_ROOT / 'frontend' if (REPO_ROOT / 'frontend').is_dir() else REPO_ROOT
XSS = '<script>alert(1)</script>'

# --- tiny template-literal scanner for the XSS static check --------------------------------------
# Template literals nest (`${rows.map(r => `<td>${escapeHTML(r.x)}</td>`)}`). An expression that holds its
# own template is judged by its inner ${...}; a plain expression must be an escaping helper or a constant.
# `value` = stat-card counts from /students/summary/ (integers); label/note/icon/color are constants in renderStats().
SAFE_EXPR = re.compile(r'^(escapeHTML|Number|personCell|statusCell)\(|^(label|note|icon|color|value)$')


def _skip_string(text, i):
    quote, i = text[i], i + 1
    while text[i] != quote:
        i += 2 if text[i] == '\\' else 1
    return i + 1


def _read_template(text, i):  # i: just after an opening backtick
    exprs = []
    while text[i] != '`':
        if text[i] == '\\':
            i += 2
        elif text.startswith('${', i):
            expr, i = _read_expr(text, i + 2)
            exprs.append(expr)
        else:
            i += 1
    return exprs, i + 1


def _read_expr(text, i):  # i: just after '${'
    depth, start = 1, i
    while True:
        char = text[i]
        if char in '\'"':
            i = _skip_string(text, i)
            continue
        if char == '`':
            i = _read_template(text, i + 1)[1]
            continue
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                return text[start:i].strip(), i + 1
        i += 1


def _template_exprs(text):
    i, found = 0, []
    while i < len(text):
        if text[i] in '\'"':
            i = _skip_string(text, i)
        elif text[i] == '`':
            exprs, i = _read_template(text, i + 1)
            found.extend(exprs)
        else:
            i += 1
    return found


def unsafe_interpolations(text):
    bad = []
    for expr in _template_exprs(text):
        if '`' in expr:
            bad += unsafe_interpolations(expr)
        elif not SAFE_EXPR.search(expr):
            bad.append(expr)
    return bad


class CSRFTests(SecurityTestCase):
    def test_login_without_csrf_token_is_rejected(self):
        client = self.csrf_client()
        response = client.post('/api/auth/login/', {'username': 'staff_full', 'password': PASSWORD}, format='json')
        self.assertEqual(response.status_code, 403)

    def test_state_changing_requests_without_csrf_token_are_rejected(self):
        client = self.csrf_client()
        client.force_login(self.u_staff)
        requests = [
            ('post', '/api/students/', {'student_id': 'C1', 'first_name': 'C', 'last_name': 'S', 'email': 'c1@example.test', 'course': 'C'}),
            ('patch', f'/api/students/{self.student_a.pk}/', {'status': 'Inactive'}),
            ('delete', f'/api/students/{self.student_a2.pk}/', None),
            ('post', '/api/attendance/', {'student': self.student_a.pk, 'date': '2026-03-01', 'status': 'Present'}),
            ('post', '/api/auth/logout/', None),
        ]
        for method, path, body in requests:
            with self.subTest(method=method, path=path):
                self.assertEqual(getattr(client, method)(path, body, format='json').status_code, 403)
        self.assertEqual(Student.objects.get(pk=self.student_a.pk).status, 'Active')

    def test_valid_csrf_token_is_accepted(self):
        client = self.csrf_client()
        token = client.get('/api/auth/csrf/').data['csrfToken']
        response = client.post('/api/auth/login/', {'username': 'staff_full', 'password': PASSWORD}, format='json', HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

    def test_get_never_changes_state(self):
        self.login_as(self.u_staff)
        self.assertEqual(self.client.get('/api/auth/logout/').status_code, 405)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)


class XSSTests(SecurityTestCase):
    def setUp(self):
        super().setUp()
        Student.objects.filter(pk=self.student_a.pk).update(first_name=XSS, address=XSS)

    def test_api_returns_payload_as_json_data_not_html(self):
        self.login_as(self.u_staff)
        response = self.client.get(f'/api/students/{self.student_a.pk}/', HTTP_ACCEPT='application/json')
        self.assertEqual(response['Content-Type'], 'application/json')
        self.assertEqual(response.data['first_name'], XSS)

    def test_browsable_api_is_off_by_default(self):
        """Audit L9: the HTML API is only offered when DEBUG is on, so it never renders the payload."""
        self.login_as(self.u_staff)
        response = self.client.get(f'/api/students/{self.student_a.pk}/', HTTP_ACCEPT='text/html')
        self.assertEqual(response.status_code, 406)
        self.assertNotIn(XSS, response.content.decode())

    def test_browsable_api_html_escapes_payload_when_enabled(self):
        """When a developer turns the HTML API on, stored payloads are still escaped."""
        # DRF copies DEFAULT_RENDERER_CLASSES onto each view class at import time, so patch the view itself.
        renderers = [JSONRenderer, BrowsableAPIRenderer]
        with mock.patch.object(StudentDetailView, 'renderer_classes', renderers):
            self.login_as(self.u_staff)
            html = self.client.get(f'/api/students/{self.student_a.pk}/', HTTP_ACCEPT='text/html').content.decode()
        self.assertNotIn(XSS, html)
        self.assertIn('&lt;script&gt;', html)

    def test_frontend_escapes_every_api_value_written_with_innerHTML(self):
        """Static check of script.js: every ${...} that ends up in innerHTML must be escaped or numeric."""
        source = (FRONTEND / 'script.js').read_text(encoding='utf-8')
        lines = [line for line in source.splitlines() if 'innerHTML' in line]
        self.assertGreater(len(lines), 5)
        self.assertEqual([expr for line in lines for expr in unsafe_interpolations(line)], [])

    def test_xss_scanner_flags_unescaped_values(self):
        """Guard: the scanner must catch an unescaped value, including one nested inside another template."""
        probe = "el.innerHTML = `${ok ? rows.map(r => `<td>${r.name}</td><td>${escapeHTML(r.id)}</td>`).join('') : ''}<b>${user.bio}</b>`;"
        self.assertEqual(unsafe_interpolations(probe), ['r.name', 'user.bio'])

    def test_no_tokens_in_browser_storage(self):
        for name in ('script.js', 'login.js'):
            with self.subTest(file=name):
                source = (FRONTEND / name).read_text(encoding='utf-8')
                self.assertNotRegex(source, r'localStorage|sessionStorage|document\.cookie')

    def test_L6_frontend_pages_set_a_content_security_policy(self):
        for page in ('index.html', 'login.html'):
            with self.subTest(page=page):
                path = FRONTEND / page
                self.assertRegex(path.read_text(encoding='utf-8'), r'(?i)http-equiv=["\']Content-Security-Policy')


class CORSAndHeaderTests(SecurityTestCase):
    def preflight(self, origin):
        return self.client.options('/api/students/', HTTP_ORIGIN=origin, HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST')

    def test_unknown_origin_gets_no_cors_grant(self):
        response = self.preflight('https://evil.example')
        self.assertNotIn('Access-Control-Allow-Origin', response)

    def test_allowed_origin_is_exact_not_wildcard(self):
        response = self.preflight('http://127.0.0.1:5500')
        self.assertEqual(response['Access-Control-Allow-Origin'], 'http://127.0.0.1:5500')
        self.assertEqual(response['Access-Control-Allow-Credentials'], 'true')

    def test_api_security_headers(self):
        response = self.client.get('/api/auth/csrf/')
        self.assertEqual(response['X-Frame-Options'], 'DENY')
        self.assertEqual(response['X-Content-Type-Options'], 'nosniff')

    def test_errors_do_not_leak_debug_details(self):
        self.assertFalse(settings.DEBUG)
        self.login_as(self.u_staff)
        body = self.client.get('/api/students/999999/').content.decode()
        self.assertNotIn('Traceback', body)


class FrontendExposureTests(SecurityTestCase):
    def test_H1_frontend_is_served_from_a_folder_without_secrets(self):
        """The static file server must serve a folder that contains only frontend files."""
        frontend = REPO_ROOT / 'frontend'
        self.assertTrue((frontend / 'index.html').is_file(), 'frontend/ folder does not exist; http.server serves the repo root')
        for secret in ('.env', 'backend', '.git', 'db.sqlite3', 'data_backup.json'):
            with self.subTest(item=secret):
                self.assertFalse(any(frontend.rglob(secret)), f'{secret} is reachable from the served folder')

    def test_H1_readme_serves_frontend_folder_only(self):
        readme = (REPO_ROOT / 'README.md').read_text(encoding='utf-8')
        for command in re.findall(r'.*http\.server.*', readme):
            with self.subTest(command=command.strip()):
                self.assertIn('frontend', command)
