from django.contrib import admin
from .models import Attendance, Department, Student


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'first_name', 'last_name', 'email', 'course', 'status', 'enrollment_date')
    list_filter = ('status', 'course', 'enrollment_date')
    search_fields = ('student_id', 'first_name', 'last_name', 'email')
    ordering = ('last_name', 'first_name')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'status')
    list_filter = ('date', 'status')
    search_fields = ('student__student_id', 'student__first_name', 'student__last_name')
