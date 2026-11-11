"""Central access rules: which role a login has and which records it may see or change.

Every view and serializer goes through these helpers so the rules live in one place.
Querysets are scoped here, at the database level, so records outside a user's scope
are never fetched (and detail views return 404 for them).
"""
from .models import Attendance, ClassSection, ParentProfile, Student, TeacherProfile

STAFF = 'staff'
TEACHER = 'teacher'
PARENT = 'parent'
STUDENT = 'student'
VIEWER = 'viewer'  # signed-in, not staff, not linked to any record: read-only access to everything


def get_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_staff:
        return STAFF
    if TeacherProfile.objects.filter(user=user).exists():
        return TEACHER
    if ParentProfile.objects.filter(user=user).exists():
        return PARENT
    if Student.objects.filter(user=user).exists():
        return STUDENT
    return VIEWER


def visible_students(user):
    role = get_role(user)
    if role in (STAFF, VIEWER):
        return Student.objects.all()
    if role == TEACHER:
        return Student.objects.filter(class_section__teachers__user=user).distinct()
    if role == PARENT:
        return Student.objects.filter(parents__user=user).distinct()
    if role == STUDENT:
        return Student.objects.filter(user=user)
    return Student.objects.none()


def visible_attendance(user):
    queryset = Attendance.objects.select_related('student')
    if get_role(user) in (STAFF, VIEWER):
        return queryset
    return queryset.filter(student__in=visible_students(user))


def visible_classes(user):
    role = get_role(user)
    if role in (STAFF, VIEWER):
        return ClassSection.objects.all()
    if role == TEACHER:
        return ClassSection.objects.filter(teachers__user=user)
    return ClassSection.objects.filter(students__in=visible_students(user)).distinct()


def can_record_attendance(user):
    """Staff record attendance for anyone; teachers only for students in their classes."""
    return get_role(user) in (STAFF, TEACHER)


def can_view_private_details(user, student):
    """Address is private: staff, the student themself and their parents may see it."""
    role = get_role(user)
    if role == STAFF:
        return True
    if role == STUDENT:
        return student.user_id == user.pk
    if role == PARENT:
        return student.parents.filter(user=user).exists()
    return False
