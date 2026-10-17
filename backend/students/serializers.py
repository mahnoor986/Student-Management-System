from rest_framework import serializers
from .models import Attendance, Department, Student


class DepartmentSerializer(serializers.ModelSerializer):
    student_count = serializers.IntegerField(source='students.count', read_only=True)
    class Meta:
        model = Department
        fields = ['id', 'name', 'code', 'description', 'student_count', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Department name is required.')
        matches = Department.objects.filter(name__iexact=value)
        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise serializers.ValidationError('A department with this name already exists.')
        return value

    def validate_code(self, value):
        value = value.strip().upper()
        if not value:
            return None
        matches = Department.objects.filter(code__iexact=value)
        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise serializers.ValidationError('A department with this code already exists.')
        return value


class StudentSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)

    class Meta:
        model = Student
        fields = ['id', 'student_id', 'first_name', 'last_name', 'name', 'email', 'phone', 'course', 'date_of_birth', 'enrollment_date', 'status', 'gender', 'address', 'department', 'department_name', 'created_at', 'updated_at']
        read_only_fields = ['id', 'name', 'created_at', 'updated_at']

    def get_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'

    def get_fields(self):
        fields = super().get_fields()
        request = self.context.get('request')
        if request and not request.user.is_staff:
            fields.pop('address', None)
        return fields

    def validate_student_id(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Student ID is required.')
        matches = Student.objects.filter(student_id__iexact=value)
        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise serializers.ValidationError('A student with this ID already exists.')
        return value

    def validate_first_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('First name is required.')
        return value

    def validate_last_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Last name is required.')
        return value

    def validate_course(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError('Course is required.')
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        matches = Student.objects.filter(email__iexact=value)
        if self.instance:
            matches = matches.exclude(pk=self.instance.pk)
        if matches.exists():
            raise serializers.ValidationError('A student with this email already exists.')
        return value

    def validate_address(self, value):
        return value.strip()


class AttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.first_name', read_only=True)
    student_full_name = serializers.SerializerMethodField()
    student_id = serializers.CharField(source='student.student_id', read_only=True)

    class Meta:
        model = Attendance
        fields = ['id', 'student', 'student_name', 'student_full_name', 'student_id', 'date', 'status', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_student_full_name(self, obj):
        return f'{obj.student.first_name} {obj.student.last_name}'
