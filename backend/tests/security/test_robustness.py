"""Input handling and response size."""
from .base import SecurityTestCase


class MalformedInputTests(SecurityTestCase):
    def test_L1_malformed_filters_return_400_not_500(self):
        self.client.raise_request_exception = False
        self.login_as(self.u_staff)
        for path in ('/api/attendance/?date=not-a-date', '/api/attendance/?student=abc',
                     '/api/students/?department=abc', '/api/students/?class=abc'):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 400)


class PaginationTests(SecurityTestCase):
    def test_L7_list_endpoints_are_paginated(self):
        self.login_as(self.u_staff)
        for path in ('/api/students/', '/api/attendance/', '/api/classes/', '/api/departments/'):
            with self.subTest(path=path):
                data = self.client.get(path).data
                self.assertIsInstance(data, dict, f'{path} returns an unbounded list')
                self.assertIn('results', data)
