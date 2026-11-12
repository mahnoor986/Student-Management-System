"""Login backend: like Django's default, but an Inactive student cannot sign in.

Owner decision (Nov 2026): a student whose record is marked Inactive loses dashboard and
Django Admin access. Graduated students keep their login. Teachers and parents keep seeing
the student whatever the status. Setting the student back to Active restores the login.

Django calls user_can_authenticate() both at login and on every request for an existing
session (get_user), so an Inactive student who is already signed in is signed out on their
next request.
"""
from django.contrib.auth.backends import ModelBackend


class StudentStatusBackend(ModelBackend):
    def user_can_authenticate(self, user):
        if not super().user_can_authenticate(user):
            return False
        from .models import Student
        return not Student.objects.filter(user=user, status=Student.Status.INACTIVE).exists()
