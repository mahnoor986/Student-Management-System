from django.db.models import Q
from django.db.models.deletion import ProtectedError
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Attendance, Department, Student
from .serializers import AttendanceSerializer, DepartmentSerializer, StudentSerializer
from .permissions import StaffWritePermission


class StudentListCreateView(generics.ListCreateAPIView):
    serializer_class = StudentSerializer
    permission_classes = [StaffWritePermission]

    def get_queryset(self):
        queryset = Student.objects.all()
        search = self.request.query_params.get('search', '').strip()
        course = self.request.query_params.get('course', '').strip()
        department = self.request.query_params.get('department', '').strip()
        status = self.request.query_params.get('status', '').strip()
        if search:
            for term in search.split():
                queryset = queryset.filter(Q(first_name__icontains=term) | Q(last_name__icontains=term) | Q(student_id__icontains=term) | Q(email__icontains=term) | Q(phone__icontains=term) | Q(course__icontains=term))
        if course:
            queryset = queryset.filter(course__iexact=course)
        if department:
            queryset = queryset.filter(department_id=department)
        if status:
            queryset = queryset.filter(status=status)
        return queryset


class StudentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [StaffWritePermission]

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            from rest_framework.exceptions import APIException
            error = APIException('This student has attendance records and cannot be deleted. Keep the record or remove attendance history first.')
            error.status_code = status.HTTP_409_CONFLICT
            raise error


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
            from rest_framework.exceptions import APIException
            error = APIException('This department still has students. Reassign those students before deleting the department.')
            error.status_code = status.HTTP_409_CONFLICT
            raise error


class AttendanceListCreateView(generics.ListCreateAPIView):
    serializer_class = AttendanceSerializer
    permission_classes = [StaffWritePermission]

    def get_queryset(self):
        queryset = Attendance.objects.select_related('student')
        student = self.request.query_params.get('student')
        attendance_date = self.request.query_params.get('date')
        if student:
            queryset = queryset.filter(student_id=student)
        if attendance_date:
            queryset = queryset.filter(date=attendance_date)
        return queryset


class AttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Attendance.objects.select_related('student')
    serializer_class = AttendanceSerializer
    permission_classes = [StaffWritePermission]


class StudentSummaryView(APIView):
    def get(self, request):
        queryset = Student.objects.all()
        counts = {key.lower(): queryset.filter(status=key).count() for key, _ in Student.Status.choices}
        return Response({
            'total_students': queryset.count(),
            'active_students': counts['active'],
            'inactive_students': counts['inactive'],
            'graduated_students': counts['graduated'],
            'total_courses': queryset.values('course').distinct().count(),
            'recent_students': StudentSerializer(queryset.order_by('-created_at', '-id')[:5], many=True, context={'request': request}).data,
        })
