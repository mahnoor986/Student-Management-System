"""An Inactive student cannot sign in; Graduated students and other roles are unaffected."""
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from .models import ClassSection, ParentProfile, Student, TeacherProfile

User = get_user_model()
PASSWORD = 'Pw-test-12345!'


class StudentStatusLoginTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.klass = ClassSection.objects.create(name='CS-1A')
        cls.user = User.objects.create_user('stu', password=PASSWORD)
        cls.student = Student.objects.create(student_id='S1', first_name='S', last_name='One', email='s1@example.test',
                                             course='CS', class_section=cls.klass, user=cls.user)
        cls.teacher = User.objects.create_user('teach', password=PASSWORD)
        TeacherProfile.objects.create(user=cls.teacher).classes.add(cls.klass)
        cls.parent = User.objects.create_user('par', password=PASSWORD)
        ParentProfile.objects.create(user=cls.parent).children.add(cls.student)

    def set_status(self, value):
        Student.objects.filter(pk=self.student.pk).update(status=value)

    def login(self, username):
        return self.client.post('/api/auth/login/', {'username': username, 'password': PASSWORD}, format='json')

    def test_active_student_can_sign_in(self):
        self.assertEqual(self.login('stu').status_code, 200)

    def test_graduated_student_can_sign_in_and_see_own_record(self):
        self.set_status(Student.Status.GRADUATED)
        self.assertEqual(self.login('stu').status_code, 200)
        self.assertEqual(self.client.get(f'/api/students/{self.student.pk}/').status_code, 200)

    def test_inactive_student_cannot_sign_in(self):
        self.set_status(Student.Status.INACTIVE)
        response = self.login('stu')
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data['detail'], 'Invalid username or password.')  # no hint that the account exists

    def test_inactive_student_cannot_sign_in_to_admin(self):
        self.set_status(Student.Status.INACTIVE)
        self.assertFalse(self.client.login(username='stu', password=PASSWORD))

    def test_existing_session_ends_when_student_becomes_inactive(self):
        self.assertEqual(self.login('stu').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)
        self.set_status(Student.Status.INACTIVE)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)
        self.assertEqual(self.client.get('/api/students/').status_code, 401)

    def test_setting_back_to_active_restores_login(self):
        self.set_status(Student.Status.INACTIVE)
        self.assertEqual(self.login('stu').status_code, 401)
        self.set_status(Student.Status.ACTIVE)
        self.assertEqual(self.login('stu').status_code, 200)

    def test_teacher_and_parent_still_see_inactive_and_graduated_students(self):
        for value in (Student.Status.INACTIVE, Student.Status.GRADUATED):
            self.set_status(value)
            for username in ('teach', 'par'):
                with self.subTest(status=value, user=username):
                    self.client.force_login(User.objects.get(username=username))
                    self.assertEqual(self.client.get(f'/api/students/{self.student.pk}/').status_code, 200)
                    self.client.logout()
