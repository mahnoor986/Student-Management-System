# Security Audit: CampusFlow Student Management System

**Branch:** `security-audit` · **Audit dates:** 11–12 November 2026 · **Status:** all approved findings fixed

## Summary

The audit covered authentication and authorization for the Django REST API, Django Admin, and the static HTML/JS frontend, using Supabase PostgreSQL as the database.

- **16 findings:** 2 High, 4 Medium, 10 Low, none Critical.
- **14 fixed,** each in its own commit.
- **2 accepted:**
  - M3, the database role: the owner decided not to change it.
  - L10, demo-only behaviour.
- **Security suite:** 287 automated tests in `backend/tests/security/` prove each finding and guard the fixes.

| | Before fixes | After fixes |
|---|---|---|
| Full test run (security + functional) | 328 tests, **31 failing** (each one a finding) | 336 tests, **0 failing** |
| Security suite only | 285 tests, 254 pass, 31 fail | 287 tests, all pass |

Between the two runs:
- 5 password-change tests and 1 no-role test were added to the functional suite.
- Two security tests were added: a check that superusers can still grant privileges, and a browsable-API test split into two (off by default; escaped when on).

## Scope and method

- **Stack:**
  - Django 5.2 + Django REST Framework 3.18, with server-side database sessions and CSRF.
  - Supabase PostgreSQL, with RLS enabled on every `public` table.
  - Static HTML/JS frontend.
- **Roles:**
  - Staff and superuser.
  - Teacher (linked to classes), student (linked to their own record) and parent (linked to their children).
  - Viewer (opt-in read-only group).
  - Signed-in user with no role.
- **Tenancy:** single school, so no tenant checks apply.
- **Not present, so not applicable:** JWT, OAuth, password reset, file uploads, webhooks, marks, fees, timetable, reports.
- **Phases:**
  1. Route inventory and permission matrix.
  2. Static audit with file:line evidence.
  3. Automated tests proving each finding.
  4. Fixes, one commit each, with the full suite re-run after every fix.
- **Data safety:** all tests ran on Django's throwaway in-memory SQLite database (`DATABASE_URL` blanked), never on Supabase. The only changes made to Supabase were the ones the owner approved:
  - migrations 0005 and 0006,
  - six fictional demo accounts,
  - adding the `mahnoor` login to the Viewers group.

## Findings and status

| # | Severity | Finding | Fix | Status | Commit |
|---|---|---|---|---|---|
| H1 | High | The frontend file server served the whole repo, including `backend/.env` (DB password and `SECRET_KEY`), `.git/` and local databases. Reachable via DNS rebinding | Frontend moved to `frontend/`; only that folder is served | **Fixed** | `43bf6c7` |
| H2 | High | A login with no linked record could read every student. This included former students, removed teachers and brand-new accounts | Deny by default; read-all only through the opt-in **Viewers** group | **Fixed** | `a68c6e6`, `e6beba1` |
| M1 | Medium | Admin login had no rate limit or lockout | Lockout after 10 failures in 15 min, per username and per IP (429). MFA not added (owner decision) | **Fixed** | `217b9e9` |
| M2 | Medium | Every staff user could write anything through the API, ignoring Django model permissions | API writes require the add/change/delete model permission | **Fixed** | `d42e77d` |
| M3 | Medium | The app connects to Supabase as the `postgres` owner role, which bypasses RLS | Proposed: a dedicated least-privilege database role | **Accepted risk** (owner decision) | — |
| M4 | Medium | Users could not change their own password | `POST /api/auth/password/`, plus a dashboard dialog | **Fixed** | `0f4ce27` |
| L1 | Low | Malformed `?date`, `?student`, `?department` and `?class` values caused a 500 error | Validated; bad values return 400 | **Fixed** | `ae08b18` |
| L2 | Low | Sessions lasted 2 weeks; cookies not `Secure` | 8-hour sessions; `DJANGO_SECURE_COOKIES=true` for HTTPS | **Fixed** (turn on `Secure` when deploying) | `30245a3` |
| L3 | Low | Passwords hashed with PBKDF2, not Argon2id | Argon2id is the default; old hashes upgrade on next login | **Fixed** | `ffa16f0` |
| L4 | Low | API login was throttled per IP only | Per-account lockout added | **Fixed** | `da67bd1` |
| L5 | Low | The "one role per login" rule was enforced only in admin forms | Enforced on every save | **Fixed** | `6146789` |
| L6 | Low | No Content-Security-Policy on the frontend | Strict CSP meta tag on both pages | **Fixed** | `ea896f6` |
| L7 | Low | List endpoints were unbounded | Pagination at 100 per page; the dashboard follows `next` links | **Fixed** | `8822f21` |
| L8 | Low | Staff with `auth.change_user` could make themselves superuser | Privilege fields are read-only for non-superusers | **Fixed** | `6fe41f7` |
| L9 | Low | Organisation-wide student counts visible to every role; browsable API always on | Counts limited to staff (departments) and staff/teachers (classes); browsable API only when `DEBUG` | **Fixed** | `c2554e0` |
| L10 | Low | `seed_demo_accounts` prints the demo password to the terminal | By design for demo data; never run it on real data | **Accepted risk** | — |

### Checks that passed with no change needed
- Every private API route is protected on the server (401 when signed out).
- Session fixation: the session ID changes on login.
- Logout deletes the session on the server.
- CSRF is enforced on every write; no GET request changes data.
- CORS allows exact origins only, not a wildcard.
- No tokens are kept in browser storage.
- Login gives the same error for a wrong username or a wrong password.
- `user`, `id` and `is_staff` can't be set through request bodies (mass assignment).
- Output escaping in `script.js` is correct.
- `X-Frame-Options`, `nosniff`, `Referrer-Policy` and COOP headers are set.
- Error responses don't leak stack traces.
- No secrets in Git history.
- `pip-audit`: no known vulnerabilities, before and after the fixes.

## Decisions made by the owner
1. **Staff API access** follows Django model permissions, the same rules as Django Admin (M2).
2. **Read-only access to all students** comes from the explicit **Viewers** group (option B). Logins with no role see nothing (H2).
3. **Teachers** may see students' email and phone; addresses are shown only to staff, the student themself and their parents.
4. **M1:** rate-limit the admin login now; no MFA for now.
5. **M3:** no separate database role (accepted risk).

## Remaining risks
- **M3, database owner role:** if the database password leaks or SQL injection is ever possible, the attacker gets full database control, including Supabase's `auth` and `storage` schemas. Revisit before storing real student data.
- **No MFA** for staff or superuser accounts.
- **Lockout counters live in per-process memory** (Django's default cache). They reset when the server restarts and aren't shared between workers. Configure a shared cache (Redis or the database cache) before running more than one worker.
- **The lockout can be abused for denial of service:** anyone can lock a known username for 15 minutes by entering wrong passwords on purpose. This is the usual trade-off of lockouts; watch for it.
- **HTTPS isn't set up:**
  - turn on `DJANGO_SECURE_COOKIES=true` once the site is served over HTTPS;
  - add HSTS at the hosting layer;
  - `frame-ancestors` can't be set from a meta tag, so send it as a header from the web server.
- **The demo accounts in Supabase** (`demo.*`, one shared password) and **the `admin` password** chosen during setup are known credentials. Delete the demo accounts and change the admin password before real data goes in.
- **Incident during the audit:** the Supabase database password was briefly printed in a tool log during a backup. It was reset the same day, and `.env` now holds the new password, URL-encoded.

## What to test by hand in the browser
1. **Changing IDs:** sign in as `demo.student.a`. In DevTools, open `http://127.0.0.1:8000/api/students/5/` (student B) → expect **404**. Repeat with `/api/attendance/<id>/` and `/api/classes/<id>/`.
2. **Replaying a request:** as `demo.teacher.a`, save attendance. Use "Copy as fetch" in DevTools and change `student` to a student from class B → expect **400**. Change the method to `DELETE` → expect **403**.
3. **Logout replay:** copy the `sessionid` cookie, log out, set the cookie back → `/api/auth/me/` should give **401**.
4. **CSRF:** replay a POST without the `X-CSRFToken` header → expect **403**.
5. **Lockout:** enter 11 wrong passwords at `/admin/login/` → the 11th should give **429**. It clears after 15 minutes.
6. **No role:** in Django Admin, create a new login without linking it → after signing in, the dashboard should show 0 students and "No access yet".
7. **CSP:** open the dashboard with DevTools → Console open. Fonts and data should load, with no CSP violations.
8. **Password change:** use "Change password" in the top bar → other signed-in browsers for that user are signed out.
9. **Secrets:** opening `http://127.0.0.1:5500/backend/.env` should give **404**.

## Running the security tests

From `backend/`, with Supabase switched off for the run:

```bash
DATABASE_URL= python manage.py test                      # everything (bash)
DATABASE_URL= python manage.py test tests.security       # security suite only
```

```powershell
$env:DATABASE_URL=' '; .\.venv\Scripts\python.exe manage.py test
```

Tests named `test_<FINDING>_…` (for example `test_H2_…`) prove one specific finding. The permission-matrix tests are generated one per cell, named `test_<action>__<role>`. Add `--parallel 4` to speed up the run; it needs the `tblib` package (dev only).

## Commits on `security-audit`

| Commit | Change |
|---|---|
| `f5a5b44` | Supabase PostgreSQL via `DATABASE_URL` |
| `0f1274b` | Row Level Security on all public tables |
| `f268505` | Student, teacher and parent logins; role-scoped access |
| `b6d9a86` | Security test suite (phase 3) |
| `43bf6c7` … `c2554e0` | One commit per fix: H1, H2, M2, M1, M4, L1–L9 |

The branch is **not merged and not pushed**. To bring it into `master`, review and merge it (for example through a pull request).
