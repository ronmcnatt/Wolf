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
- Internal portal login: http://localhost:8000/tech/login/
- Tech dashboard: http://localhost:8000/tech/dashboard/
- Ops dashboard: http://localhost:8000/tech/ops/

## POC Users

| Role       | Username     | Password   | Lands On                               |
|------------|--------------|------------|----------------------------------------|
| Technician | `technician` | `tech123`  | Daily schedule (today's assigned jobs) |
| Operations | `operations` | `ops123`   | Job management dashboard               |
| Manager    | `manager`    | `mgr123`   | Job management dashboard               |
| Admin      | `admin`      | `admin123` | User management (all users + roles)    |

Users and today's sample jobs are seeded automatically on deploy via `create_demo_users` management command.
To re-seed locally: `python manage.py create_demo_users`

## Data Models

### UserProfile (technician/models.py)
Links Django's built-in `User` to a role. Roles: `technician`, `operations`, `manager`, `admin`.

### Job (technician/models.py)
Stores all job/site information. Fields cover:
- Customer, address, contact, phone
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

Login redirects automatically based on role. Unauthorized role access redirects to login.

## Current POC Limitations (Known Tech Debt)
1. **No multi-tenant support** — no concept of separate companies/accounts yet
2. **No scheduling system** — jobs assigned manually by operations, no dispatch/routing optimization
3. **No utility API integration** — `utility_submitted` field exists but no actual submission logic (contact JEA or BackflowManager for integration access)
4. **Manager role** — currently sees Operations views; manager-specific reporting views not yet built
5. **No password reset** — POC credentials only, no email/reset flow

## Deployment
- Platform: Render — https://wolf-9bbc.onrender.com
- Build: `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate && python manage.py create_demo_users`
- Start: `gunicorn wolf_backflow.wsgi:application`
- Env vars required: `SECRET_KEY`, `DATABASE_URL` (Supabase pooler URI, port 6543), `DEBUG=False`
- Supabase connection: use pooler URI (not direct port 5432 — Render free tier blocks it)
- Strip `?pgbouncer=true` from Supabase ORM connection string before setting `DATABASE_URL`

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