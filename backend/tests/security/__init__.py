"""Security test suite (SECURITY_AUDIT phase 3).

Runs only on Django's throwaway test database. Run from backend/ with Supabase disabled:

    DATABASE_URL= python manage.py test tests.security        (bash)
    $env:DATABASE_URL=' '; python manage.py test tests.security   (PowerShell)

Tests named test_<FINDING>_... prove a finding from the audit (H1, H2, M1, M2, M4, L1-L9).
They are expected to fail until that finding is fixed.
"""
