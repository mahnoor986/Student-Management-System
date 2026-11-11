"""Functional tests for student / teacher / parent logins and role-scoped access."""
from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.core.management import call_command
from rest_framework import status
from rest_framework.test import APITestCase

from .access import get_role
from .models import Attendance, ClassSection, ParentProfile, Student, TeacherProfile

User = get_user_model()


class RoleAccessTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.class_a = ClassSection.objects.create(name='CS-1A')
        cls.class_b = ClassSection.objects.create(name='BUS-1A')

        def student(code, class_section, **extra):
            return Student.objects.create(student_id=code, first_name=code, last_name='Test', email=f'{code.lower()}@example.test',
                                          course='Computer Science', class_section=class_section, address=f'{code} Street', **extra)

        cls.user_student_a = User.objects.create_user('student-a', password='Pw-test-12345!')
        cls.user_student_b = User.objects.create_user('student-b', password='Pw-test-12345!')
        cls.student_a = student('STU-A', cls.class_a, user=cls.user_student_a)
        cls.student_a2 = student('STU-A2', cls.class_a)
        cls.student_b = student('STU-B', cls.class_b, user=cls.user_student_b)
        cls.student_none = student('STU-N', None)

        cls.teacher_a = User.objects.create_user('teacher-a', password='Pw-test-12345!')
        cls.teacher_b = User.objects.create_user('teacher-b', password='Pw-test-12345!')
        TeacherProfile.objects.create(user=cls.teacher_a).classes.add(cls.class_a)
        TeacherProfile.objects.create(user=cls.teacher_b).classes.add(cls.class_b)

        cls.parent_a = User.objects.create_user('parent-a', password='Pw-test-12345!')
        cls.parent_b = User.objects.create_user('parent-b', password='Pw-test-12345!')
        ParentProfile.objects.create(user=cls.parent_a).children.add(cls.student_a)
        ParentProfile.objects.create(user=cls.parent_b).children.add(cls.student_b)

        cls.staff = User.objects.create_user('staff', password='Pw-test-12345!', is_staff=True)
        cls.viewer = User.objects.create_user('viewer', password='Pw-test-12345!')
        cls.viewer.groups.add(Group.objects.get(name='Viewers'))  # read-only access is opt-in (audit H2)
        cls.unlinked = User.objects.create_user('unlinked', password='Pw-test-12345!')

        cls.att_a = Attendance.objects.create(student=cls.student_a, date='2026-01-05', status='Present')
        cls.att_b = Attendance.objects.create(student=cls.student_b, date='2026-01-05', status='Absent')

    def ids(self, response):
        return sorted(item['student_id'] if 'student_id' in item else item['id'] for item in response.data)

    def as_user(self, user):
        self.client.force_authenticate(user=user)

    # --- roles ---------------------------------------------------------------
    def test_role_detection(self):
        self.assertEqual(get_role(self.staff), 'staff')
        self.assertEqual(get_role(self.teacher_a), 'teacher')
        self.assertEqual(get_role(self.parent_a), 'parent')
        self.assertEqual(get_role(self.user_student_a), 'student')
        self.assertEqual(get_role(self.viewer), 'viewer')
        self.assertEqual(get_role(self.unlinked), 'none')

    def test_login_without_a_role_sees_nothing(self):
        self.as_user(self.unlinked)
        self.assertEqual(self.client.get('/api/students/').data, [])
        self.assertEqual(self.client.get(f'/api/students/{self.student_a.pk}/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get('/api/auth/me/').data['user']['role'], 'none')

    def test_me_endpoint_reports_role(self):
        self.as_user(self.teacher_a)
        response = self.client.get('/api/auth/me/')
        self.assertEqual(response.data['user']['role'], 'teacher')

    def test_login_can_hold_only_one_role(self):
        profile = TeacherProfile(user=self.user_student_a)
        with self.assertRaises(ValidationError):
            profile.full_clean()
        staff_parent = ParentProfile(user=self.staff)
        with self.assertRaises(ValidationError):
            staff_parent.full_clean()

    # --- student scoping -----------------------------------------------------
    def test_student_sees_only_own_record(self):
        self.as_user(self.user_student_a)
        self.assertEqual(self.ids(self.client.get('/api/students/')), ['STU-A'])
        self.assertEqual(self.client.get(f'/api/students/{self.student_b.pk}/').status_code, status.HTTP_404_NOT_FOUND)

    def test_parent_sees_only_own_children(self):
        self.as_user(self.parent_a)
        self.assertEqual(self.ids(self.client.get('/api/students/')), ['STU-A'])
        self.assertEqual(self.client.get(f'/api/students/{self.student_b.pk}/').status_code, status.HTTP_404_NOT_FOUND)

    def test_teacher_sees_only_students_in_their_classes(self):
        self.as_user(self.teacher_a)
        self.assertEqual(self.ids(self.client.get('/api/students/')), ['STU-A', 'STU-A2'])
        self.assertEqual(self.client.get(f'/api/students/{self.student_b.pk}/').status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(f'/api/students/{self.student_none.pk}/').status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_and_viewer_see_everyone(self):
        for user in (self.staff, self.viewer):
            self.as_user(user)
            self.assertEqual(len(self.client.get('/api/students/').data), 4)

    def test_summary_is_scoped(self):
        self.as_user(self.parent_b)
        response = self.client.get('/api/students/summary/')
        self.assertEqual(response.data['total_students'], 1)
        self.assertEqual([s['student_id'] for s in response.data['recent_students']], ['STU-B'])

    # --- private details (address) ------------------------------------------
    def test_address_visible_to_self_parent_and_staff_only(self):
        url = f'/api/students/{self.student_a.pk}/'
        for user in (self.user_student_a, self.parent_a, self.staff):
            self.as_user(user)
            self.assertEqual(self.client.get(url).data.get('address'), 'STU-A Street', user.username)
        for user in (self.teacher_a, self.viewer):
            self.as_user(user)
            self.assertNotIn('address', self.client.get(url).data, user.username)

    def test_linked_login_is_not_exposed(self):
        self.as_user(self.staff)
        self.assertNotIn('user', self.client.get(f'/api/students/{self.student_a.pk}/').data)

    # --- student writes stay staff-only --------------------------------------
    def test_non_staff_roles_cannot_change_students(self):
        for user in (self.teacher_a, self.parent_a, self.user_student_a):
            self.as_user(user)
            self.assertEqual(self.client.patch(f'/api/students/{self.student_a.pk}/', {'status': 'Inactive'}, format='json').status_code, status.HTTP_403_FORBIDDEN)
            self.assertEqual(self.client.post('/api/classes/', {'name': 'X'}, format='json').status_code, status.HTTP_403_FORBIDDEN)

    # --- attendance ----------------------------------------------------------
    def test_attendance_is_scoped(self):
        self.as_user(self.user_student_a)
        self.assertEqual([r['id'] for r in self.client.get('/api/attendance/').data], [self.att_a.pk])
        self.assertEqual(self.client.get(f'/api/attendance/{self.att_b.pk}/').status_code, status.HTTP_404_NOT_FOUND)

    def test_teacher_records_attendance_only_for_own_students(self):
        self.as_user(self.teacher_a)
        ok = self.client.post('/api/attendance/', {'student': self.student_a2.pk, 'date': '2026-01-06', 'status': 'Late'}, format='json')
        self.assertEqual(ok.status_code, status.HTTP_201_CREATED)
        other = self.client.post('/api/attendance/', {'student': self.student_b.pk, 'date': '2026-01-06', 'status': 'Late'}, format='json')
        self.assertEqual(other.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.client.patch(f'/api/attendance/{self.att_b.pk}/', {'status': 'Present'}, format='json').status_code, status.HTTP_404_NOT_FOUND)
        moved = self.client.patch(f'/api/attendance/{self.att_a.pk}/', {'student': self.student_b.pk}, format='json')
        self.assertEqual(moved.status_code, status.HTTP_400_BAD_REQUEST)

    def test_teacher_cannot_delete_attendance(self):
        self.as_user(self.teacher_a)
        self.assertEqual(self.client.delete(f'/api/attendance/{self.att_a.pk}/').status_code, status.HTTP_403_FORBIDDEN)

    def test_students_parents_and_viewers_cannot_record_attendance(self):
        for user in (self.user_student_a, self.parent_a, self.viewer):
            self.as_user(user)
            response = self.client.post('/api/attendance/', {'student': self.student_a.pk, 'date': '2026-01-07', 'status': 'Present'}, format='json')
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN, user.username)

    # --- classes -------------------------------------------------------------
    def test_classes_are_scoped(self):
        self.as_user(self.teacher_b)
        self.assertEqual([c['name'] for c in self.client.get('/api/classes/').data], ['BUS-1A'])
        self.as_user(self.parent_a)
        self.assertEqual([c['name'] for c in self.client.get('/api/classes/').data], ['CS-1A'])
        self.as_user(self.staff)
        self.assertEqual(len(self.client.get('/api/classes/').data), 2)


class SeedDemoAccountsTests(APITestCase):
    def test_creates_two_of_each_role_and_is_repeatable(self):
        call_command('seed_demo_accounts', password='Demo-pass-12345!', stdout=StringIO())
        call_command('seed_demo_accounts', stdout=StringIO())
        roles = {name: get_role(User.objects.get(username=name)) for name in (
            'demo.teacher.a', 'demo.teacher.b', 'demo.student.a', 'demo.student.b', 'demo.parent.a', 'demo.parent.b')}
        self.assertEqual(sorted(roles.values()), ['parent', 'parent', 'student', 'student', 'teacher', 'teacher'])
        self.assertTrue(User.objects.get(username='demo.parent.a').check_password('Demo-pass-12345!'))
