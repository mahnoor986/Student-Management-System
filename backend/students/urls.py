from django.urls import path
from .views import AttendanceDetailView, AttendanceListCreateView, DepartmentDetailView, DepartmentListCreateView, StudentDetailView, StudentListCreateView, StudentSummaryView

urlpatterns = [
    path('students/', StudentListCreateView.as_view(), name='student-list-create'),
    path('students/summary/', StudentSummaryView.as_view(), name='student-summary'),
    path('students/<int:pk>/', StudentDetailView.as_view(), name='student-detail'),
    path('departments/', DepartmentListCreateView.as_view(), name='department-list-create'),
    path('departments/<int:pk>/', DepartmentDetailView.as_view(), name='department-detail'),
    path('attendance/', AttendanceListCreateView.as_view(), name='attendance-list-create'),
    path('attendance/<int:pk>/', AttendanceDetailView.as_view(), name='attendance-detail'),
]
