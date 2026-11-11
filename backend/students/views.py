from datetime import date

from django.db.models import Q
from django.db.models.deletion import ProtectedError
from rest_framework import generics, status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from .access import visible_attendance, visible_classes, visible_students
from .models import Department, Student
from .serializers import AttendanceSerializer, ClassSectionSerializer, DepartmentSerializer, StudentSerializer
from .permissions import AttendancePermission, StaffWritePermission


def conflict(message):
    error = APIException(message)
    error.status_code = status.HTTP_409_CONFLICT
    return error


def id_param(request, name):
    """Optional positive-integer query parameter; a malformed value is a 400, not a 500 (audit L1)."""
    value = request.query_params.get(name, '').strip()
    if not value:
        return None
    if not value.isdigit():
        raise ValidationError({name: 'Must be a whole number.'})
    return int(value)


def date_param(request, name):
    value = request.query_params.get(name, '').strip()
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({name: 'Use the format YYYY-MM-DD.'})


class StudentListCreateView(generics.ListCreateAPIView):
    serializer_class = StudentSerializer
    permission_classes = [StaffWritePermission]

    def get_queryset(self):
        queryset = visible_students(self.request.user).select_related('department', 'class_section')
        search = self.request.query_params.get('search', '').strip()
        course = self.request.query_params.get('course', '').strip()
        department = id_param(self.request, 'department')
        class_section = id_param(self.request, 'class')
        status = self.request.query_params.get('status', '').strip()
        if search:
            for term in search.split():
                queryset = queryset.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term) | Q(student_id__icontains=term) | Q(email__icontains=term) | Q(phone__icontains=term) | Q(course__icontains=term))
        if course:
            queryset = queryset.filter(course__iexact=course)
        if department is not None:
            queryset = queryset.filter(department_id=department)
        if class_section is not None:
            queryset = queryset.filter(class_section_id=class_section)
        if status:
            queryset = queryset.filter(status=status)
        return queryset


class StudentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = StudentSerializer
    permission_classes = [StaffWritePermission]

    def get_queryset(self):
        return visible_students(self.request.user).select_related('department', 'class_section')

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise conflict('This student has attendance records and cannot be deleted. Keep the record or remove attendance history first.')


class DepartmentListCreateView(generics.ListCreateAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [StaffWritePermission]


class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [StaffWritePermission]

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise conflict('This department still has students or classes. Reassign them before deleting the department.')


class ClassSectionListCreateView(generics.ListCreateAPIView):
    serializer_class = ClassSectionSerializer
    permission_classes = [StaffWritePermission]

    def get_queryset(self):
        return visible_classes(self.request.user).select_related('department')


class ClassSectionDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ClassSectionSerializer
    permission_classes = [StaffWritePermission]

    def get_queryset(self):
        return visible_classes(self.request.user).select_related('department')

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise conflict('This class still has students. Move them to another class before deleting it.')


class AttendanceListCreateView(generics.ListCreateAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [AttendancePermission]

    def get_queryset(self):
        queryset = visible_attendance(self.request.user)
        student = id_param(self.request, 'student')
        attendance_date = date_param(self.request, 'date')
        if student is not None:
            queryset = queryset.filter(student_id=student)
        if attendance_date is not None:
            queryset = queryset.filter(date=attendance_date)
        return queryset


class AttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [AttendancePermission]

    def get_queryset(self):
        return visible_attendance(self.request.user)


class StudentSummaryView(APIView):
    def get(self, request):
        queryset = visible_students(request.user)
        counts = {key.lower(): queryset.filter(status=key).count() for key, _ in Student.Status.choices}
        return Response({
            'total_students': queryset.count(),
            'active_students': counts['active'],
            'inactive_students': counts['inactive'],
            'graduated_students': counts['graduated'],
            'total_courses': queryset.values('course').distinct().count(),
            'recent_students': StudentSerializer(queryset.order_by('-created_at', '-id')[:5], many=True, context={'request': request}).data,
        })
