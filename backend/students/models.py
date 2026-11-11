from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone


def validate_single_role(user, allowed_link):
    """A login may hold exactly one role: staff, student, teacher or parent."""
    if user is None:
        return
    if user.is_staff or user.is_superuser:
        raise ValidationError({'user': 'Staff accounts cannot also be a student, teacher or parent. Use a separate login.'})
    links = {
        'student': Student.objects.filter(user=user).exists(),
        'teacher': TeacherProfile.objects.filter(user=user).exists(),
        'parent': ParentProfile.objects.filter(user=user).exists(),
    }
    taken = [role for role, linked in links.items() if linked and role != allowed_link]
    if taken:
        raise ValidationError({'user': f'This login is already linked as a {taken[0]}. Each login can have only one role.'})


class Student(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'Active', 'Active'
        INACTIVE = 'Inactive', 'Inactive'
        GRADUATED = 'Graduated', 'Graduated'

    class Gender(models.TextChoices):
        FEMALE = 'Female', 'Female'
        MALE = 'Male', 'Male'
        NON_BINARY = 'Non-binary', 'Non-binary'
        PREFER_NOT_TO_SAY = 'Prefer not to say', 'Prefer not to say'

    student_id = models.CharField(max_length=24, unique=True, validators=[RegexValidator(r'^[A-Za-z0-9_-]+$', 'Use letters, numbers, hyphens, or underscores.')])
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80)
    email = models.EmailField(max_length=254, unique=True)
    phone = models.CharField(max_length=30, blank=True)
    course = models.CharField(max_length=120)
    date_of_birth = models.DateField(null=True, blank=True)
    enrollment_date = models.DateField(default=timezone.localdate)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    gender = models.CharField(max_length=24, choices=Gender.choices, blank=True)
    address = models.CharField(max_length=500, blank=True)
    department = models.ForeignKey('Department', null=True, blank=True, on_delete=models.PROTECT, related_name='students')
    class_section = models.ForeignKey('ClassSection', null=True, blank=True, on_delete=models.PROTECT, related_name='students', verbose_name='class')
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name='student_record', help_text='Login account for this student. Leave empty if the student does not sign in.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        super().clean()
        validate_single_role(self.user, 'student')

    class Meta:
        ordering = ['last_name', 'first_name', 'id']
        constraints = [
            models.CheckConstraint(condition=~models.Q(first_name=''), name='student_first_name_not_blank'),
            models.CheckConstraint(condition=~models.Q(last_name=''), name='student_last_name_not_blank'),
            models.CheckConstraint(condition=~models.Q(course=''), name='student_course_not_blank'),
        ]

    def __str__(self):
        return f'{self.first_name} {self.last_name} ({self.student_id})'


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True, blank=True, null=True)
    description = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class ClassSection(models.Model):
    """A teaching group such as 'BSCS-2A'. Teachers are assigned to classes; students belong to one."""
    name = models.CharField(max_length=50, unique=True)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.PROTECT, related_name='classes')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'class'
        verbose_name_plural = 'classes'

    def __str__(self):
        return self.name


class TeacherProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='teacher_profile')
    classes = models.ManyToManyField(ClassSection, blank=True, related_name='teachers')

    class Meta:
        ordering = ['user__username']
        verbose_name = 'teacher'

    def clean(self):
        super().clean()
        validate_single_role(getattr(self, 'user', None), 'teacher')

    def __str__(self):
        return self.user.get_full_name() or self.user.get_username()


class ParentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='parent_profile')
    children = models.ManyToManyField(Student, blank=True, related_name='parents')

    class Meta:
        ordering = ['user__username']
        verbose_name = 'parent'

    def clean(self):
        super().clean()
        validate_single_role(getattr(self, 'user', None), 'parent')

    def __str__(self):
        return self.user.get_full_name() or self.user.get_username()


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'Present', 'Present'
        ABSENT = 'Absent', 'Absent'
        LATE = 'Late', 'Late'

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='attendance_records')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', 'student__last_name', 'student__first_name']
        constraints = [models.UniqueConstraint(fields=['student', 'date'], name='unique_student_attendance_per_day')]

    def __str__(self):
        return f'{self.student} - {self.date}: {self.status}'
