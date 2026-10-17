import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = []
    operations = [
        migrations.CreateModel(
            name='Student',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('student_id', models.CharField(max_length=24, unique=True, validators=[django.core.validators.RegexValidator(r'^[A-Za-z0-9_-]+$', 'Use letters, numbers, hyphens, or underscores.')])) ,
                ('first_name', models.CharField(max_length=80)),
                ('last_name', models.CharField(max_length=80)),
                ('email', models.EmailField(max_length=254, unique=True)),
                ('phone', models.CharField(blank=True, max_length=30)),
                ('course', models.CharField(max_length=120)),
                ('date_of_birth', models.DateField(blank=True, null=True)),
                ('enrollment_date', models.DateField(default=django.utils.timezone.localdate)),
                ('status', models.CharField(choices=[('Active', 'Active'), ('Inactive', 'Inactive'), ('Graduated', 'Graduated')], default='Active', max_length=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['last_name', 'first_name', 'id']},
        ),
        migrations.AddConstraint(model_name='student', constraint=models.CheckConstraint(condition=models.Q(('first_name', ''), _negated=True), name='student_first_name_not_blank')),
        migrations.AddConstraint(model_name='student', constraint=models.CheckConstraint(condition=models.Q(('last_name', ''), _negated=True), name='student_last_name_not_blank')),
        migrations.AddConstraint(model_name='student', constraint=models.CheckConstraint(condition=models.Q(('course', ''), _negated=True), name='student_course_not_blank')),
    ]
