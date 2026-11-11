from django.apps import AppConfig
from django.db.models.signals import post_migrate


def enable_row_level_security(using, **kwargs):
    """Keep RLS on for every public table, including ones added by later migrations.

    Supabase exposes the public schema through its REST API (anon key). RLS with no
    policies blocks that API; Django's `postgres` role bypasses RLS. No-op on SQLite.
    """
    from django.db import connections

    connection = connections[using]
    if connection.vendor != 'postgresql':
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND NOT rowsecurity")
        for (table,) in cursor.fetchall():
            cursor.execute(f'ALTER TABLE public.{connection.ops.quote_name(table)} ENABLE ROW LEVEL SECURITY')


class StudentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'students'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in, user_login_failed

        from .login_limits import clear_username, record_failure

        post_migrate.connect(enable_row_level_security, sender=self, dispatch_uid='students.enable_rls')
        user_login_failed.connect(record_failure, dispatch_uid='students.record_login_failure')
        user_logged_in.connect(clear_username, dispatch_uid='students.clear_login_failures')
