# Student Management System

CampusFlow is a local student-management app with a responsive HTML/CSS/vanilla-JavaScript frontend and a Django REST Framework backend. Phase 3 adds Django session authentication, CSRF protection, and role-based API permissions. Student data remains in the existing SQLite database.

## Files

- `index.html`, `style.css`, `script.js` — existing dashboard and student-management interface, now protected by a Django session.
- `login.html`, `login.js` — sign-in page and CSRF-protected login request.
- `backend/config/` — Django settings and top-level routes.
- `backend/students/` — student model/API, auth endpoints, permissions, admin setup, and tests.
- `backend/db.sqlite3` — local development database (ignored by Git; do not delete to reset anything).

## Roles and access

- **Staff/admin accounts** can view the dashboard and student records and create, edit, or delete records. Create the first administrator with Django's `createsuperuser` command. Staff can add regular users through Django Admin.
- **Regular signed-in users** can view the dashboard and student records, but cannot mutate records.
- **Anonymous visitors** are sent to `login.html`; all student and dashboard API endpoints also require authentication. Backend permissions enforce these rules even if someone edits the frontend.
- There is no public registration page. Django Admin remains protected by Django's built-in staff and permission checks.

Session cookies are HttpOnly; the frontend does not store passwords, session IDs, or tokens in localStorage/sessionStorage. Login and logout use CSRF tokens, and authenticated unsafe API requests use Django REST Framework's session authentication and CSRF checks. CORS and trusted CSRF origins are limited to local ports 5500 on `127.0.0.1` and `localhost`. The API is intended for local development and is not production-ready.

Login attempts are throttled to 10 per minute per client address using Django REST Framework's local cache. Configure a shared production cache and stronger monitoring/lockout policy before deployment.

## Windows setup (PowerShell)

Open PowerShell in the project folder and check Python:

```powershell
py --version
cd .\backend
```

Create a virtual environment if one does not already exist, activate it, and install requirements:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, use the environment's interpreter directly from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Apply migrations and create an administrator account when needed:

```powershell
python manage.py migrate
python manage.py createsuperuser
```

The initial database migration is already included. Do not delete `db.sqlite3`; migrations preserve existing student records. Start Django in this terminal:

```powershell
python manage.py runserver --insecure
```

`runserver --insecure` is only for local development static files when `DEBUG=False`; it lets Django serve its built-in admin assets without turning debug mode on. `STATIC_URL` is `/static/` and `STATIC_ROOT` is `backend/staticfiles`. For deployment, use `collectstatic` and a dedicated static-file server instead. `runserver` is for development only. Django hides password characters during `createsuperuser`; type the password and press Enter, then confirm it at the next prompt.

Open a second PowerShell window at the project root and serve the frontend:

```powershell
cd C:\Users\mahnoor\Desktop\SMS
py -m http.server 5500 --bind 127.0.0.1
```

Open <http://127.0.0.1:5500/>. The dashboard redirects signed-out visitors to the sign-in page. Use the username/password created with `createsuperuser`. The API hostname follows the frontend hostname, so `localhost:5500` pairs with `localhost:8000`, while `127.0.0.1:5500` pairs with `127.0.0.1:8000`.

## Admin and API

Open <http://127.0.0.1:8000/admin/> and sign in with a staff account to create regular accounts and manage students.

- `GET /api/auth/csrf/` — obtain a CSRF token for the browser session.
- `POST /api/auth/login/` — sign in with username and password.
- `GET /api/auth/me/` — retrieve the signed-in user's name and staff role.
- `POST /api/auth/logout/` — end the current session.
- `/api/students/` and `/api/students/<id>/` — student list/search/filter and detail CRUD. All requests require a signed-in user; writes require staff.
- `GET /api/students/summary/` — dashboard statistics; signed-in users only.

The auth endpoints handle JSON and session cookies. To inspect protected API responses manually, sign in first or use the dashboard. The browsable API may show an HTML page in a browser; append `?format=json` to request JSON representation.

## Tests and checks

From `backend/` with the virtual environment active:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
```

## Troubleshooting

- **`python` or `py` is not recognized:** install Python for Windows with the Python Launcher, or use `..venv\Scripts\python.exe` from `backend/` if the environment already exists.
- **Sign-in says Django is unreachable:** keep `runserver` running, serve the frontend over HTTP on port 5500, and use the same hostname for both URLs (`127.0.0.1` or `localhost`). Do not open the HTML file directly.
- **CSRF or CORS error:** use the configured local frontend origin and reload the sign-in page so it obtains a fresh CSRF token. Check `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` in `backend/config/settings.py` if you change ports.
- **Regular account receives 403 on a write:** this is expected; only a staff account can change student records.
- **Django Admin redirects to login:** sign in with a staff account. A regular user cannot access the admin site. If the Admin page appears unstyled locally, restart Django with `python manage.py runserver --insecure`; the project keeps `DEBUG=False` by default.

Use a stable `DJANGO_SECRET_KEY`, HTTPS, secure cookie settings, appropriate hosts, authentication hardening, and a production server before any public deployment. The development server and current local security settings are not production-ready.

## Phase 4: Profiles, departments, and attendance

- Student profiles reuse the existing unique student ID, names, email, phone, date of birth, course, enrollment date, and status. Optional gender and address fields are available; address is omitted from API responses to regular read-only accounts.
- Departments can be created, edited, listed, and removed by staff. All signed-in users can view them. Existing student rows keep a nullable department so the migration preserves current records. Department deletion is blocked with HTTP 409 while students are assigned; reassign students first.
- Staff can record and update attendance (Present, Absent, Late). Signed-in users can view records and filter by date. The database enforces one attendance row per student per date. Student deletion is blocked while attendance history exists to avoid silently removing it.
- New API routes: `/api/departments/`, `/api/departments/<id>/`, `/api/attendance/`, and `/api/attendance/<id>/`. All require a signed-in session; unsafe writes require a staff account and CSRF protection.
- Migration `0002` adds optional profile fields, departments, and attendance without deleting existing student records. Migration `0003` permits multiple departments to omit a code.

Apply new migrations after updating:

```powershell
cd C:\Users\mahnoor\Desktop\SMS\backend
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py test
```

## Add fictional sample students

From the `backend` folder, run:

```powershell
.\.venv\Scripts\python.exe manage.py seed_students
```

The command creates up to 15 fictional students and four sample departments. It uses reserved `example.test` email addresses and fictional `555-01xx` phone numbers. It validates records before saving, skips any record whose sample student ID or email already exists, and never overwrites or deletes records. Run it again safely to fill in only missing sample entries. Dashboard counts update from the database.
