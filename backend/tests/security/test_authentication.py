"""Authentication, sessions, cookies, passwords and rate limiting."""
from datetime import timedelta

from django.conf import settings
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.sessions.models import Session
from django.utils import timezone

from .base import PASSWORD, SecurityTestCase, User

PROTECTED_API = [
    ('get', '/api/students/'), ('post', '/api/students/'), ('get', '/api/students/summary/'),
    ('get', '/api/students/1/'), ('put', '/api/students/1/'), ('patch', '/api/students/1/'), ('delete', '/api/students/1/'),
    ('get', '/api/departments/'), ('post', '/api/departments/'), ('get', '/api/departments/1/'), ('patch', '/api/departments/1/'), ('delete', '/api/departments/1/'),
    ('get', '/api/classes/'), ('post', '/api/classes/'), ('get', '/api/classes/1/'), ('patch', '/api/classes/1/'), ('delete', '/api/classes/1/'),
    ('get', '/api/attendance/'), ('post', '/api/attendance/'), ('get', '/api/attendance/1/'), ('patch', '/api/attendance/1/'), ('delete', '/api/attendance/1/'),
    ('get', '/api/auth/me/'), ('post', '/api/auth/logout/'),
]
PROTECTED_ADMIN = ['/admin/', '/admin/students/student/', '/admin/auth/user/', '/admin/auth/user/add/', '/admin/password_change/']


class UnauthenticatedAccessTests(SecurityTestCase):
    def test_every_protected_api_route_returns_401(self):
        for method, path in PROTECTED_API:
            with self.subTest(method=method, path=path):
                self.assertEqual(getattr(self.client, method)(path, format='json').status_code, 401)

    def test_admin_pages_redirect_to_login(self):
        for path in PROTECTED_ADMIN:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn('/admin/login/', response['Location'])

    def test_non_staff_roles_cannot_open_admin(self):
        for user in (self.u_student_a, self.u_parent_a, self.u_teacher_a, self.u_viewer):
            with self.subTest(user=user.username):
                self.login_as(user)
                self.assertEqual(self.client.get('/admin/').status_code, 302)


class SessionTests(SecurityTestCase):
    def api_login(self, client, username, password=PASSWORD):
        return client.post('/api/auth/login/', {'username': username, 'password': password}, format='json')

    def test_session_id_changes_on_login(self):
        planted = SessionStore()
        planted['planted'] = True
        planted.create()
        self.client.cookies['sessionid'] = planted.session_key
        self.assertEqual(self.api_login(self.client, 'student_a').status_code, 200)
        self.assertNotEqual(self.client.cookies['sessionid'].value, planted.session_key)
        self.assertFalse(Session.objects.filter(session_key=planted.session_key).exists())

    def test_logout_invalidates_session_server_side(self):
        self.api_login(self.client, 'student_a')
        stolen = self.client.cookies['sessionid'].value
        self.assertEqual(self.client.post('/api/auth/logout/').status_code, 204)
        replay = self.client_class()
        replay.cookies['sessionid'] = stolen
        self.assertEqual(replay.get('/api/auth/me/').status_code, 401)

    def test_tampered_session_cookie_is_rejected(self):
        self.client.cookies['sessionid'] = 'x' * 32
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_expired_session_is_rejected(self):
        self.api_login(self.client, 'student_a')
        Session.objects.filter(session_key=self.client.cookies['sessionid'].value).update(expire_date=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_deactivated_user_session_is_rejected(self):
        self.api_login(self.client, 'student_a')
        User.objects.filter(pk=self.u_student_a.pk).update(is_active=False)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_password_change_elsewhere_invalidates_session(self):
        self.api_login(self.client, 'student_a')
        user = User.objects.get(pk=self.u_student_a.pk)
        user.set_password('Another-pass-9911!')
        user.save()
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_auth_cookie_flags(self):
        response = self.api_login(self.client, 'student_a')
        cookie = response.cookies['sessionid']
        self.assertTrue(cookie['httponly'])
        self.assertEqual(cookie['samesite'], 'Lax')

    def test_L2_session_lifetime_is_short(self):
        """Policy: sessions expire within 12 hours (Django default is 2 weeks)."""
        self.assertLessEqual(settings.SESSION_COOKIE_AGE, 12 * 60 * 60)


class LoginTests(SecurityTestCase):
    def test_same_error_for_unknown_user_and_wrong_password(self):
        unknown = self.client.post('/api/auth/login/', {'username': 'nobody', 'password': 'x'}, format='json')
        wrong = self.client.post('/api/auth/login/', {'username': 'student_a', 'password': 'x'}, format='json')
        self.assertEqual((unknown.status_code, unknown.data), (wrong.status_code, wrong.data))

    def test_api_login_is_rate_limited_per_client(self):
        codes = [self.client.post('/api/auth/login/', {'username': 'student_a', 'password': 'wrong'}, format='json').status_code for _ in range(11)]
        self.assertEqual(codes[-1], 429)

    def test_L4_api_login_is_rate_limited_per_account(self):
        """Rotating IP addresses must not allow unlimited guesses against one account."""
        codes = [self.client.post('/api/auth/login/', {'username': 'student_a', 'password': 'wrong'}, format='json',
                                  REMOTE_ADDR=f'10.0.0.{i}').status_code for i in range(1, 13)]
        self.assertEqual(codes[-1], 429)

    def test_M1_admin_login_is_rate_limited(self):
        codes = [self.client.post('/admin/login/', {'username': 'root', 'password': 'wrong'}).status_code for _ in range(11)]
        self.assertIn(codes[-1], (403, 429), 'admin login allowed 11 rapid failed attempts')

    def test_M4_users_can_change_their_own_password(self):
        self.login_as(self.u_parent_a)
        response = self.client.post('/api/auth/password/', {'current_password': PASSWORD, 'new_password': 'Fresh-pass-7713!'}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.get(pk=self.u_parent_a.pk).check_password('Fresh-pass-7713!'))


class PasswordStorageTests(SecurityTestCase):
    def test_password_is_hashed_not_plaintext(self):
        stored = User.objects.get(pk=self.u_student_a.pk).password
        self.assertNotIn(PASSWORD, stored)
        self.assertRegex(stored, r'^(argon2|bcrypt|pbkdf2_sha256)\$')

    def test_L3_password_hasher_is_argon2(self):
        user = User.objects.create_user('fresh_hash', password=PASSWORD)
        self.assertTrue(user.password.startswith('argon2'), user.password.split('$')[0])
