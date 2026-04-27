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
technician/        # Technician portal — login, dashboard, job detail, test submission
static/            # CSS and images (compiled to staticfiles/ on build)
branding/          # Logo SVGs and branding assets
```

## Running Locally
```bash
cd /Users/ronaldmcnatt/Documents/Wolf
python manage.py runserver
```
- Tech portal login: username `test` / password `test` (hardcoded POC credentials)
- Tech dashboard: http://localhost:8000/tech/

## Data Models

### TestResult (technician/models.py)
Persists backflow test readings to the database. Fields cover:
- Job reference, customer, address
- Device identity: type (RPZ, DCVA, PVB, SVB, RPDA), size, manufacturer, model, serial, install year
- Test readings: CV1/CV2 results + PSI, RV result + PSI, line PSI
- Overall pass/fail, technician initials, notes
- Future: utility API submission tracking (`utility_submitted`, `utility_submitted_at`)

### Jobs (POC — NOT yet in DB)
Jobs are currently hardcoded as `SAMPLE_JOBS` list in `technician/views.py`. This is a proof-of-concept only. A proper `Job` database model needs to be built.

## Current POC Limitations (Known Tech Debt)
1. **No Job model** — jobs are a hardcoded list in views.py, not stored in the database
2. **Hardcoded auth** — technician login checks `username == 'test' and password == 'test'`; needs proper Django auth or a Technician model
3. **No multi-tenant support** — no concept of separate companies/accounts yet
4. **No scheduling system** — jobs have hardcoded times, no real dispatch/scheduling
5. **No utility API integration** — `utility_submitted` field exists but no actual submission logic

## Deployment
- Platform: Render
- Build: `pip install -r requirements.txt && python manage.py collectstatic --no-input && python manage.py migrate`
- Start: `gunicorn wolf_backflow.wsgi:application`
- Env vars required: `SECRET_KEY`, `DATABASE_URL` (Supabase pooler URI, port 6543), `DEBUG=False`
- Supabase connection: use pooler URI (not direct port 5432 — Render free tier blocks it)
- Strip `?pgbouncer=true` from Supabase ORM connection string before setting `DATABASE_URL`

## Next Priorities (as of April 2026)
- [ ] Build proper `Job` model and migrate SAMPLE_JOBS to database
- [ ] Replace hardcoded auth with proper Technician model / Django auth
- [ ] Multi-company / multi-tenant architecture for acquired companies
- [ ] Scheduling and dispatch system
- [ ] Utility compliance report generation and submission (mock API layer built, real utility API TBD — contact JEA or BackflowManager for integration access)

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
- URL namespacing: public routes at `/`, technician routes at `/tech/`
- Templates live inside each app: `technician/templates/technician/` and `public/templates/public/`
