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
Stores reusable customer/account records. Fields: business name, contact name, phone, email, **website** (URLField), billing address, city, state, county, zip, notes, property lat/lng, device lat/lng. Operations and Manager roles can create and edit. 10 sample customers seeded on startup with addresses and coordinates matching the demo jobs. Websites researched and populated for ~34 customers via `seedcustomerwebsites` endpoint.

### CustomerLocation (technician/models.py)
One-to-many service locations per Customer (FK → Customer, `related_name='locations'`). Each location has: label (e.g. "Main Office", "Building A"), address, city, state, county, zip_code, lat/lng (property), device_lat/device_lng. Managed via AJAX endpoints on the customer edit page — each location has its own map for property and device coordinates. When a customer has locations, the job form shows a location picker dropdown to pre-fill the job address/coords from a specific location.

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

### ActivityLog (technician/models.py)
Records user actions for process mining and audit. Fields: `user` (FK to User), `activity` (choice), `timestamp` (auto), `detail` (JSONField — context like job_id, customer, result), `ip_address`.
Current activity choices: `login`, `view_job`, `submit_test_result`.
Logging is wired in `views.py` via `log_activity(request, activity, **detail)` helper. To add a new activity: add a choice to `ActivityLog.ACTIVITIES`, call `log_activity()` in the relevant view.

### SmokeTestRun / SmokeTestCase (technician/models.py)
Stores results from each smoke test run. `SmokeTestRun` has `run_at`, `triggered_by` (FK to User), `passed`, `failed` counts. `SmokeTestCase` has `run` (FK), `name`, `label`, `category`, `passed` (bool), `detail` (text).
Test definitions live in `technician/smoke_tests.py` — each test is a decorated function returning `(bool, str)`. To add a new test: use `@register(name, label, category)` decorator.

## Role-Based Access

| Role | Can Access |
|------|-----------|
| Technician | Open jobs (pending/in-progress from today forward by default), job detail, test submission form |
| Operations | Job management dashboard (Jobs + Customers tabs), create/edit jobs, create/edit customers, assign technicians, CSV import |
| Manager | Same as Operations (manager-specific reporting views planned) |
| Admin | User management, Smoke Tests tab, Process Mining tab |
| Customer | Customer portal — view test history and upcoming service (separate login at `/tech/customer/login/`) |

Login redirects automatically based on role. Unauthorized role access redirects to login.

> **TODO — Password Persistence:** Currently `AppConfig.ready()` resets all demo passwords on every app startup, so any password changed via the Admin screen will be overwritten on the next deploy or restart. To fix: update `_seed_demo_users()` in `technician/apps.py` to only call `set_password()` when `created=True` (user is brand new), not on every run.

## Current POC Limitations (Known Tech Debt)
1. **No multi-tenant support** — no concept of separate companies/accounts yet
2. **Auto-schedule is greedy, not optimal** — geo-VRP with 2-opt exists but no real-time traffic, drive-time estimates, or technician start/end locations; county centroids used as fallback when coordinates are missing
3. **No utility API integration** — `utility_submitted` field exists but no actual submission logic (contact JEA or BackflowManager for integration access)
4. **Manager role** — currently sees Operations views; manager-specific reporting views not yet built
5. **No password reset** — POC credentials only, no email/reset flow
6. **No Paylocity Integration** - For Technician PTO, Coverage Areas, et. Al
7. **No QuickBooks Integration** - For Estimates and Invoicing, M&A Invoice uploads, etc.

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
| 0009 | smoke_test_models | SmokeTestRun, SmokeTestCase |
| 0010 | activity_log | ActivityLog |
| 0011 | website_and_customer_locations | website (URLField) on Customer; CustomerLocation model |

## Sample Data (Supabase / Production)
All one-time seed endpoints have been run against Supabase. Current state:
- **10 original customers** — seeded with addresses and coordinates
- **10 historical 2025 jobs** — one per customer, all completed/passed; distributed JS×4, MT×3, RD×3
- **3 completed 2026 jobs** — Jan–Mar 2026, all by John Smith (JS), all passed
- **7 unassigned pending 2026 jobs** — May–Jun 2026, remaining original customers
- **45 unassigned pending 2026 jobs** — May 6–8 2026, Duval/St. Johns/Clay counties; seeded via `seedupcomingjobs`; new Customer records created for each (coordinates need `geocodecustomers` run)
- **13 TestResult records** — one for each completed job

Seed endpoints (keep in urls.py for future reseeds, idempotent):
- `GET /tech/seedusers/` — creates/updates all 7 demo users with correct passwords, roles, counties, and license data (use when AppConfig.ready() seed fails silently)
- `GET /tech/reseedcoords/` — patches lat/lng onto the 10 original sample customers
- `GET /tech/seedhistory/` — creates historical jobs + test results (skips if already exist)
- `GET /tech/reassignhistory/` — patches assigned_to/submitted_by on historical jobs (fixes unassigned if seedhistory ran before mthompson/rdiaz were created)
- `GET /tech/seedutilityfields/` — patches utility_account_number on existing TestResults with demo account numbers (JEA/CCUA/SJC format by county)
- `GET /tech/seedupcomingjobs/` — creates 45 pending unassigned jobs for May 6–8 2026 across Duval/St. Johns/Clay (idempotent — skips if already exist)
- `GET /tech/geocodecustomers/` — geocodes all Customer records missing lat/lng via Nominatim at 1 req/sec; **run once after seedupcomingjobs** to populate coordinates for the 45 new customers so auto-schedule uses real distances
- `GET /tech/seedcustomerwebsites/` — idempotent: sets `website` (and `email` when missing) on ~34 existing customers from researched data; **run once on Render after deploying migration 0011**

## Florida Utility Integration Reference
Full FL utility research is in `florida_utilities.csv` at project root (60+ utilities). Key findings:
- **No Florida utility has a public API** — all use closed SaaS portals or email/PDF
- **Platform landscape**: BSI Online (Broward + others), Tokay WebTest (Miami-Dade, Sarasota), SwiftComply (Tampa), VEPO CrossConnex (Delray Beach), Backflow BMP (Hillsborough County), Manatee portal (in-house), GRU CCC Database (in-house), PBCWUD E-Backflow (in-house)
- **Universal test fields** are identical statewide (AWWA/USC standard: CV1, CV2, RV, line PSI)
- **The key differentiator per utility** is the account identifier label (JEA Account #, BSI CCN, VEPO VCC#, Tokay meter #, PBCWUD account #, etc.)
- **`UTILITY_CONFIGS` dict** in `views.py` maps `(state, county)` tuples to utility metadata; currently covers 35 FL counties; the `tech_job_detail` view passes `utility_config` to `job_detail.html`
- **Dynamic utility section** on the test form: if a county maps to a known utility, a teal-bordered section appears above the Notes field showing the utility name, platform, the right account number label, optional reference/permit field, and a submission reminder note. GRU (Alachua) also shows hazard level and service type dropdowns.
- To add a new county config: add a `('FL', 'CountyName')` entry to `UTILITY_CONFIGS` in `views.py` — no template changes needed

## Next Priorities (as of May 2026)
- [x] Create Import page in Operations — CSV upload, preview with checkboxes, confirm import
- [x] Activity log for process mining — login, view job, submit test wired for technician role
- [x] Smoke test tab on admin console — Technician workflow checks, run on demand, history
- [x] Auto-schedule panel — geo-VRP routing with 2-opt, route miles, unassign + re-schedule option
- [ ] Run `GET /tech/geocodecustomers/` on Render to populate coordinates for 45 new customers
- [ ] Identify / Handle Acquisitions in Data Model
- [ ] Add Operations/Admin/Customer workflow specs → smoke test cases for those roles
- [ ] Expand activity logging to Operations role (create job, edit job, create customer)
- [ ] Improve auto-schedule with drive-time estimates (Google Maps / OSRM) instead of straight-line haversine
- [ ] Customer self-registers
- [ ] Wire up utility submission: generate per-utility PDF (BSI form, Pasco form, etc.) or POST to SwiftComply/Tokay portal using stored `utility_account_number`
- [ ] Ability to submit results to a utility, Portal and API
- [ ] Sales role that can see estimates, ability to email to prospective customers, saved in QBO
- [ ] Ability to update Estimate to an Order
- [ ] Manager-specific reporting views (test results summary, technician performance)
- [ ] Multi-company / multi-tenant architecture for acquired companies
- [ ] Utility compliance report generation and submission
- [ ] Integrate Repairs and Parts Inventory
- [ ] Customer self orders a test, including via text, take picture of letter from utility, etc
- [ ] Automation to request non-compliant devices from each utility
- [ ] Workflow to test on behalf of utility and them bill customer


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
- **Operations dashboard tabs**: `?tab=jobs` (default) and `?tab=customers`. Jobs tab defaults to showing jobs from today forward (pending + future); a "Show All Dates" link appears when using the default — "Clear" when a custom filter is active. User can filter by date, status, or technician. Customers tab has search by business name, city, or county; shows active jobs, total jobs, last test date and pass/fail result per customer.
- **Operations nav**: Operations and Manager users see **📥 Import** and **Log Out** as always-visible links in the top-right nav. Other roles see only Log Out.
- **CSV Import** (`/tech/ops/import/`): two-step flow — upload CSV → preview table with per-row checkboxes (New/Existing customer badge, status pill, warnings) → confirm POST creates Customer (if new), Job, and TestResult (for completed rows with `overall_result`). Downloadable template at `/tech/ops/import/template/`. 30 supported columns across Customer, Job, and Test Result. Import summary shown as a green banner on the ops dashboard after completion.
- **Admin console tabs**: Users | Smoke Tests | Process Mining — all three admin pages share the same tab nav.
- **Smoke Tests tab** (`/tech/admin/smoketests/`): run on-demand via POST button; shows latest results table grouped by category (PASS/FAIL badges + detail message) and run history for last 10 runs. Test definitions in `technician/smoke_tests.py` using `@register(name, label, category)` decorator. Currently 6 Technician checks.
- **Process Mining tab** (`/tech/admin/processmining/`): filterable activity feed (role, user, activity dropdowns — auto-submit on change). Shows last 200 events with timestamp, user, role badge, color-coded activity badge (🔑 Logged In / 👁 Viewed Job / ✓ Submitted Test), job/customer context, and IP address. Stat cards: Total Events / Today / Unique Users.
- **Technician dashboard default**: shows open jobs (pending + in-progress) from today forward. Filter pills: Today / Open Jobs (default) / All Dates.
- **State/County dropdowns**: FL counties are pre-populated; selecting a non-FL state clears the county list. Pattern used in job form, customer modal, and customer edit page.
- **Dynamic utility section on test form**: when a job's state+county maps to a known utility (via `UTILITY_CONFIGS` in views.py), a teal-bordered card appears on the test form above Notes. Shows utility name, platform badge, submission instructions, and the correct account number field label for that utility (BSI CCN, JEA account #, VEPO VCC#, etc.). GRU (Alachua) additionally shows hazard level and service type selects.
- **Auto-schedule panel** (right sidebar on ops dashboard): date picker, multi-select technician dropdown, Max Trips (5–15), Unassign Current Trips (No/Yes), ⚡ Auto Schedule button, 📍 Geocode Addresses button.
  - **Routing algorithm** (`ops_auto_schedule` in views.py): (1) resolves lat/lng for each job — job record → linked customer → county centroid fallback; (2) builds per-tech running centroid from existing assignments; techs with no existing jobs are spread east-to-west across the job bounding box; (3) greedy nearest-centroid assignment — jobs sorted outward from geographic center, each goes to eligible tech with closest centroid (tiebreak: fewest total jobs); (4) 2-opt optimization minimises total driving distance within each tech's route; (5) `scheduled_time` set in optimised order starting 8:00am + 45 min per stop.
  - **Unassign Current Trips = Yes** — clears `assigned_to` and `scheduled_time` for all pending/in-progress jobs belonging to selected techs on that date before routing, giving the algo a clean slate.
  - **Result display**: per-tech card showing new jobs, total, and route miles; total estimated miles across all techs; skipped jobs with reason.
  - **Geocode Addresses button** — AJAX GET to `/tech/geocodecustomers/`; geocodes all Customer records missing lat/lng via Nominatim at 1 req/sec; shows geocoded/failed/skipped counts when done. Run once after seeding new customers.
  - **Geo helpers in views.py**: `_COUNTY_CENTROIDS` (6 FL counties), `haversine(lat1, lng1, lat2, lng2)` → miles, `geocode_nominatim(address, city, state)` → `(lat, lng)` or None.
- **Technician county filter on job form**: the "Assign To" dropdown in `ops_job_form.html` is JS-driven (TECHNICIANS array from `technicians_json`). Selecting a county filters the dropdown to only technicians whose `counties` list includes that county. A coverage note "(N cover County, M hidden)" appears next to the label. If a tech's license expires within 90 days, their name shows "⚠ Exp. Mon YYYY" in amber; if expired, "✗ License expired" in red. Techs outside coverage but already assigned to a job appear with "⚠ Outside coverage area" warning.

## Conventions
- Time zone: `America/New_York`
- All test PSI values: `DecimalField(max_digits=6, decimal_places=1)`
- URL namespacing: public routes at `/`, internal portal routes at `/tech/`
- Templates live inside each app: `technician/templates/technician/` and `public/templates/public/`
- Custom template tag `tech_extras` (in `technician/templatetags/`): `get_item` dict lookup filter, `split` string split filter