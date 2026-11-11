"""Self-service password change: POST /api/auth/password/ (audit finding M4)."""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient, APITestCase

User = get_user_model()
OLD = 'Old-pass-test-4821!'
NEW = 'New-pass-test-7713!'
URL = '/api/auth/password/'


class PasswordChangeTests(APITestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user('changer', password=OLD)

    def login(self, client):
        client.post('/api/auth/login/', {'username': 'changer', 'password': OLD}, format='json')

    def test_requires_sign_in(self):
        self.assertEqual(self.client.post(URL, {'current_password': OLD, 'new_password': NEW}, format='json').status_code, 401)

    def test_wrong_current_password_is_rejected(self):
        self.login(self.client)
        response = self.client.post(URL, {'current_password': 'wrong', 'new_password': NEW}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('current_password', response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(OLD))

    def test_weak_new_password_is_rejected(self):
        self.login(self.client)
        response = self.client.post(URL, {'current_password': OLD, 'new_password': '123'}, format='json')
        self.assertEqual(response.status_code, 400)
        self.assertIn('new_password', response.data)

    def test_success_keeps_this_session_and_signs_out_others(self):
        other = APIClient()
        self.login(other)
        self.login(self.client)
        self.assertEqual(self.client.post(URL, {'current_password': OLD, 'new_password': NEW}, format='json').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/me/').status_code, 200)
        self.assertEqual(other.get('/api/auth/me/').status_code, 401)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW))

    def test_csrf_token_is_required(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(URL, {'current_password': OLD, 'new_password': NEW}, format='json').status_code, 403)
