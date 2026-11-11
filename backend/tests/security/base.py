"""Shared fixtures: two of every role, two classes, attendance, and staff with limited vs full permissions."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

from students.models import Attendance, ClassSection, Department, ParentProfile, Student, TeacherProfile

User = get_user_model()
PASSWORD = 'Sec-test-pass-4821!'
VIEWERS_GROUP = 'Viewers'  # decision B: explicit opt-in read-only group


class SecurityTestCase(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dept = Department.objects.create(name='Computing', code='CS')
        cls.class_a = ClassSection.objects.create(name='CLASS-A', department=cls.dept)
        cls.class_b = ClassSection.objects.create(name='CLASS-B')

        def make_user(username, **extra):
            return User.objects.create_user(username, password=PASSWORD, **extra)

        def make_student(code, class_section, user=None):
            return Student.objects.create(
                student_id=code, first_name=code, last_name='Pupil', email=f'{code.lower()}@example.test',
                phone='0300-0000000', course='Computer Science', class_section=class_section,
                address=f'{code} Private Street', user=user)

        cls.u_student_a = make_user('student_a')
        cls.u_student_b = make_user('student_b')
        cls.student_a = make_student('STU-A', cls.class_a, cls.u_student_a)
        cls.student_a2 = make_student('STU-A2', cls.class_a)
        cls.student_b = make_student('STU-B', cls.class_b, cls.u_student_b)

        cls.u_teacher_a = make_user('teacher_a')
        cls.u_teacher_b = make_user('teacher_b')
        TeacherProfile.objects.create(user=cls.u_teacher_a).classes.add(cls.class_a)
        TeacherProfile.objects.create(user=cls.u_teacher_b).classes.add(cls.class_b)

        cls.u_parent_a = make_user('parent_a')
        cls.u_parent_b = make_user('parent_b')
        ParentProfile.objects.create(user=cls.u_parent_a).children.add(cls.student_a)
        ParentProfile.objects.create(user=cls.u_parent_b).children.add(cls.student_b)

        cls.u_unlinked = make_user('unlinked')
        cls.u_viewer = make_user('viewer')
        cls.u_viewer.groups.add(Group.objects.create(name=VIEWERS_GROUP))

        app_perms = Permission.objects.filter(content_type__app_label='students')
        cls.u_staff_limited = make_user('staff_limited', is_staff=True)
        cls.u_staff_limited.user_permissions.set(app_perms.filter(codename__startswith='view_'))
        cls.u_staff = make_user('staff_full', is_staff=True)
        cls.u_staff.user_permissions.set(app_perms)
        cls.u_superuser = User.objects.create_superuser('root', 'root@example.test', PASSWORD)

        cls.att_a = Attendance.objects.create(student=cls.student_a, date='2026-01-05', status='Present')
        cls.att_b = Attendance.objects.create(student=cls.student_b, date='2026-01-05', status='Absent')

    def setUp(self):
        cache.clear()  # login throttles live in the cache; keep tests independent

    def login_as(self, user):
        """Real session login (not force_authenticate), so session and admin paths are exercised."""
        self.client.logout()
        if user is not None:
            self.client.force_login(user)

    @staticmethod
    def csrf_client():
        return APIClient(enforce_csrf_checks=True)

    @staticmethod
    def rows(response):
        """List payload whether or not the endpoint is paginated (L7 fix changes the shape)."""
        data = response.data
        return data['results'] if isinstance(data, dict) and 'results' in data else data

    def student_ids(self, response):
        return sorted(item['student_id'] for item in self.rows(response))
