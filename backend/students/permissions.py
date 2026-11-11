from rest_framework.permissions import BasePermission, SAFE_METHODS

from .access import TEACHER, get_role

ACTION_BY_METHOD = {'POST': 'add', 'PUT': 'change', 'PATCH': 'change', 'DELETE': 'delete'}


def has_model_permission(user, method, model):
    """Staff writes follow Django model permissions, exactly like Django Admin (audit finding M2)."""
    action = ACTION_BY_METHOD.get(method)
    if not action or not user.is_staff:
        return False
    return user.has_perm(f'{model._meta.app_label}.{action}_{model._meta.model_name}')


def view_model(view):
    return view.get_serializer_class().Meta.model


class StaffWritePermission(BasePermission):
    """Signed-in users read (scoped by role); writes need staff status plus the add/change/delete permission."""

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        return has_model_permission(user, request.method, view_model(view))


class AttendancePermission(BasePermission):
    """Signed-in users read (scoped by role). Staff write with the matching model permission.
    Teachers create/update for their own students only; they never delete.

    Teachers are limited to their own students by the view's queryset (404 for others)
    and by the serializer's student choices (400 for others).
    """

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if request.method in SAFE_METHODS:
            return True
        if user.is_staff:
            return has_model_permission(user, request.method, view_model(view))
        return request.method in ('POST', 'PUT', 'PATCH') and get_role(user) == TEACHER
