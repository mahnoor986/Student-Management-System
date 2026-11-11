"""One test per cell of the agreed permission matrix (role x resource x action -> expected HTTP status).

Expected values encode the business rules agreed in the audit:
  * H2 / decision B: a login with no linked record sees nothing; only the "Viewers" group reads everything.
  * M2: staff API writes follow Django model permissions (staff_limited has view-only permissions).
Cells that fail today point at those findings; see SECURITY_AUDIT.md.
"""
from .base import SecurityTestCase

ROLES = ['anon', 'unlinked', 'viewer', 'student_a', 'student_b', 'parent_a', 'parent_b',
         'teacher_a', 'teacher_b', 'staff_limited', 'staff', 'superuser']

def expect(default, **overrides):
    table = {role: default for role in ROLES}
    table['anon'] = 401
    table.update(overrides)
    return table


# Who may see records linked to student A / class A (students A, parent A, teacher A, viewer, staff).
SEES_A = dict(unlinked=404, viewer=200, student_a=200, student_b=404, parent_a=200, parent_b=404,
              teacher_a=200, teacher_b=404, staff_limited=200, staff=200, superuser=200)


def _student_payload(n):
    return {'student_id': f'NEW-{n}', 'first_name': 'New', 'last_name': 'Student', 'email': f'new{n}@example.test', 'course': 'Maths'}


# name, method, path(self), body(self) or None, expected {role: status}
MATRIX = [
    ('students_list', 'get', lambda t: '/api/students/', None, expect(200)),
    ('students_read_A', 'get', lambda t: f'/api/students/{t.student_a.pk}/', None, expect(200, **SEES_A)),
    ('students_create', 'post', lambda t: '/api/students/', lambda t: _student_payload(1), expect(403, staff=201, superuser=201)),
    ('students_update_A', 'patch', lambda t: f'/api/students/{t.student_a.pk}/', lambda t: {'status': 'Inactive'}, expect(403, staff=200, superuser=200)),
    ('students_delete_A2', 'delete', lambda t: f'/api/students/{t.student_a2.pk}/', None, expect(403, staff=204, superuser=204)),
    ('summary_read', 'get', lambda t: '/api/students/summary/', None, expect(200)),
    ('departments_list', 'get', lambda t: '/api/departments/', None, expect(200)),
    ('departments_create', 'post', lambda t: '/api/departments/', lambda t: {'name': 'Physics'}, expect(403, staff=201, superuser=201)),
    ('departments_update', 'patch', lambda t: f'/api/departments/{t.dept.pk}/', lambda t: {'description': 'x'}, expect(403, staff=200, superuser=200)),
    ('classes_read_A', 'get', lambda t: f'/api/classes/{t.class_a.pk}/', None, expect(200, **SEES_A)),
    ('classes_create', 'post', lambda t: '/api/classes/', lambda t: {'name': 'CLASS-C'}, expect(403, staff=201, superuser=201)),
    ('classes_delete_B', 'delete', lambda t: f'/api/classes/{t.class_b.pk}/', None, expect(403, staff=409, superuser=409)),
    ('attendance_read_A', 'get', lambda t: f'/api/attendance/{t.att_a.pk}/', None, expect(200, **SEES_A)),
    ('attendance_create_for_A', 'post', lambda t: '/api/attendance/', lambda t: {'student': t.student_a.pk, 'date': '2026-02-01', 'status': 'Present'},
     expect(403, teacher_a=201, teacher_b=400, staff=201, superuser=201)),
    ('attendance_update_A', 'patch', lambda t: f'/api/attendance/{t.att_a.pk}/', lambda t: {'status': 'Late'},
     expect(403, teacher_a=200, teacher_b=404, staff=200, superuser=200)),
    ('attendance_delete_A', 'delete', lambda t: f'/api/attendance/{t.att_a.pk}/', None, expect(403, staff=204, superuser=204)),
    ('me_read', 'get', lambda t: '/api/auth/me/', None, expect(200)),
    # Django Admin: user management is superuser-only (staff without auth.* perms get 403).
    ('admin_user_add', 'get', lambda t: '/admin/auth/user/add/', None, expect(302, anon=302, staff_limited=403, staff=403, superuser=200)),
    ('admin_student_delete', 'post', lambda t: f'/admin/students/student/{t.student_a2.pk}/delete/', lambda t: {'post': 'yes'},
     expect(302, anon=302, staff_limited=403, staff=302, superuser=302)),
]


class PermissionMatrixTests(SecurityTestCase):
    def role_user(self, role):
        return None if role == 'anon' else {
            'unlinked': self.u_unlinked, 'viewer': self.u_viewer, 'student_a': self.u_student_a, 'student_b': self.u_student_b,
            'parent_a': self.u_parent_a, 'parent_b': self.u_parent_b, 'teacher_a': self.u_teacher_a, 'teacher_b': self.u_teacher_b,
            'staff_limited': self.u_staff_limited, 'staff': self.u_staff, 'superuser': self.u_superuser,
        }[role]

    def check(self, role, method, path_fn, body_fn, expected):
        self.login_as(self.role_user(role))
        kwargs = {'format': 'json'} if path_fn(self).startswith('/api/') else {}
        if body_fn:
            kwargs['data'] = body_fn(self)
        response = getattr(self.client, method)(path_fn(self), **kwargs)
        self.assertEqual(response.status_code, expected, f'{role} {method.upper()} {path_fn(self)}')


def _make(role, method, path_fn, body_fn, expected):
    def test(self):
        self.check(role, method, path_fn, body_fn, expected)
    return test


for _name, _method, _path, _body, _expected in MATRIX:
    for _role in ROLES:
        setattr(PermissionMatrixTests, f'test_{_name}__{_role}', _make(_role, _method, _path, _body, _expected[_role]))


class ListScopingTests(SecurityTestCase):
    """List endpoints return 200 for everyone, so scoping is checked by content."""

    def test_H2_unlinked_login_sees_no_students(self):
        self.login_as(self.u_unlinked)
        self.assertEqual(self.rows(self.client.get('/api/students/')), [])

    def test_H2_unlinked_login_sees_no_attendance_or_classes(self):
        self.login_as(self.u_unlinked)
        self.assertEqual(self.rows(self.client.get('/api/attendance/')), [])
        self.assertEqual(self.rows(self.client.get('/api/classes/')), [])

    def test_H2_unlinked_summary_is_empty(self):
        self.login_as(self.u_unlinked)
        self.assertEqual(self.client.get('/api/students/summary/').data['total_students'], 0)

    def test_H2_viewers_group_reads_everyone_without_address(self):
        self.login_as(self.u_viewer)
        response = self.client.get('/api/students/')
        self.assertEqual(len(self.rows(response)), 3)
        self.assertTrue(all('address' not in row for row in self.rows(response)))

    def test_scoped_lists_per_role(self):
        cases = [(self.u_student_a, ['STU-A']), (self.u_parent_b, ['STU-B']), (self.u_teacher_a, ['STU-A', 'STU-A2']),
                 (self.u_teacher_b, ['STU-B']), (self.u_staff, ['STU-A', 'STU-A2', 'STU-B'])]
        for user, ids in cases:
            with self.subTest(user=user.username):
                self.login_as(user)
                self.assertEqual(self.student_ids(self.client.get('/api/students/')), ids)
