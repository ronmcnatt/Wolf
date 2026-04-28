# Wolf — Backflow Testing Enterprise Platform

## Business Context
Wolf is an enterprise SaaS platform for commercial backflow testing companies. The business model is acquisition-led: buy existing backflow testing companies and migrate their operations onto this platform. The platform handles technician scheduling, job management, field test data capture, and compliance reporting.

## Stack
- **Language**: Python 3.11
- **Framework**: Django 5.2
- **Database**: SQLite (local dev) / Supabase PostgreSQL (production)
- **Static files**: WhiteNoise
- **Server**: Gunicorn
- **Deployment**: Render (render.yaml configured)

## Project Location
`/Users/ronaldmcnatt/Documents/Wolf/`

## App Structure
```
wolf_backflow/     # Django project config (settings, root URLs)
public/            # Marketing site — home, services, coverage, contact
technician/        # All internal portal views — login, technician, operations, manager
static/            # CSS and images (compiled to staticfiles/ on build)
branding/          # Logo SVGs and branding assets
```

## Running Locally
```bash
cd /Users/ronaldmcnatt/Documents/Wolf
conda activate wolf_backflow
python manage.py runserver
```
- Public website:  https://wolf-9bbc.onrender.com/
- Internal portal login: http://localhost:8000/tech/login/
- Tech dashboard: http://localhost:8000/tech/dashboard/
- Ops dashboard: http://localhost:8000/tech/ops/
- Admin dashboard: http://localhost:8000/tech/admin/users/
- Customer portal: http://localhost:8000/tech/customer/

## POC Users

| Role       | Username     | Password   | Lands On                               |
|------------|--------------|------------|----------------------------------------|
| Technician | `technician` | `tech123`  | Daily schedule (today's assigned jobs) |
| Operations | `operations` | `ops123`   | Job management dashboard               |
| Manager    | `manager`    | `mgr123`   | Job management dashboard               |
| Admin      | `admin`      | `admin123` | User management (all users + roles)    |
| Customer   | `customer`   | `cust123`  | Customer portal (test history)         |

Demo users are seeded automatically on startup via `TechnicianConfig.ready()` in `technician/apps.py` (gated by `DJANGO_SEED_ON_READY=1` env var). Passwords are always reset on each startup so credentials never drift.
To re-seed locally: `python manage.py create_demo_users`.  Change this behavior when you want user changes to persist.

## Data Models

### UserProfile (technician/models.py)
Links Django's built-in `User` to a role. Roles: `technician`, `operations`, `manager`, `admin`, `customer`.

### Customer (technician/models.py)
Stores reusable customer/account records. Fields: business name, contact name, phone, email, billing address, city, state, county, zip. Operations and Manager roles can create and edit. 10 sample customers seeded on startup matching the demo jobs.

### Job (technician/models.py)
Stores all job/site information. Fields cover:
- customer_ref (optional FK to Customer), customer name (text), address, contact, phone
- State and county (service location jurisdiction)
- Scheduled date and time
- Assigned technician (ForeignKey to User)
- Status: pending / in_progress / completed / cancelled
- Device identity: type, size, make, model, serial, location notes
- Map coordinates: property lat/lng and device lat/lng
- Created/updated timestamps

### TestResult (technician/models.py)
Persists backflow test readings submitted by technicians. Fields cover:
- Job reference (ForeignKey to Job), customer, address
- Device identity: type, size, manufacturer, model, serial, install year
- Test readings: CV1/CV2 results + PSI, RV result + PSI, line PSI
- Overall pass/fail, technician initials, notes, submitted_by user
- Future: utility API submission tracking (`utility_submitted`, `utility_submitted_at`)

## Role-Based Access

| Role | Can Access |
|------|-----------|
| Technician | Daily schedule, job detail, test submission form |
| Operations | Job management dashboard, create/edit jobs, assign technicians |
| Manager | Same as Operations (manager-specific views planned) |
| Admin | User management — view all users, add new users, edit roles/passwords |
| Customer | Customer portal — view test history and upcoming service |

Login redirects automatically based on role. Unauthorized role access redirects to login.

> **TODO — Password Persistence:** Currently `AppConfig.ready()` resets all demo passwords on every app startup, so any password changed via the Admin screen will be overwritten on the next deploy or restart. To fix: update `_seed_demo_users()` in `technician/apps.py` to only call `set_password()` when `created=True` (user is brand new), not on every run.

## Current POC Limitations (Known Tech Debt)
1. **No multi-tenant support** — no concept of separate companies/accounts yet
2. **No scheduling system** — jobs assigned manually by operations, no dispatch/routing optimization
3. **No utility API integration** — `utility_submitted` field exists but no actual submission logic (contact JEA or BackflowManager for integration access)
4. **Manager role** — currently sees Operations views; manager-specific reporting views not yet built
5. **No password reset** — POC credentials only, no email/reset flow

## Deployment
- Platform: Render — https://wolf-9bbc.onrender.com
- Build: `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate`
- Start: `DJANGO_SEED_ON_READY=1 gunicorn wolf_backflow.wsgi:application`
- Env vars required: `SECRET_KEY`, `DATABASE_URL` (Supabase pooler URI, port 6543), `DEBUG=False`, `DJANGO_SEED_ON_READY=1`
- Supabase connection: use pooler URI (not direct port 5432 — Render free tier blocks it)
- Strip `?pgbouncer=true` from Supabase ORM connection string before setting `DATABASE_URL`
- Note: `create_demo_users` management command was removed from the build step because Render's build phase cannot write to Supabase; seeding now runs inside the gunicorn process via `AppConfig.ready()`

## Next Priorities (as of April 2026)
- [ ] Manager-specific reporting views (test results summary, technician performance)
- [ ] Multi-company / multi-tenant architecture for acquired companies
- [ ] Scheduling and dispatch system with routing optimization
- [ ] Utility compliance report generation and submission
- [ ] Customer portal (separate login for property owners to view test history)
- [ ] QuickBooks Online integration for invoicing

## Device Types Supported
| Code | Full Name |
|------|-----------|
| RPZ  | Reduced Pressure Zone |
| DCVA | Double Check Valve Assembly |
| PVB  | Pressure Vacuum Breaker |
| SVB  | Spill-Resistant Vacuum Breaker |
| RPDA | Reduced Pressure Detector Assembly |

## Conventions
- Time zone: `America/New_York`
- All test PSI values: `DecimalField(max_digits=6, decimal_places=1)`
- URL namespacing: public routes at `/`, internal portal routes at `/tech/`
- Templates live inside each app: `technician/templates/technician/` and `public/templates/public/`