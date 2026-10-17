from rest_framework.permissions import BasePermission, SAFE_METHODS


class StaffWritePermission(BasePermission):
    """All users must be signed in; only staff can mutate student records."""

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (request.method in SAFE_METHODS or user.is_staff))
