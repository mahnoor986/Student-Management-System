import secrets

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from students.models import ClassSection, Department, ParentProfile, Student, TeacherProfile

User = get_user_model()

# Two of each role so cross-access (A vs B) can be tried in the browser and in tests.
CLASSES = (
    ('DEMO-CS-1A', 'DEMO-CS', ('DEMO-2026-001', 'DEMO-2026-002', 'DEMO-2026-013', 'DEMO-2026-015')),
    ('DEMO-BUS-1A', 'DEMO-BUS', ('DEMO-2026-005', 'DEMO-2026-006', 'DEMO-2026-007', 'DEMO-2026-014')),
)
TEACHERS = (('demo.teacher.a', 'Teacher', 'A', 'DEMO-CS-1A'), ('demo.teacher.b', 'Teacher', 'B', 'DEMO-BUS-1A'))
STUDENTS = (('demo.student.a', 'DEMO-2026-001'), ('demo.student.b', 'DEMO-2026-005'))
PARENTS = (('demo.parent.a', 'Parent', 'A', 'DEMO-2026-001'), ('demo.parent.b', 'Parent', 'B', 'DEMO-2026-005'))


class Command(BaseCommand):
    help = 'Create fictional demo classes and teacher/student/parent logins. Existing accounts are not changed.'

    def add_arguments(self, parser):
        parser.add_argument('--password', help='Password for newly created demo accounts. A random one is generated if omitted.')

    @transaction.atomic
    def handle(self, *args, **options):
        password = options['password'] or f'Demo-{secrets.token_urlsafe(9)}'
        call_command('seed_students', stdout=self.stdout)
        created, kept = [], []

        def account(username, first='', last=''):
            user, is_new = User.objects.get_or_create(username=username, defaults={'first_name': first, 'last_name': last})
            if is_new:
                user.set_password(password)
                user.save(update_fields=['password'])
                created.append(username)
            else:
                if user.is_staff or user.is_superuser:
                    raise CommandError(f'{username} exists and is a staff account; refusing to give it a demo role.')
                kept.append(username)
            return user

        def student(student_id):
            try:
                return Student.objects.get(student_id=student_id)
            except Student.DoesNotExist:
                raise CommandError(f'Sample student {student_id} is missing. Run seed_students first.')

        for name, dept_code, student_ids in CLASSES:
            class_section, _ = ClassSection.objects.get_or_create(name=name, defaults={'department': Department.objects.filter(code=dept_code).first()})
            Student.objects.filter(student_id__in=student_ids, class_section__isnull=True).update(class_section=class_section)

        for username, first, last, class_name in TEACHERS:
            profile, _ = TeacherProfile.objects.get_or_create(user=account(username, first, last))
            profile.classes.add(ClassSection.objects.get(name=class_name))

        for username, student_id in STUDENTS:
            record = student(student_id)
            user = account(username, record.first_name, record.last_name)
            if record.user_id is None:
                record.user = user
                record.save(update_fields=['user'])

        for username, first, last, child_id in PARENTS:
            profile, _ = ParentProfile.objects.get_or_create(user=account(username, first, last))
            profile.children.add(student(child_id))

        if created:
            self.stdout.write(self.style.SUCCESS(f'Created {len(created)} demo login(s): {", ".join(created)}'))
            self.stdout.write(f'Password for the new accounts: {password}')
        if kept:
            self.stdout.write(f'Already present, password unchanged: {", ".join(kept)}')
