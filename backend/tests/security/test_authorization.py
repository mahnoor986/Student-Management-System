"""Cross-user access (IDOR), vertical escalation, mass assignment and role integrity."""
from django.core.exceptions import ValidationError

from students.access import get_role
from students.models import Attendance, ParentProfile, Student, TeacherProfile

from .base import SecurityTestCase, User


class CrossUserAccessTests(SecurityTestCase):
    """A user changes an ID in the URL to reach someone else's data."""

    def assert_hidden(self, user, other_student, other_attendance, other_class):
        self.login_as(user)
        for path in (f'/api/students/{other_student.pk}/', f'/api/attendance/{other_attendance.pk}/', f'/api/classes/{other_class.pk}/'):
            with self.subTest(user=user.username, path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_student_a_cannot_read_student_b(self):
        self.assert_hidden(self.u_student_a, self.student_b, self.att_b, self.class_b)

    def test_parent_a_cannot_read_parent_b_child(self):
        self.assert_hidden(self.u_parent_a, self.student_b, self.att_b, self.class_b)

    def test_teacher_a_cannot_read_class_b(self):
        self.assert_hidden(self.u_teacher_a, self.student_b, self.att_b, self.class_b)

    def test_query_filters_do_not_leak_other_records(self):
        self.login_as(self.u_student_a)
        self.assertEqual(self.rows(self.client.get(f'/api/attendance/?student={self.student_b.pk}')), [])
        self.assertEqual(self.rows(self.client.get('/api/students/?search=STU-B')), [])

    def test_teacher_a_cannot_edit_or_move_attendance_into_class_b(self):
        self.login_as(self.u_teacher_a)
        self.assertEqual(self.client.patch(f'/api/attendance/{self.att_b.pk}/', {'status': 'Present'}, format='json').status_code, 404)
        self.assertEqual(self.client.patch(f'/api/attendance/{self.att_a.pk}/', {'student': self.student_b.pk}, format='json').status_code, 400)
        self.assertEqual(Attendance.objects.get(pk=self.att_a.pk).student_id, self.student_a.pk)

    def test_private_address_only_for_self_parent_and_staff(self):
        path = f'/api/students/{self.student_a.pk}/'
        for user, visible in ((self.u_student_a, True), (self.u_parent_a, True), (self.u_staff, True),
                              (self.u_teacher_a, False), (self.u_viewer, False)):
            with self.subTest(user=user.username):
                self.login_as(user)
                self.assertEqual('address' in self.client.get(path).data, visible)


class VerticalEscalationTests(SecurityTestCase):
    def test_non_staff_roles_cannot_call_staff_actions(self):
        actions = [
            ('post', '/api/students/', {'student_id': 'X1', 'first_name': 'X', 'last_name': 'Y', 'email': 'x1@example.test', 'course': 'C'}),
            ('delete', f'/api/students/{self.student_a2.pk}/', None),
            ('post', '/api/departments/', {'name': 'Hack'}),
            ('post', '/api/classes/', {'name': 'HACK'}),
            ('delete', f'/api/attendance/{self.att_a.pk}/', None),
        ]
        for user in (self.u_student_a, self.u_parent_a, self.u_teacher_a, self.u_viewer, self.u_unlinked):
            self.login_as(user)
            for method, path, body in actions:
                with self.subTest(user=user.username, method=method, path=path):
                    self.assertEqual(getattr(self.client, method)(path, body, format='json').status_code, 403)
        self.assertTrue(Student.objects.filter(pk=self.student_a2.pk).exists())

    def test_role_flags_cannot_be_changed_through_the_api(self):
        self.login_as(self.u_student_a)
        for method in ('post', 'put', 'patch'):
            with self.subTest(method=method):
                self.assertEqual(getattr(self.client, method)('/api/auth/me/', {'is_staff': True, 'is_superuser': True}, format='json').status_code, 405)
        self.u_student_a.refresh_from_db()
        self.assertFalse(self.u_student_a.is_staff or self.u_student_a.is_superuser)

    def test_L8_staff_with_user_change_permission_cannot_make_themselves_superuser(self):
        from django.contrib.auth.models import Permission
        manager = User.objects.create_user('user_manager', password='Mgr-pass-55123!', is_staff=True)
        manager.user_permissions.add(*Permission.objects.filter(codename__in=['change_user', 'view_user']))
        self.login_as(manager)
        form = {'username': 'user_manager', 'is_active': 'on', 'is_staff': 'on', 'is_superuser': 'on',
                'date_joined_0': '2026-01-01', 'date_joined_1': '00:00:00', 'last_login_0': '', 'last_login_1': ''}
        self.client.post(f'/admin/auth/user/{manager.pk}/change/', form)
        manager.refresh_from_db()
        self.assertFalse(manager.is_superuser, 'staff with auth.change_user promoted itself to superuser')


class MassAssignmentTests(SecurityTestCase):
    def test_student_create_ignores_user_id_and_read_only_fields(self):
        self.login_as(self.u_staff)
        response = self.client.post('/api/students/', {
            'student_id': 'MASS-1', 'first_name': 'Mass', 'last_name': 'Assign', 'email': 'mass@example.test', 'course': 'C',
            'user': self.u_superuser.pk, 'id': 99999, 'created_at': '2000-01-01T00:00:00Z'}, format='json')
        self.assertEqual(response.status_code, 201)
        created = Student.objects.get(student_id='MASS-1')
        self.assertIsNone(created.user_id)
        self.assertNotEqual(created.pk, 99999)
        self.assertNotEqual(created.created_at.year, 2000)

    def test_student_update_cannot_link_a_login(self):
        self.login_as(self.u_staff)
        self.client.patch(f'/api/students/{self.student_a2.pk}/', {'user': self.u_teacher_b.pk}, format='json')
        self.assertIsNone(Student.objects.get(pk=self.student_a2.pk).user_id)


class RoleIntegrityTests(SecurityTestCase):
    def test_admin_form_validation_blocks_second_role(self):
        with self.assertRaises(ValidationError):
            TeacherProfile(user=self.u_parent_a).full_clean()

    def test_L5_second_role_is_blocked_even_outside_admin_forms(self):
        user = User.objects.create_user('double_role', password='Dbl-pass-88123!')
        TeacherProfile.objects.create(user=user)
        with self.assertRaises(ValidationError):
            ParentProfile.objects.create(user=user)
        self.assertEqual(get_role(user), 'teacher')

    def test_H2_removed_teacher_loses_all_access(self):
        user = User.objects.create_user('ex_teacher', password='Ex-pass-66123!')
        TeacherProfile.objects.create(user=user).delete()
        self.login_as(user)
        self.assertEqual(self.rows(self.client.get('/api/students/')), [])

    def test_H2_deleted_student_record_leaves_login_without_access(self):
        user = User.objects.create_user('graduate', password='Grad-pass-66123!')
        Student.objects.create(student_id='GRAD', first_name='G', last_name='R', email='g@example.test', course='C', user=user).delete()
        self.login_as(user)
        self.assertEqual(self.rows(self.client.get('/api/students/')), [])


class InformationLeakTests(SecurityTestCase):
    def test_L9_org_wide_student_counts_hidden_from_students_and_parents(self):
        for user in (self.u_student_a, self.u_parent_a):
            with self.subTest(user=user.username):
                self.login_as(user)
                row = self.rows(self.client.get('/api/departments/'))[0]
                self.assertNotIn('student_count', row)
