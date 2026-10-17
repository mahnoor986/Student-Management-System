from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q

from students.models import Department, Student


class Command(BaseCommand):
    help = 'Add fictional sample students without changing existing records.'

    DEPARTMENTS = (
        ('Computing Studies', 'DEMO-CS'),
        ('Business Studies', 'DEMO-BUS'),
        ('Applied Sciences', 'DEMO-SCI'),
        ('Creative Arts', 'DEMO-ART'),
    )

    STUDENTS = (
        ('Avery', 'Sample', 'Computer Science', 'Active', 'Female', date(2024, 9, 2), 1),
        ('Jordan', 'Example', 'Software Engineering', 'Active', 'Male', date(2024, 9, 2), 1),
        ('Casey', 'Fiction', 'Data Science', 'Active', 'Non-binary', date(2025, 1, 13), 1),
        ('Riley', 'Demo', 'Computer Science', 'Inactive', '', date(2023, 9, 4), 1),
        ('Morgan', 'Sample', 'Business Administration', 'Active', 'Prefer not to say', date(2025, 9, 1), 2),
        ('Taylor', 'Example', 'Business Administration', 'Active', 'Female', date(2024, 1, 15), 2),
        ('Quinn', 'Fiction', 'Business Administration', 'Graduated', 'Male', date(2022, 9, 5), 2),
        ('Reese', 'Demo', 'Psychology', 'Active', 'Female', date(2025, 9, 1), 3),
        ('Skyler', 'Sample', 'Data Science', 'Active', 'Prefer not to say', date(2026, 1, 12), 3),
        ('Rowan', 'Example', 'Psychology', 'Inactive', 'Non-binary', date(2023, 1, 16), 3),
        ('Emerson', 'Fiction', 'Graphic Design', 'Active', 'Female', date(2024, 9, 2), 4),
        ('Finley', 'Demo', 'Graphic Design', 'Graduated', 'Male', date(2022, 1, 17), 4),
        ('Dakota', 'Sample', 'Software Engineering', 'Active', '', date(2026, 9, 7), 1),
        ('Alex', 'Example', 'Business Administration', 'Inactive', 'Prefer not to say', date(2024, 1, 15), 2),
        ('Sage', 'Fiction', 'Computer Science', 'Active', 'Non-binary', date(2025, 9, 1), 1),
    )

    def handle(self, *args, **options):
        departments = self._get_departments()
        created = 0
        skipped = 0

        for index, record in enumerate(self.STUDENTS, start=1):
            first_name, last_name, course, status, gender, enrollment_date, department_index = record
            student_id = f'DEMO-2026-{index:03d}'
            email = f'student{index:02d}@example.test'
            existing = Student.objects.filter(
                Q(student_id__iexact=student_id) | Q(email__iexact=email)
            ).first()
            if existing:
                skipped += 1
                continue

            student = Student(
                student_id=student_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=f'+1-202-555-01{index:02d}',
                course=course,
                date_of_birth=date(2003 + (index % 4), (index % 12) + 1, (index % 27) + 1),
                enrollment_date=enrollment_date,
                status=status,
                gender=gender,
                department=departments[department_index - 1],
            )
            try:
                student.full_clean()
                with transaction.atomic():
                    student.save(force_insert=True)
            except (ValidationError, IntegrityError) as exc:
                raise CommandError(f'Could not create sample record {student_id}: {exc}') from exc
            created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Sample students complete: {created} created, {skipped} already present. '
            f'Total students in database: {Student.objects.count()}.'
        ))

    def _get_departments(self):
        departments = []
        for name, code in self.DEPARTMENTS:
            department = Department.objects.filter(name__iexact=name).first()
            if department is None:
                code_in_use = Department.objects.filter(code__iexact=code).exists()
                department = Department(name=name, code=None if code_in_use else code)
                department.full_clean()
                department.save(force_insert=True)
            departments.append(department)
        return departments
