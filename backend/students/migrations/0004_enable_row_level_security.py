"""Enable Row Level Security on every table in the public schema (PostgreSQL only).

Supabase exposes the public schema through its auto-generated REST API, which anyone
holding the project's public anon key can call. With RLS enabled and no policies, that
API can no longer read or write these tables. Django connects as the `postgres` role,
which bypasses RLS, so the app keeps working. On SQLite this migration does nothing.
"""
from django.db import migrations

ENABLE_RLS = """
DO $$
DECLARE t record;
BEGIN
    FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
        EXECUTE format('ALTER TABLE public.%%I ENABLE ROW LEVEL SECURITY', t.tablename);
    END LOOP;
END $$;
"""

DISABLE_RLS = ENABLE_RLS.replace('ENABLE ROW LEVEL SECURITY', 'DISABLE ROW LEVEL SECURITY')


def run_sql(sql):
    def apply(apps, schema_editor):
        if schema_editor.connection.vendor == 'postgresql':
            # %%I is format()'s identifier placeholder, escaped for the DB driver.
            schema_editor.execute(sql, params=())
    return apply


class Migration(migrations.Migration):
    dependencies = [
        ('students', '0003_alter_department_code'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('admin', '0003_logentry_add_action_flag_choices'),
        ('sessions', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [migrations.RunPython(run_sql(ENABLE_RLS), run_sql(DISABLE_RLS))]
