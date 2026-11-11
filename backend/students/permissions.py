from rest_framework.permissions import BasePermission, SAFE_METHODS

from .access import can_record_attendance


class StaffWritePermission(BasePermission):
    """All users must be signed in; only staff can mutate records."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (request.method in SAFE_METHODS or user.is_staff))


class AttendancePermission(BasePermission):
    """Signed-in users read (scoped by role); staff and teachers create/update; only staff delete.

    Teachers are limited to their own students by the view's queryset (404 for others)
    and by the serializer's student choices (400 for others).
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.method == 'DELETE':
            return user.is_staff
        return can_record_attendance(user)
