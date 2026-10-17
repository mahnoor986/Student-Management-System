from rest_framework import status
from rest_framework.test import APITestCase
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import Client
from django.core.management import call_command
from io import StringIO
from django.contrib.staticfiles import finders
from django.templatetags.static import static
from .models import Attendance, Department, Student

User = get_user_model()


class StudentAPITests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username='staff-test', password='Valid-test-password-983!', is_staff=True)
        self.client.force_authenticate(user=self.staff)

    def payload(self, **overrides):
        return {
            'student_id': 'STU-1001', 'first_name': 'Ayesha', 'last_name': 'Khan',
            'email': 'ayesha@example.com', 'phone': '03001234567', 'course': 'Computer Science',
            'date_of_birth': '2004-05-14', 'enrollment_date': '2025-09-01', 'status': 'Active',
            **overrides,
        }

    def create_student(self, **overrides):
        return Student.objects.create(
            student_id=overrides.get('student_id', 'STU-1001'),
            first_name=overrides.get('first_name', 'Ayesha'), last_name=overrides.get('last_name', 'Khan'),
            email=overrides.get('email', 'ayesha@example.com'), course=overrides.get('course', 'Computer Science'),
            status=overrides.get('status', Student.Status.ACTIVE),
        )

    def test_list_endpoint(self):
        self.create_student()
        response = self.client.get('/api/students/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_create_student(self):
        response = self.client.post('/api/students/', self.payload(), format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Student.objects.count(), 1)

    def test_required_field_validation(self):
        data = self.payload()
        del data['first_name']
        response = self.client.post('/api/students/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('first_name', response.data)

    def test_invalid_email(self):
        response = self.client.post('/api/students/', self.payload(email='bad-email'), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_duplicate_email(self):
        self.create_student()
        response = self.client.post('/api/students/', self.payload(student_id='STU-1002', email='AYESHA@example.com'), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_duplicate_student_id(self):
        self.create_student()
        response = self.client.post('/api/students/', self.payload(email='other@example.com'), format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('student_id', response.data)

    def test_retrieve_student(self):
        student = self.create_student()
        response = self.client.get(f'/api/students/{student.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['student_id'], student.student_id)

    def test_update_student(self):
        student = self.create_student()
        data = self.payload(student_id=student.student_id, email=student.email, first_name='Aisha')
        response = self.client.put(f'/api/students/{student.pk}/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student.refresh_from_db()
        self.assertEqual(student.first_name, 'Aisha')

    def test_partial_update_student(self):
        student = self.create_student()
        response = self.client.patch(f'/api/students/{student.pk}/', {'status': Student.Status.INACTIVE}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        student.refresh_from_db()
        self.assertEqual(student.status, Student.Status.INACTIVE)

    def test_delete_student(self):
        student = self.create_student()
        response = self.client.delete(f'/api/students/{student.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Student.objects.exists())

    def test_search_and_filtering(self):
        self.create_student()
        self.create_student(student_id='STU-1002', email='hamza@example.com', first_name='Hamza', course='Data Science', status=Student.Status.INACTIVE)
        searched = self.client.get('/api/students/', {'search': 'Hamza Data'})
        filtered = self.client.get('/api/students/', {'course': 'Computer Science', 'status': 'Active'})
        self.assertEqual(len(searched.data), 1)
        self.assertEqual(searched.data[0]['student_id'], 'STU-1002')
        self.assertEqual(len(filtered.data), 1)

    def test_missing_student(self):
        response = self.client.get('/api/students/9999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_summary_counts_all_statuses(self):
        self.create_student()
        self.create_student(student_id='STU-1002', email='b@example.com', status=Student.Status.GRADUATED)
        response = self.client.get('/api/students/summary/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_students'], 2)
        self.assertEqual(response.data['graduated_students'], 1)

    def test_local_frontend_cors_preflight(self):
        response = self.client.options(
            '/api/students/',
            HTTP_ORIGIN='http://127.0.0.1:5500',
            HTTP_ACCESS_CONTROL_REQUEST_METHOD='POST',
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS='content-type',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Access-Control-Allow-Origin'], 'http://127.0.0.1:5500')

    def test_student_is_registered_in_admin(self):
        self.assertIn(Student, admin.site._registry)

    def test_django_admin_static_assets_are_configured_and_discoverable(self):
        self.assertEqual(static('admin/css/base.css'), '/static/admin/css/base.css')
        for asset in ('admin/css/base.css', 'admin/js/core.js'):
            with self.subTest(asset=asset):
                self.assertTrue(finders.find(asset))


class AuthorizationTests(APITestCase):
    def setUp(self):
        self.student = Student.objects.create(
            student_id='AUTH-1001', first_name='Test', last_name='Student',
            email='auth.student@example.com', course='Computer Science',
        )

    def test_anonymous_user_cannot_read_or_write_student_api(self):
        self.assertEqual(self.client.get('/api/students/').status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get('/api/students/summary/').status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(f'/api/students/{self.student.pk}/').status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.post('/api/students/', {}, format='json').status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.put(f'/api/students/{self.student.pk}/', {}, format='json').status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.patch(f'/api/students/{self.student.pk}/', {}, format='json').status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.delete(f'/api/students/{self.student.pk}/').status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_can_read_but_cannot_mutate_records(self):
        user = User.objects.create_user(username='reader-test', password='Valid-test-password-983!')
        self.client.force_authenticate(user=user)
        self.assertEqual(self.client.get('/api/students/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get('/api/students/summary/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.get(f'/api/students/{self.student.pk}/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.post('/api/students/', {}, format='json').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.put(f'/api/students/{self.student.pk}/', {}, format='json').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.patch(f'/api/students/{self.student.pk}/', {'status': 'Inactive'}, format='json').status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(self.client.delete(f'/api/students/{self.student.pk}/').status_code, status.HTTP_403_FORBIDDEN)


class SessionAuthenticationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='session-test', password='Valid-test-password-983!')
        self.client = Client(enforce_csrf_checks=True)

    def csrf_token(self):
        response = self.client.get('/api/auth/csrf/')
        self.assertEqual(response.status_code, 200)
        return response.json()['csrfToken']

    def test_login_logout_and_session(self):
        token = self.csrf_token()
        response = self.client.post(
            '/api/auth/login/',
            data={'username': 'session-test', 'password': 'Valid-test-password-983!'},
            content_type='application/json', HTTP_ORIGIN='http://127.0.0.1:5500', HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['user']['is_staff'] is False)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)
        self.assertEqual(self.client.get('/api/students/').status_code, status.HTTP_200_OK)
        token = self.csrf_token()
        response = self.client.post(
            '/api/auth/logout/', data='{}', content_type='application/json',
            HTTP_ORIGIN='http://127.0.0.1:5500', HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 401)

    def test_login_requires_csrf_and_rejects_invalid_password(self):
        response = self.client.post(
            '/api/auth/login/', data={'username': 'session-test', 'password': 'wrong'},
            content_type='application/json', HTTP_ORIGIN='http://127.0.0.1:5500',
        )
        self.assertEqual(response.status_code, 403)
        token = self.csrf_token()
        response = self.client.post(
            '/api/auth/login/', data={'username': 'session-test', 'password': 'wrong'},
            content_type='application/json', HTTP_ORIGIN='http://127.0.0.1:5500', HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 401)

    def test_login_rejects_malformed_credentials(self):
        token = self.csrf_token()
        response = self.client.post(
            '/api/auth/login/', data={'username': None, 'password': 123},
            content_type='application/json', HTTP_ORIGIN='http://127.0.0.1:5500', HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('detail', response.json())


class PhaseFourAPITests(APITestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username='phase4-staff', password='Strong-test-password-983!', is_staff=True)
        self.reader = User.objects.create_user(username='phase4-reader', password='Strong-test-password-983!')
        self.client.force_authenticate(user=self.staff)
        self.department = Department.objects.create(name='Science', code='SCI')
        self.student = Student.objects.create(student_id='P4-1001', first_name='Ayesha', last_name='Khan', email='p4@example.com', course='Biology', department=self.department, address='12 Example Road')

    def test_student_profile_fields_and_department_filter(self):
        response = self.client.get('/api/students/', {'department': self.department.pk})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data[0]['department_name'], 'Science')
        self.assertEqual(self.client.get('/api/departments/').data[0]['student_count'], 1)
        self.assertEqual(self.client.get(f'/api/students/{self.student.pk}/').data['address'], '12 Example Road')

    def test_department_delete_is_blocked_when_students_use_it(self):
        response = self.client.delete(f'/api/departments/{self.department.pk}/')
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
        self.assertTrue(Department.objects.filter(pk=self.department.pk).exists())

    def test_attendance_unique_per_student_and_date(self):
        payload = {'student': self.student.pk, 'date': '2026-10-17', 'status': 'Present'}
        first = self.client.post('/api/attendance/', payload, format='json')
        duplicate = self.client.post('/api/attendance/', payload, format='json')
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(duplicate.status_code, status.HTTP_400_BAD_REQUEST)

    def test_attendance_read_only_for_regular_users(self):
        Attendance.objects.create(student=self.student, date='2026-10-17', status=Attendance.Status.LATE)
        self.client.force_authenticate(user=self.reader)
        self.assertEqual(self.client.get('/api/attendance/').status_code, status.HTTP_200_OK)
        self.assertEqual(self.client.post('/api/attendance/', {}, format='json').status_code, status.HTTP_403_FORBIDDEN)
        self.assertNotIn('address', self.client.get(f'/api/students/{self.student.pk}/').data)
        self.assertNotIn('address', self.client.get('/api/students/summary/').data['recent_students'][0])


class SeedStudentsCommandTests(APITestCase):
    def test_seed_is_repeatable_and_does_not_overwrite_existing_records(self):
        existing = Student.objects.create(
            student_id='DEMO-2026-001', first_name='Existing', last_name='Record',
            email='existing@example.test', course='Existing Course',
        )
        first_output = StringIO()
        second_output = StringIO()
        call_command('seed_students', stdout=first_output)
        call_command('seed_students', stdout=second_output)

        self.assertEqual(Student.objects.count(), 15)
        self.assertEqual(Department.objects.count(), 4)
        existing.refresh_from_db()
        self.assertEqual(existing.first_name, 'Existing')
        self.assertEqual(existing.course, 'Existing Course')
        self.assertIn('14 created, 1 already present', first_output.getvalue())
        self.assertIn('0 created, 15 already present', second_output.getvalue())

        staff = User.objects.create_user(username='seed-dashboard-staff', password='Strong-test-password-983!', is_staff=True)
        self.client.force_authenticate(user=staff)
        summary = self.client.get('/api/students/summary/')
        listed = self.client.get('/api/students/')
        self.assertEqual(summary.status_code, status.HTTP_200_OK)
        self.assertEqual(summary.data['total_students'], 15)
        self.assertEqual(summary.data['active_students'], 10)
        self.assertEqual(summary.data['inactive_students'], 3)
        self.assertEqual(summary.data['graduated_students'], 2)
        self.assertEqual(listed.status_code, status.HTTP_200_OK)
        self.assertEqual(len(listed.data), 15)
