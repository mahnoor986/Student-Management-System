"""Create the "Viewers" group: the explicit opt-in for read-only access to every student (audit finding H2)."""
from django.db import migrations

VIEWERS_GROUP = 'Viewers'


def create_group(apps, schema_editor):
    apps.get_model('auth', 'Group').objects.get_or_create(name=VIEWERS_GROUP)


def remove_group(apps, schema_editor):
    apps.get_model('auth', 'Group').objects.filter(name=VIEWERS_GROUP).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('students', '0005_roles_and_classes'),
        ('auth', '0012_alter_user_first_name_max_length'),
    ]

    operations = [migrations.RunPython(create_group, remove_group)]
