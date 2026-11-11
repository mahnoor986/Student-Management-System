from django.contrib import admin
from .models import Attendance, ClassSection, Department, ParentProfile, Student, TeacherProfile


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'first_name', 'last_name', 'email', 'course', 'class_section', 'status', 'user')
    list_filter = ('status', 'class_section', 'course', 'enrollment_date')
    search_fields = ('student_id', 'first_name', 'last_name', 'email')
    ordering = ('last_name', 'first_name')
    autocomplete_fields = ('user', 'class_section')


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(ClassSection)
class ClassSectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'department')
    list_filter = ('department',)
    search_fields = ('name',)


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user',)
    filter_horizontal = ('classes',)


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'user')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    autocomplete_fields = ('user', 'children')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'status')
    list_filter = ('date', 'status')
    search_fields = ('student__student_id', 'student__first_name', 'student__last_name')
