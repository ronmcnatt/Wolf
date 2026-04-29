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

| Role       | Username     | Password        | Name           | Lands On                               |
|------------|--------------|-----------------|----------------|----------------------------------------|
| Technician | `technician` | `tech123`       | John Smith     | Daily schedule (today's assigned jobs) |
| Technician | `mthompson`  | `mthompson123`  | Marcus Thompson| Daily schedule (today's assigned jobs) |
| Technician | `rdiaz`      | `rdiaz123`      | Rosa Diaz      | Daily schedule (today's assigned jobs) |
| Operations | `operations` | `ops123`        | Sarah Johnson  | Job management dashboard               |
| Manager    | `manager`    | `mgr123`        | Robert Wolf    | Job management dashboard               |
| Admin      | `admin`      | `admin123`      | Admin Wolf     | User management (all users + roles)    |
| Customer   | `customer`   | `cust123`       | James Wilson   | Customer portal (test history)         |

Demo users are seeded automatically on startup via `TechnicianConfig.ready()` in `technician/apps.py` (gated by `DJANGO_SEED_ON_READY=1` env var). Passwords are always reset on each startup so credentials never drift.
To re-seed locally: `python manage.py create_demo_users`.  Change this behavior when you want user changes to persist.

## Data Models

### UserProfile (technician/models.py)
Links Django's built-in `User` to a role. Roles: `technician`, `operations`, `manager`, `admin`, `customer`.
Technician-specific fields: `counties` (JSONField — list of FL county strings they are certified to work in), `is_licensed` (bool), `license_expires` (DateField). Demo technician coverage: John Smith → Duval/Clay/St. Johns/Nassau; Marcus Thompson → Duval/Clay/St. Johns/Flagler; Rosa Diaz → Duval/Clay/St. Johns/Alachua.

### Customer (technician/models.py)
Stores reusable customer/account records. Fields: business name, contact name, phone, email, billing address, city, state, county, zip, notes, property lat/lng, device lat/lng. Operations and Manager roles can create and edit. 10 sample customers seeded on startup with addresses and coordinates matching the demo jobs.

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
- Utility-specific fields: `utility_account_number` (account/meter/CCN/VCC# for that utility), `utility_reference_number` (permit #, secondary ref), `hazard_level` (low/high — used by GRU and others), `service_type` (domestic/irrigation/fire/other)
- Future: utility API submission tracking (`utility_submitted`, `utility_submitted_at`)

## Role-Based Access

| Role | Can Access |
|------|-----------|
| Technician | Daily schedule, job detail, test submission form |
| Operations | Job management dashboard (Jobs + Customers tabs), create/edit jobs, create/edit customers, assign technicians |
| Manager | Same as Operations (manager-specific reporting views planned) |
| Admin | User management — view all users, add new users, edit roles/passwords |
| Customer | Customer portal — view test history and upcoming service (separate login at `/tech/customer/login/`) |

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

## Migrations
| # | Name | What it adds |
|---|------|-------------|
| 0001 | initial | UserProfile, Job, TestResult |
| 0002 | add_test_result | TestResult model refinements |
| 0003 | admin role | admin choice added to UserProfile.role |
| 0004 | customer role | customer choice added to UserProfile.role |
| 0005 | Customer model + Job jurisdiction | Customer model; state/county fields on Job |
| 0006 | customer_latlng | lat/lng/device_lat/device_lng on Customer |
| 0007 | utility_fields_on_testresult | utility_account_number, utility_reference_number, hazard_level, service_type on TestResult |
| 0008 | technician_credentials | counties (JSONField), is_licensed, license_expires on UserProfile |

## Sample Data (Supabase / Production)
All one-time seed endpoints have been run against Supabase. Current state:
- **10 customers** — seeded with addresses and coordinates
- **10 historical 2025 jobs** — one per customer, all completed/passed; distributed JS×4, MT×3, RD×3
- **3 completed 2026 jobs** — Jan–Mar 2026, all by John Smith (JS), all passed
- **7 unassigned pending 2026 jobs** — May–Jun 2026, remaining customers
- **13 TestResult records** — one for each completed job

Seed endpoints (keep in urls.py for future reseeds, idempotent):
- `GET /tech/reseedcoords/` — patches lat/lng onto the 10 sample customers
- `GET /tech/seedhistory/` — creates historical jobs + test results (skips if already exist)
- `GET /tech/reassignhistory/` — patches assigned_to/submitted_by on historical jobs (fixes unassigned if seedhistory ran before mthompson/rdiaz were created)
- `GET /tech/seedutilityfields/` — patches utility_account_number on existing TestResults with demo account numbers (JEA/CCUA/SJC format by county)

## Florida Utility Integration Reference
Full FL utility research is in `florida_utilities.csv` at project root (60+ utilities). Key findings:
- **No Florida utility has a public API** — all use closed SaaS portals or email/PDF
- **Platform landscape**: BSI Online (Broward + others), Tokay WebTest (Miami-Dade, Sarasota), SwiftComply (Tampa), VEPO CrossConnex (Delray Beach), Backflow BMP (Hillsborough County), Manatee portal (in-house), GRU CCC Database (in-house), PBCWUD E-Backflow (in-house)
- **Universal test fields** are identical statewide (AWWA/USC standard: CV1, CV2, RV, line PSI)
- **The key differentiator per utility** is the account identifier label (JEA Account #, BSI CCN, VEPO VCC#, Tokay meter #, PBCWUD account #, etc.)
- **`UTILITY_CONFIGS` dict** in `views.py` maps `(state, county)` tuples to utility metadata; currently covers 35 FL counties; the `tech_job_detail` view passes `utility_config` to `job_detail.html`
- **Dynamic utility section** on the test form: if a county maps to a known utility, a teal-bordered section appears above the Notes field showing the utility name, platform, the right account number label, optional reference/permit field, and a submission reminder note. GRU (Alachua) also shows hazard level and service type dropdowns.
- To add a new county config: add a `('FL', 'CountyName')` entry to `UTILITY_CONFIGS` in `views.py` — no template changes needed

## Next Priorities (as of April 2026)
- [ ] Create Import Tab on the Operations Landing Page, have an upload button, preview and import
- [ ] Identify / Handle Aquisitions in Data Model
- [ ] Scheduling and dispatch system with routing optimization
- [ ] Customer self-registers
- [ ] Wire up utility submission: generate per-utility PDF (BSI form, Pasco form, etc.) or POST to SwiftComply/Tokay portal using stored `utility_account_number`
- [ ] Ability to submit results to a utility, Portal and API
- [ ] Sales role that can see estimates, ability to email to prospective customers, saved in QBO
- [ ] Abiilty to update Estimate to an Order
- [ ] Manager-specific reporting views (test results summary, technician performance)
- [ ] Multi-company / multi-tenant architecture for acquired companies
- [ ] Utility compliance report generation and submission
- [ ] QuickBooks Online integration for invoicing
- [ ] Integrate Repairs and Parts Inventory
- [ ] Customer self orders a test
- [ ] Handle Technician credentials and work schedule, PTO, service area

## Device Types Supported
| Code | Full Name |
|------|-----------|
| RPZ  | Reduced Pressure Zone |
| DCVA | Double Check Valve Assembly |
| PVB  | Pressure Vacuum Breaker |
| SVB  | Spill-Resistant Vacuum Breaker |
| RPDA | Reduced Pressure Detector Assembly |

## Key UI Patterns
- **Customer lookup on job form**: filter-as-you-type input + select dropdown; selecting a customer auto-fills business name, address, contact, phone, state/county dropdowns, and both Leaflet map markers.
- **Customer modal**: "+ New Customer" and "✎ Edit Customer" buttons open an inline modal (AJAX `POST` to `customer_save`); the CUSTOMERS JS array is updated in-place without a page reload.
- **Leaflet maps**: both the job form and customer edit form have Property Location and Device Location maps (OpenStreetMap tiles via Leaflet 1.9.4). Dragging markers updates hidden lat/lng inputs. Job form has a "📍 Locate" button that geocodes the address via Nominatim.
- **Operations dashboard tabs**: `?tab=jobs` (default) and `?tab=customers`. Jobs tab defaults to showing all jobs (no date filter); user can filter by date, status, or technician. Customers tab has search by business name, city, or county; shows active jobs, total jobs, last test date and pass/fail result per customer.
- **State/County dropdowns**: FL counties are pre-populated; selecting a non-FL state clears the county list. Pattern used in job form, customer modal, and customer edit page.
- **Dynamic utility section on test form**: when a job's state+county maps to a known utility (via `UTILITY_CONFIGS` in views.py), a teal-bordered card appears on the test form above Notes. Shows utility name, platform badge, submission instructions, and the correct account number field label for that utility (BSI CCN, JEA account #, VEPO VCC#, etc.). GRU (Alachua) additionally shows hazard level and service type selects.
- **Technician county filter on job form**: the "Assign To" dropdown in `ops_job_form.html` is JS-driven (TECHNICIANS array from `technicians_json`). Selecting a county filters the dropdown to only technicians whose `counties` list includes that county. A coverage note "(N cover County, M hidden)" appears next to the label. If a tech's license expires within 90 days, their name shows "⚠ Exp. Mon YYYY" in amber; if expired, "✗ License expired" in red. Techs outside coverage but already assigned to a job appear with "⚠ Outside coverage area" warning.

## Conventions
- Time zone: `America/New_York`
- All test PSI values: `DecimalField(max_digits=6, decimal_places=1)`
- URL namespacing: public routes at `/`, internal portal routes at `/tech/`
- Templates live inside each app: `technician/templates/technician/` and `public/templates/public/`
- Custom template tag `tech_extras` (in `technician/templatetags/`): `get_item` dict lookup filter, `split` string split filter