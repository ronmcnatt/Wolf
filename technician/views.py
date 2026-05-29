import csv
import io
import json
import math
import time
import urllib.request
import urllib.parse
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.utils import timezone
from django.views.decorators.http import require_POST
from functools import wraps
from .models import UserProfile, Job, TestResult, Customer, CustomerLocation, ActivityLog

def log_activity(request, activity, **detail):
    ip = request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip() \
         or request.META.get('REMOTE_ADDR')
    user = request.user if request.user.is_authenticated else None
    ActivityLog.objects.create(user=user, activity=activity, detail=detail, ip_address=ip or None)


# ── Geo utilities ─────────────────────────────────────────────────────────────

_COUNTY_CENTROIDS = {
    'Duval':     (30.3322, -81.6557),
    'St. Johns': (29.9200, -81.4340),
    'Clay':      (30.0994, -81.6771),
    'Nassau':    (30.5941, -81.7787),
    'Flagler':   (29.4730, -81.3014),
    'Alachua':   (29.6516, -82.3248),
}


def haversine(lat1, lng1, lat2, lng2):
    """Straight-line distance in miles between two lat/lng points."""
    R = 3958.8
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def geocode_nominatim(address, city, state):
    """
    Single geocode request via Nominatim.
    Returns (lat, lng) or None. Caller must enforce 1-req/sec rate limit.
    """
    q = ', '.join(filter(None, [address, city, state]))
    url = 'https://nominatim.openstreetmap.org/search?' + urllib.parse.urlencode(
        {'q': q, 'format': 'json', 'limit': 1}
    )
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'WolfBackflow/1.0'})
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read())
            if data:
                return float(data[0]['lat']), float(data[0]['lon'])
    except Exception:
        pass
    return None


# Maps (state, county) → utility submission metadata shown on the test form.
# Keys: utility, platform, account_label, reference_label, show_hazard,
#       show_service_type, note
UTILITY_CONFIGS = {
    ('FL', 'Alachua'):      {'utility': 'GRU (Gainesville Regional Utilities)', 'platform': 'GRU CCC Online Database', 'account_label': 'GRU Account / Device ID', 'reference_label': None, 'show_hazard': True, 'show_service_type': True, 'note': 'Submit via GRU proprietary portal. Tester must have GRU credentials. Residential testing is biennial (2-year).'},
    ('FL', 'Bay'):          {'utility': 'City of Panama City', 'platform': 'Email + Permit', 'account_label': 'Account Number', 'reference_label': 'Building Permit Number', 'show_hazard': False, 'show_service_type': False, 'note': '$44 permit fee required. Online permit at us.cloudpermit.com.'},
    ('FL', 'Brevard'):      {'utility': 'Brevard County Utilities', 'platform': 'Email', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Contact Brevard County Utilities for submission details.'},
    ('FL', 'Broward'):      {'utility': 'Broward County / BSI municipalities', 'platform': 'BSI Online', 'account_label': 'BSI Customer Confirmation Number (CCN)', 'reference_label': 'Permit Number (Fort Lauderdale only)', 'show_hazard': False, 'show_service_type': False, 'note': 'CCN is mailed by the utility to the property owner. Submit at bsionline.com. Fort Lauderdale adds a $45 recertification admin fee.'},
    ('FL', 'Charlotte'):    {'utility': 'Charlotte County Utilities', 'platform': 'Email (PDF)', 'account_label': 'Charlotte County Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Email to CCUBackflow@CharlotteCountyFL.gov within 30 days.'},
    ('FL', 'Citrus'):       {'utility': 'Citrus County / FGUA', 'platform': 'Email (FGUA form)', 'account_label': 'FGUA Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'FGUA-approved form required. Submit to appropriate FGUA office.'},
    ('FL', 'Clay'):         {'utility': 'Clay County Utility Authority (CCUA)', 'platform': 'Email / Online Portal', 'account_label': 'CCUA Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Submit via the CCUA customer portal or email crossconnection@ccua.com. Annual testing required for all commercial assemblies.'},
    ('FL', 'Collier'):      {'utility': 'Collier County Water-Sewer District', 'platform': 'Contact utility', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Contact Collier County: 239-252-6245.'},
    ('FL', 'Duval'):        {'utility': 'JEA (Jacksonville Electric Authority)', 'platform': 'Email', 'account_label': 'JEA Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Submit to backflow@jea.com within 30 days of test date.'},
    ('FL', 'Escambia'):     {'utility': 'ECUA (Escambia County Utilities Authority)', 'platform': 'Email', 'account_label': 'ECUA Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Contact ECUA for submission details: ecua.fl.gov.'},
    ('FL', 'Flagler'):      {'utility': 'Flagler County / FGUA', 'platform': 'Email (FGUA form)', 'account_label': 'FGUA Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'FGUA-approved form required. Submit to appropriate FGUA office.'},
    ('FL', 'Hernando'):     {'utility': 'Hernando County / FGUA', 'platform': 'Email (FGUA form)', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'FGUA serves some Hernando areas. FGUA-approved form required.'},
    ('FL', 'Hillsborough'): {'utility': 'City of Tampa (SwiftComply) / Hillsborough County (Backflow BMP)', 'platform': 'SwiftComply / Backflow BMP', 'account_label': 'Utility Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'City of Tampa: submit via tampafl.c3swift.com within 7 days. Unincorporated Hillsborough: submit via bmpcomp.com.'},
    ('FL', 'Indian River'):  {'utility': 'Indian River County Utilities', 'platform': 'BSI Online', 'account_label': 'BSI Customer Confirmation Number (CCN)', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Submit at bsionlinetracking.com. BSI primary contact: 800-414-4990.'},
    ('FL', 'Lake'):         {'utility': 'Lake County / FGUA', 'platform': 'Email (FGUA form)', 'account_label': 'FGUA Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'FGUA serves 23 systems in Lake County. FGUA-approved form required.'},
    ('FL', 'Lee'):          {'utility': 'Lee County Utilities', 'platform': 'Contact utility', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'FGUA serves Lehigh Acres, N. Fort Myers, South Seas. Contact leegov.com.'},
    ('FL', 'Leon'):         {'utility': 'City of Tallahassee Utilities', 'platform': 'Physical delivery', 'account_label': 'Tallahassee Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Originals must be physically delivered to 4505-A Springhill Rd, Tallahassee FL 32305. No faxes accepted. Required before Certificate of Occupancy.'},
    ('FL', 'Manatee'):      {'utility': 'Manatee County Utilities', 'platform': 'Manatee Backflow Portal', 'account_label': 'Manatee Portal Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Portal-only — email/fax explicitly rejected. Submit within 7 days (failures within 1 business day). Pre-registration required.'},
    ('FL', 'Marion'):       {'utility': 'Marion County Utilities', 'platform': 'Email', 'account_label': 'Marion County Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Email to crossconnectioncontrol@marionfl.org. Phone: 352-307-4630.'},
    ('FL', 'Martin'):       {'utility': 'Martin County Utilities', 'platform': 'Contact utility', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Contact Martin County Utilities: 772-287-5453.'},
    ('FL', 'Miami-Dade'):   {'utility': 'Miami-Dade Water & Sewer (MDWASD)', 'platform': 'Tokay WebTest', 'account_label': 'MDWASD Meter / Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Submit via miamidade.tokaytest.com. CCU: 305-547-3046.'},
    ('FL', 'Nassau'):       {'utility': 'Nassau County / FGUA', 'platform': 'Email (FGUA form)', 'account_label': 'FGUA Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'FGUA-approved form required. Submit to appropriate FGUA office.'},
    ('FL', 'Okaloosa'):     {'utility': 'Okaloosa County Water & Sewer', 'platform': 'Contact utility', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Contact Okaloosa County Water & Sewer: 850-651-7172.'},
    ('FL', 'Orange'):       {'utility': 'Orange County Utilities / OUC', 'platform': 'Email (PDF)', 'account_label': 'Customer Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Email PDF form to Water.Backflow@ocfl.net. Note: all emails become public record.'},
    ('FL', 'Osceola'):      {'utility': 'Toho Water Authority', 'platform': 'Email', 'account_label': 'Toho Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Toho tests residential devices themselves. Commercial: email to BackflowCompliance@tohowater.com.'},
    ('FL', 'Palm Beach'):   {'utility': 'Palm Beach County Water Utilities (PBCWUD)', 'platform': 'E-Backflow Portal', 'account_label': 'PBCWUD Account Number', 'reference_label': 'Building Permit # (new installs)', 'show_hazard': False, 'show_service_type': False, 'note': 'Submit via ebill.pbcwater.com/ebackflow. Pre-register: WUDEBACKFLOWNOTIFICATION@pbcwater.com.'},
    ('FL', 'Pasco'):        {'utility': 'Pasco County Utilities', 'platform': 'Email (Pasco-specific form)', 'account_label': 'Pasco Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Pasco-specific form required — generic forms not accepted. Email to backflowprogram@mypasco.net.'},
    ('FL', 'Pinellas'):     {'utility': 'Pinellas County Utilities', 'platform': 'Contact utility', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Contact Pinellas County Utilities for submission details.'},
    ('FL', 'Polk'):         {'utility': 'Polk County / FGUA', 'platform': 'Email (FGUA form)', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'FGUA serves 7 Polk systems. FGUA-approved form required.'},
    ('FL', 'Putnam'):       {'utility': 'Putnam County / FGUA', 'platform': 'Email (FGUA form)', 'account_label': 'FGUA Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'FGUA-approved form required. Submit to appropriate FGUA office.'},
    ('FL', 'Sarasota'):     {'utility': 'Sarasota County Utilities', 'platform': 'Tokay WebTest', 'account_label': 'Service Meter Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Submit via sarasota.tokaytest.com. $5/submission fee. Email: backflow@scgov.net.'},
    ('FL', 'Seminole'):     {'utility': 'Seminole County Utilities', 'platform': 'Email', 'account_label': 'Seminole Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'After repairs: email affirmation within 24–48 hours to cwyatt@seminolecountyfl.gov.'},
    ('FL', 'St. Johns'):    {'utility': 'St. Johns County Utilities', 'platform': 'Email', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Contact St. Johns County Utilities for submission details.'},
    ('FL', 'St. Lucie'):    {'utility': 'St. Lucie County Utilities', 'platform': 'Contact utility', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Contact St. Lucie County Utilities: 772-464-7323.'},
    ('FL', 'Sumter'):       {'utility': 'NSCUDD / The Villages', 'platform': 'Contact utility', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Contact North Sumter County Utility Dependent District for submission details.'},
    ('FL', 'Volusia'):      {'utility': 'City of Daytona Beach / Volusia County', 'platform': 'Paper form', 'account_label': 'Account Number', 'reference_label': None, 'show_hazard': False, 'show_service_type': False, 'note': 'Paper form only. Deliver to 125 Basin St., Daytona Beach FL 32114.'},
}

FL_COUNTIES = [
    'Alachua','Baker','Bay','Bradford','Brevard','Broward','Calhoun',
    'Charlotte','Citrus','Clay','Collier','Columbia','DeSoto','Dixie',
    'Duval','Escambia','Flagler','Franklin','Gadsden','Gilchrist',
    'Glades','Gulf','Hamilton','Hardee','Hendry','Hernando','Highlands',
    'Hillsborough','Holmes','Indian River','Jackson','Jefferson',
    'Lafayette','Lake','Lee','Leon','Levy','Liberty','Madison',
    'Manatee','Marion','Martin','Miami-Dade','Monroe','Nassau',
    'Okaloosa','Okeechobee','Orange','Osceola','Palm Beach','Pasco',
    'Pinellas','Polk','Putnam','Santa Rosa','Sarasota','Seminole',
    'St. Johns','St. Lucie','Sumter','Suwannee','Taylor','Union',
    'Volusia','Wakulla','Walton','Washington',
]

US_STATES = [
    ('AL','Alabama'),('AK','Alaska'),('AZ','Arizona'),('AR','Arkansas'),
    ('CA','California'),('CO','Colorado'),('CT','Connecticut'),('DE','Delaware'),
    ('FL','Florida'),('GA','Georgia'),('HI','Hawaii'),('ID','Idaho'),
    ('IL','Illinois'),('IN','Indiana'),('IA','Iowa'),('KS','Kansas'),
    ('KY','Kentucky'),('LA','Louisiana'),('ME','Maine'),('MD','Maryland'),
    ('MA','Massachusetts'),('MI','Michigan'),('MN','Minnesota'),('MS','Mississippi'),
    ('MO','Missouri'),('MT','Montana'),('NE','Nebraska'),('NV','Nevada'),
    ('NH','New Hampshire'),('NJ','New Jersey'),('NM','New Mexico'),('NY','New York'),
    ('NC','North Carolina'),('ND','North Dakota'),('OH','Ohio'),('OK','Oklahoma'),
    ('OR','Oregon'),('PA','Pennsylvania'),('RI','Rhode Island'),('SC','South Carolina'),
    ('SD','South Dakota'),('TN','Tennessee'),('TX','Texas'),('UT','Utah'),
    ('VT','Vermont'),('VA','Virginia'),('WA','Washington'),('WV','West Virginia'),
    ('WI','Wisconsin'),('WY','Wyoming'),('DC','District of Columbia'),
]


# ── Role-based access decorators ──────────────────────────────────────────────

def role_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('tech_login')
            profile = getattr(request.user, 'profile', None)
            if not profile or profile.role not in roles:
                return redirect('tech_login')
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _redirect_by_role(user):
    role = getattr(getattr(user, 'profile', None), 'role', '')
    if role == 'admin':
        return redirect('admin_users')
    if role in ('operations', 'manager'):
        return redirect('ops_dashboard')
    if role == 'customer':
        return redirect('customer_dashboard')
    return redirect('tech_dashboard')


# ── Auth ──────────────────────────────────────────────────────────────────────

def tech_login(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)
    error = None
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username', ''),
            password=request.POST.get('password', ''),
        )
        if user is None:
            error = 'Invalid username or password.'
        else:
            if not hasattr(user, 'profile'):
                UserProfile.objects.create(user=user, role='technician')
            login(request, user)
            log_activity(request, 'login')
            return _redirect_by_role(user)
    return render(request, 'technician/login.html', {'error': error})


def tech_logout(request):
    logout(request)
    return redirect('tech_login')


def customer_login(request):
    if request.user.is_authenticated:
        return _redirect_by_role(request.user)
    error = None
    if request.method == 'POST':
        user = authenticate(
            request,
            username=request.POST.get('username', ''),
            password=request.POST.get('password', ''),
        )
        if user is None:
            error = 'Invalid username or password.'
        else:
            if not hasattr(user, 'profile'):
                UserProfile.objects.create(user=user, role='customer')
            login(request, user)
            return redirect('customer_dashboard')
    return render(request, 'technician/customer_login.html', {'error': error})




# ── Technician views ──────────────────────────────────────────────────────────

@role_required('technician', 'manager')
def tech_dashboard(request):
    today = timezone.localdate()
    date_filter = request.GET.get('filter', 'upcoming')

    jobs = Job.objects.filter(assigned_to=request.user)
    if date_filter == 'today':
        jobs = jobs.filter(scheduled_date=today)
    elif date_filter == 'upcoming':
        jobs = jobs.filter(scheduled_date__gte=today, status__in=('pending', 'in_progress'))
    # 'all' — no date or status restriction

    jobs = jobs.order_by('scheduled_date', 'scheduled_time')
    completed   = jobs.filter(status='completed').count()
    in_progress = jobs.filter(status='in_progress').count()
    pending     = jobs.filter(status='pending').count()

    return render(request, 'technician/dashboard.html', {
        'jobs': jobs,
        'completed': completed,
        'in_progress': in_progress,
        'pending': pending,
        'total': jobs.count(),
        'today': today,
        'date_filter': date_filter,
    })


@role_required('technician', 'manager')
def tech_job_detail(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    submitted = False

    if request.method == 'GET':
        log_activity(request, 'view_job',
                     job_id=job.id,
                     customer=job.customer,
                     scheduled_date=str(job.scheduled_date))

    if request.method == 'POST':
        p = request.POST

        def psi(f):
            try: return float(p[f]) if p.get(f) else None
            except ValueError: return None

        def yr(f):
            try: return int(p[f]) if p.get(f) else None
            except ValueError: return None

        TestResult.objects.create(
            job=job,
            customer=job.customer,
            address=job.address,
            device_type=p.get('device_type', job.device_type),
            device_size=p.get('device_size', job.device_size),
            manufacturer=p.get('manufacturer', job.device_make),
            model=p.get('model', job.device_model),
            serial=p.get('serial', job.serial),
            install_year=yr('install_year'),
            test_date=p.get('test_date'),
            test_time=p.get('test_time'),
            cv1_result=p.get('cv1_result', ''),
            cv1_psi=psi('cv1_psi'),
            cv2_result=p.get('cv2_result', ''),
            cv2_psi=psi('cv2_psi'),
            rv_result=p.get('rv_result', ''),
            rv_psi=psi('rv_psi'),
            line_psi=psi('line_psi'),
            overall_result=p.get('overall_result', 'pass'),
            notes=p.get('notes', ''),
            technician_initials=p.get('initials', '').upper(),
            submitted_by=request.user,
            utility_account_number=p.get('utility_account_number', '').strip(),
            utility_reference_number=p.get('utility_reference_number', '').strip(),
            hazard_level=p.get('hazard_level', ''),
            service_type=p.get('service_type', ''),
        )
        job.status = 'completed'
        job.save()
        log_activity(request, 'submit_test_result',
                     job_id=job.id,
                     customer=job.customer,
                     result=p.get('overall_result', 'pass'))
        submitted = True

    prior_results = job.test_results.all()
    utility_config = UTILITY_CONFIGS.get((job.state, job.county))
    return render(request, 'technician/job_detail.html', {
        'job': job,
        'submitted': submitted,
        'prior_results': prior_results,
        'utility_config': utility_config,
    })


# ── Operations views ──────────────────────────────────────────────────────────

@role_required('operations', 'manager')
def ops_dashboard(request):
    import_summary = request.session.pop('import_summary', None)
    tab = request.GET.get('tab', 'jobs')

    # ── Jobs tab ──
    date_filter   = request.GET.get('date', '')
    status_filter = request.GET.get('status', '')
    tech_filter   = request.GET.get('tech', '')
    show_all      = request.GET.get('show_all', '')

    jobs = Job.objects.select_related('assigned_to', 'customer_ref').all()

    # Default to today + future when no explicit filters are active
    using_default = not any([date_filter, status_filter, tech_filter, show_all])
    if using_default:
        jobs = jobs.filter(scheduled_date__gte=timezone.localdate())
    else:
        if date_filter:
            jobs = jobs.filter(scheduled_date=date_filter)
        if status_filter:
            jobs = jobs.filter(status=status_filter)
        if tech_filter:
            jobs = jobs.filter(assigned_to__id=tech_filter)

    technicians = User.objects.filter(profile__role='technician').select_related('profile').order_by('first_name')
    total       = jobs.count()
    unassigned  = jobs.filter(assigned_to__isnull=True).count()
    completed   = jobs.filter(status='completed').count()
    pending     = jobs.filter(status='pending').count()

    technicians_json = json.dumps([
        {'id': t.id, 'name': t.get_full_name() or t.username}
        for t in technicians
    ])

    # ── Customers tab ──
    csearch   = request.GET.get('csearch', '').strip()
    customers = Customer.objects.prefetch_related('jobs__test_results').all()
    if csearch:
        customers = customers.filter(business_name__icontains=csearch) | \
                    customers.filter(city__icontains=csearch) | \
                    customers.filter(county__icontains=csearch)
    customers = customers.order_by('business_name')

    customer_rows = []
    for c in customers:
        c_jobs       = c.jobs.all()
        active_jobs  = sum(1 for j in c_jobs if j.status in ('pending', 'in_progress'))
        total_jobs   = c_jobs.count()
        last_result  = TestResult.objects.filter(job__customer_ref=c).order_by('-submitted_at').first()
        customer_rows.append({
            'customer':    c,
            'active_jobs': active_jobs,
            'total_jobs':  total_jobs,
            'last_result': last_result,
        })

    return render(request, 'technician/ops_dashboard.html', {
        'tab': tab,
        # jobs
        'jobs': jobs, 'technicians': technicians, 'technicians_json': technicians_json,
        'date_filter': date_filter, 'status_filter': status_filter, 'tech_filter': tech_filter,
        'using_default': using_default,
        'today': timezone.localdate(),
        'total': total, 'unassigned': unassigned, 'completed': completed, 'pending': pending,
        # customers
        'customer_rows': customer_rows, 'csearch': csearch,
        'total_customers': Customer.objects.count(),
        # import
        'import_summary': import_summary,
    })


@role_required('operations', 'manager')
def ops_auto_schedule(request):
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    data      = json.loads(request.body)
    date_str  = data.get('date', '').strip()
    tech_ids  = [int(i) for i in data.get('tech_ids', [])]
    max_trips = int(data.get('max_trips', 8))
    unassign  = bool(data.get('unassign', False))

    if not date_str:
        return JsonResponse({'ok': False, 'error': 'Date is required'})
    if not tech_ids:
        return JsonResponse({'ok': False, 'error': 'Select at least one technician'})

    # Unassign existing trips for selected techs on this date so the algo starts fresh
    if unassign:
        Job.objects.filter(
            scheduled_date=date_str,
            assigned_to__in=tech_ids,
            status__in=['pending', 'in_progress'],
        ).update(assigned_to=None, scheduled_time=None)

    unassigned = list(
        Job.objects.filter(scheduled_date=date_str, status='pending', assigned_to__isnull=True)
        .select_related('customer_ref')
    )
    if not unassigned:
        return JsonResponse({'ok': True, 'assigned': 0, 'skipped': 0,
                             'message': 'No unassigned pending jobs for that date.',
                             'details': []})

    def resolve_coords(job):
        """Return (lat, lng) for a job: job coords → customer coords → county centroid."""
        if job.lat and job.lng:
            return (float(job.lat), float(job.lng))
        if job.customer_ref and job.customer_ref.lat and job.customer_ref.lng:
            return (float(job.customer_ref.lat), float(job.customer_ref.lng))
        return _COUNTY_CENTROIDS.get(job.county, (30.3322, -81.6557))

    job_geo = {job.id: resolve_coords(job) for job in unassigned}

    # Build per-tech state with centroid of existing assignments for this date
    techs = User.objects.filter(id__in=tech_ids).select_related('profile')
    state = {}
    for t in techs:
        existing = list(Job.objects.filter(assigned_to=t, scheduled_date=date_str)
                        .select_related('customer_ref'))
        ex_coords = [resolve_coords(j) for j in existing]
        if ex_coords:
            centroid = (
                sum(c[0] for c in ex_coords) / len(ex_coords),
                sum(c[1] for c in ex_coords) / len(ex_coords),
            )
        else:
            centroid = None  # spread below
        state[t.id] = {
            'user':     t,
            'name':     t.get_full_name() or t.username,
            'counties': set(t.profile.counties or []),
            'existing': len(existing),
            'total':    len(existing),
            'centroid': centroid,
            'new_jobs': [],
        }

    # Spread techs with no existing jobs evenly across the job bounding box (east→west)
    no_centroid = [s for s in state.values() if s['centroid'] is None]
    if no_centroid:
        lats = [c[0] for c in job_geo.values()]
        lngs = [c[1] for c in job_geo.values()]
        mid_lat = (min(lats) + max(lats)) / 2
        min_lng, max_lng = min(lngs), max(lngs)
        n = len(no_centroid)
        for i, s in enumerate(no_centroid):
            frac = (i + 0.5) / n
            s['centroid'] = (mid_lat, min_lng + frac * (max_lng - min_lng))

    # Sort jobs from geographic center outward so edge jobs fill first
    all_lats = [c[0] for c in job_geo.values()]
    all_lngs = [c[1] for c in job_geo.values()]
    geo_center = (sum(all_lats) / len(all_lats), sum(all_lngs) / len(all_lngs))
    remaining = sorted(unassigned, key=lambda j: haversine(*geo_center, *job_geo[j.id]))

    assigned_count = 0
    skipped = []

    for job in remaining:
        jlat, jlng = job_geo[job.id]
        eligible = [
            s for s in state.values()
            if (not job.county or job.county in s['counties'])
            and s['total'] < max_trips
        ]
        if not eligible:
            reason = ('capacity full' if any(job.county in s['counties'] for s in state.values())
                      else f'no tech covers {job.county} county')
            skipped.append({'customer': job.customer, 'reason': reason})
            continue

        # Nearest centroid wins; tiebreak on fewest total jobs
        eligible.sort(key=lambda s: (haversine(s['centroid'][0], s['centroid'][1], jlat, jlng),
                                     s['total']))
        best = eligible[0]
        job.assigned_to = best['user']
        job.save()
        best['new_jobs'].append(job)
        best['total'] += 1

        # Running centroid update
        n = best['total']
        clat, clng = best['centroid']
        best['centroid'] = ((clat * (n - 1) + jlat) / n, (clng * (n - 1) + jlng) / n)
        assigned_count += 1

    # 2-opt route optimization per tech, then assign scheduled times
    from datetime import datetime as dt, time as dtime, timedelta

    def _route_dist(coords):
        return sum(haversine(*coords[i], *coords[i + 1]) for i in range(len(coords) - 1))

    def two_opt(coords):
        best = list(coords)
        improved = True
        while improved:
            improved = False
            for i in range(1, len(best) - 1):
                for j in range(i + 1, len(best)):
                    candidate = best[:i] + best[i:j + 1][::-1] + best[j + 1:]
                    if _route_dist(candidate) < _route_dist(best) - 0.001:
                        best = candidate
                        improved = True
        return best

    details = []
    total_miles_all = 0.0

    for s in state.values():
        if not s['new_jobs']:
            continue

        job_list = s['new_jobs']
        coords   = [job_geo[j.id] for j in job_list]

        if len(coords) >= 3:
            opt_coords = two_opt(coords)
            # Map optimised coords back to jobs (use index to avoid float equality issues)
            coord_index = {coords[i]: i for i in range(len(coords))}
            ordered = [job_list[coord_index[c]] for c in opt_coords]
        else:
            opt_coords = coords
            ordered    = job_list

        route_miles = _route_dist(opt_coords) if len(opt_coords) > 1 else 0.0
        total_miles_all += route_miles

        # Assign scheduled times: 8 am + 45 min per stop
        for idx, job in enumerate(ordered):
            sched = (dt.combine(dt.today(), dtime(8, 0)) + timedelta(minutes=idx * 45)).time()
            job.scheduled_time = sched
            job.save()

        details.append({
            'tech':        s['name'],
            'new':         len(job_list),
            'existing':    s['existing'],
            'total':       s['total'],
            'route_miles': round(route_miles, 1),
            'jobs':        [j.customer for j in ordered],
        })

    return JsonResponse({
        'ok':           True,
        'assigned':     assigned_count,
        'skipped':      len(skipped),
        'skipped_detail': skipped,
        'total_miles':  round(total_miles_all, 1),
        'details':      details,
    })


@role_required('operations', 'manager')
def ops_job_form(request, job_id=None):
    job = get_object_or_404(Job, pk=job_id) if job_id else None
    technicians = User.objects.filter(profile__role='technician').select_related('profile').order_by('first_name')
    customers = Customer.objects.all()

    today = timezone.localdate()
    technicians_json = json.dumps([{
        'id': t.id,
        'name': t.get_full_name() or t.username,
        'counties': getattr(t, 'profile', None) and t.profile.counties or [],
        'is_licensed': getattr(t, 'profile', None) and t.profile.is_licensed or False,
        'license_expires': str(t.profile.license_expires) if getattr(t, 'profile', None) and t.profile.license_expires else '',
    } for t in technicians])

    customers_with_locations = customers.prefetch_related('locations')
    customers_json = json.dumps([{
        'id': c.id, 'business_name': c.business_name, 'contact_name': c.contact_name,
        'phone': c.phone, 'email': c.email, 'website': c.website, 'address': c.address,
        'city': c.city, 'state': c.state, 'county': c.county,
        'zip_code': c.zip_code, 'notes': c.notes,
        'lat': c.lat, 'lng': c.lng,
        'device_lat': c.device_lat, 'device_lng': c.device_lng,
        'locations': [{'id': l.id, 'label': l.label, 'address': l.address,
                       'city': l.city, 'state': l.state, 'county': l.county,
                       'zip_code': l.zip_code, 'lat': l.lat, 'lng': l.lng,
                       'device_lat': l.device_lat, 'device_lng': l.device_lng}
                      for l in c.locations.all()],
    } for c in customers_with_locations])

    if request.method == 'POST':
        p = request.POST

        def flt(f):
            try: return float(p[f]) if p.get(f) else None
            except ValueError: return None

        assigned_id = p.get('assigned_to')
        assigned = User.objects.filter(pk=assigned_id).first() if assigned_id else None
        customer_ref_id = p.get('customer_ref') or None
        customer_ref = Customer.objects.filter(pk=customer_ref_id).first() if customer_ref_id else None
        location_ref_id = p.get('location_ref') or None
        location_ref = CustomerLocation.objects.filter(pk=location_ref_id).first() if location_ref_id else None

        data = dict(
            customer_ref=customer_ref,
            location_ref=location_ref,
            customer=p.get('customer', ''),
            address=p.get('address', ''),
            contact=p.get('contact', ''),
            phone=p.get('phone', ''),
            state=p.get('state', 'FL'),
            county=p.get('county', ''),
            scheduled_date=p.get('scheduled_date'),
            scheduled_time=p.get('scheduled_time'),
            status=p.get('status', 'pending'),
            assigned_to=assigned,
            device_type=p.get('device_type', 'RPZ'),
            device_size=p.get('device_size', ''),
            device_make=p.get('device_make', ''),
            device_model=p.get('device_model', ''),
            serial=p.get('serial', ''),
            device_notes=p.get('device_notes', ''),
            lat=flt('lat'), lng=flt('lng'),
            device_lat=flt('device_lat'), device_lng=flt('device_lng'),
            notes=p.get('notes', ''),
        )

        if job:
            for k, v in data.items():
                setattr(job, k, v)
            job.save()
        else:
            job = Job.objects.create(**data)

        return redirect('ops_dashboard')

    return render(request, 'technician/ops_job_form.html', {
        'job': job,
        'technicians': technicians,
        'customers': customers,
        'customers_json': customers_json,
        'technicians_json': technicians_json,
        'DEVICE_TYPES': Job.DEVICE_TYPES,
        'STATUS_CHOICES': Job.STATUS_CHOICES,
        'US_STATES': US_STATES,
        'FL_COUNTIES': FL_COUNTIES,
    })



def _sync_primary_location(customer):
    """Keep a 'Primary Address' CustomerLocation in sync with the customer's billing address."""
    if not customer.address:
        return
    loc, _ = CustomerLocation.objects.get_or_create(
        customer=customer, label='Primary Address',
    )
    loc.address    = customer.address
    loc.city       = customer.city
    loc.state      = customer.state
    loc.county     = customer.county
    loc.zip_code   = customer.zip_code
    loc.lat        = customer.lat
    loc.lng        = customer.lng
    loc.device_lat = customer.device_lat
    loc.device_lng = customer.device_lng
    loc.save()


@role_required('operations', 'manager')
def ops_customer_form(request, customer_id=None):
    customer = get_object_or_404(Customer, pk=customer_id) if customer_id else None
    error = None

    if request.method == 'POST':
        p = request.POST
        business_name = p.get('business_name', '').strip()
        if not business_name:
            error = 'Business name is required.'
        else:
            if not customer:
                customer = Customer()
            customer.business_name = business_name
            customer.contact_name  = p.get('contact_name', '').strip()
            customer.phone         = p.get('phone', '').strip()
            customer.email         = p.get('email', '').strip()
            customer.website       = p.get('website', '').strip()
            customer.address       = p.get('address', '').strip()
            customer.city          = p.get('city', '').strip()
            customer.state         = p.get('state', 'FL')
            customer.county        = p.get('county', '').strip()
            customer.zip_code      = p.get('zip_code', '').strip()
            customer.notes         = p.get('notes', '').strip()

            def _pflt(f):
                try: return float(p[f]) if p.get(f) else None
                except ValueError: return None

            customer.lat        = _pflt('lat')
            customer.lng        = _pflt('lng')
            customer.device_lat = _pflt('device_lat')
            customer.device_lng = _pflt('device_lng')
            customer.save()
            _sync_primary_location(customer)
            return redirect('/tech/ops/?tab=customers')

    job_history = []
    locations = []
    location_filter = None
    if customer:
        locations = list(customer.locations.all())
        loc_filter_id = request.GET.get('location') or None
        location_filter = next((l for l in locations if str(l.id) == loc_filter_id), None) if loc_filter_id else None
        qs = Job.objects.filter(customer_ref=customer)\
                        .select_related('location_ref')\
                        .prefetch_related('test_results')\
                        .order_by('-scheduled_date')
        if location_filter:
            qs = qs.filter(location_ref=location_filter)
        job_history = list(qs[:20])

    return render(request, 'technician/ops_customer_form.html', {
        'customer':        customer,
        'job_history':     job_history,
        'locations':       locations,
        'location_filter': location_filter,
        'US_STATES':       US_STATES,
        'FL_COUNTIES':     FL_COUNTIES,
        'error':           error,
    })


@role_required('operations', 'manager')
def customer_save(request, customer_id=None):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    customer = get_object_or_404(Customer, pk=customer_id) if customer_id else Customer()
    customer.business_name = data.get('business_name', '').strip()
    if not customer.business_name:
        return JsonResponse({'error': 'Business name is required'}, status=400)
    customer.contact_name = data.get('contact_name', '').strip()
    customer.phone = data.get('phone', '').strip()
    customer.email = data.get('email', '').strip()
    customer.website = data.get('website', '').strip()
    customer.address = data.get('address', '').strip()
    customer.city = data.get('city', '').strip()
    customer.state = data.get('state', 'FL').strip()
    customer.county = data.get('county', '').strip()
    customer.zip_code = data.get('zip_code', '').strip()
    customer.notes = data.get('notes', '').strip()

    def _flt(key):
        try: return float(data[key]) if data.get(key) is not None else None
        except (ValueError, TypeError): return None

    customer.lat = _flt('lat')
    customer.lng = _flt('lng')
    customer.device_lat = _flt('device_lat')
    customer.device_lng = _flt('device_lng')
    customer.save()
    _sync_primary_location(customer)

    locs = [{'id': l.id, 'label': l.label, 'address': l.address,
              'city': l.city, 'state': l.state, 'county': l.county,
              'zip_code': l.zip_code, 'lat': l.lat, 'lng': l.lng,
              'device_lat': l.device_lat, 'device_lng': l.device_lng}
             for l in customer.locations.all()]

    return JsonResponse({'ok': True, 'customer': {
        'id': customer.id, 'business_name': customer.business_name,
        'contact_name': customer.contact_name, 'phone': customer.phone,
        'email': customer.email, 'website': customer.website, 'address': customer.address,
        'city': customer.city, 'state': customer.state,
        'county': customer.county, 'zip_code': customer.zip_code,
        'notes': customer.notes,
        'lat': customer.lat, 'lng': customer.lng,
        'device_lat': customer.device_lat, 'device_lng': customer.device_lng,
        'locations': locs,
    }})


@role_required('operations', 'manager')
def location_save(request, customer_id, location_id=None):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    customer = get_object_or_404(Customer, pk=customer_id)
    loc = get_object_or_404(CustomerLocation, pk=location_id, customer=customer) \
          if location_id else CustomerLocation(customer=customer)

    loc.label = data.get('label', 'Main').strip() or 'Main'
    loc.address = data.get('address', '').strip()
    loc.city = data.get('city', '').strip()
    loc.state = data.get('state', 'FL').strip()
    loc.county = data.get('county', '').strip()
    loc.zip_code = data.get('zip_code', '').strip()

    def _flt(key):
        try: return float(data[key]) if data.get(key) is not None else None
        except (ValueError, TypeError): return None

    loc.lat = _flt('lat')
    loc.lng = _flt('lng')
    loc.device_lat = _flt('device_lat')
    loc.device_lng = _flt('device_lng')
    loc.save()

    return JsonResponse({'ok': True, 'location': {
        'id': loc.id, 'label': loc.label, 'address': loc.address,
        'city': loc.city, 'state': loc.state, 'county': loc.county,
        'zip_code': loc.zip_code, 'lat': loc.lat, 'lng': loc.lng,
        'device_lat': loc.device_lat, 'device_lng': loc.device_lng,
    }})


@role_required('operations', 'manager')
def location_delete(request, location_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    loc = get_object_or_404(CustomerLocation, pk=location_id)
    loc.delete()
    return JsonResponse({'ok': True})


# ── Temporary: seed historical job/test data on Render ────────────────────────

def seed_history(request):
    import decimal
    import datetime as dt
    from django.contrib.auth.models import User

    TECH_MAP = {
        'technician': User.objects.filter(username='technician').first(),
        'mthompson':  User.objects.filter(username='mthompson').first(),
        'rdiaz':      User.objects.filter(username='rdiaz').first(),
    }

    def _c(val):
        return decimal.Decimal(str(val)) if val is not None else None

    def _cust(name):
        return Customer.objects.filter(business_name=name).first()

    HIST = [
        {'n': 'Riverside Auto Wash',          'tech': 'technician', 'ini': 'JS', 'd': dt.date(2025, 3, 10),  't': dt.time(8,  0), 'dt': 'RPZ',  'ds': '1"',   'dm': 'Watts',   'dmo': '009',     'ser': 'W2204-8871',  'iy': 2018, 'cv1': 'closed', 'p1': 10.2, 'cv2': 'closed', 'p2': 9.1, 'rv': 'opened_ok', 'rp': 2.1, 'lp': 82.0},
        {'n': 'Sunshine Apartments',           'tech': 'mthompson',  'ini': 'MT', 'd': dt.date(2025, 4, 7),   't': dt.time(9, 15), 'dt': 'DCVA', 'ds': '3/4"', 'dm': 'Febco',   'dmo': '850',     'ser': 'F2019-3341',  'iy': 2019, 'cv1': 'closed', 'p1': 11.0, 'cv2': 'closed', 'p2': 9.8, 'rv': '',          'rp': None,'lp': 78.0},
        {'n': 'Orange Park Commons HOA',       'tech': 'rdiaz',      'ini': 'RD', 'd': dt.date(2025, 4, 21),  't': dt.time(10,30), 'dt': 'RPZ',  'ds': '2"',   'dm': 'Wilkins', 'dmo': '975XL',   'ser': 'WK2021-6612', 'iy': 2021, 'cv1': 'closed', 'p1': 10.8, 'cv2': 'closed', 'p2': 9.3, 'rv': 'opened_ok', 'rp': 2.3, 'lp': 85.0},
        {'n': 'Fleming Island Medical Center', 'tech': 'technician', 'ini': 'JS', 'd': dt.date(2025, 5, 15),  't': dt.time(11,45), 'dt': 'RPZ',  'ds': '1.5"', 'dm': 'Ames',    'dmo': '4000SS',  'ser': 'A2022-1197',  'iy': 2022, 'cv1': 'closed', 'p1': 11.2, 'cv2': 'closed', 'p2': 9.7, 'rv': 'opened_ok', 'rp': 2.0, 'lp': 80.0},
        {'n': 'St. Johns County Rec Center',   'tech': 'mthompson',  'ini': 'MT', 'd': dt.date(2025, 6, 9),   't': dt.time(13, 0), 'dt': 'PVB',  'ds': '1"',   'dm': 'Watts',   'dmo': '800M4',   'ser': 'W2020-5589',  'iy': 2020, 'cv1': 'closed', 'p1': 10.5, 'cv2': '',       'p2': None,'rv': 'opened_ok', 'rp': 1.8, 'lp': 76.0},
        {'n': 'Ponte Vedra Beach Club',        'tech': 'rdiaz',      'ini': 'RD', 'd': dt.date(2025, 7, 22),  't': dt.time(14, 0), 'dt': 'DCVA', 'ds': '1"',   'dm': 'Febco',   'dmo': '860',     'ser': 'F2023-8823',  'iy': 2023, 'cv1': 'closed', 'p1': 10.9, 'cv2': 'closed', 'p2': 9.5, 'rv': '',          'rp': None,'lp': 88.0},
        {'n': 'Atlantic Beach City Hall',      'tech': 'technician', 'ini': 'JS', 'd': dt.date(2025, 8, 11),  't': dt.time(9,  0), 'dt': 'RPZ',  'ds': '1"',   'dm': 'Watts',   'dmo': '909',     'ser': 'W2021-2214',  'iy': 2021, 'cv1': 'closed', 'p1': 10.3, 'cv2': 'closed', 'p2': 9.0, 'rv': 'opened_ok', 'rp': 2.2, 'lp': 81.0},
        {'n': 'Neptune Beach HOA',             'tech': 'mthompson',  'ini': 'MT', 'd': dt.date(2025, 9, 18),  't': dt.time(10, 0), 'dt': 'PVB',  'ds': '3/4"', 'dm': 'Wilkins', 'dmo': '720A',    'ser': 'WK2019-9901', 'iy': 2019, 'cv1': 'closed', 'p1': 10.7, 'cv2': '',       'p2': None,'rv': 'opened_ok', 'rp': 1.9, 'lp': 77.0},
        {'n': 'Mandarin Presbyterian Church',  'tech': 'rdiaz',      'ini': 'RD', 'd': dt.date(2025, 10, 6),  't': dt.time(11, 0), 'dt': 'DCVA', 'ds': '3/4"', 'dm': 'Ames',    'dmo': '2000SS',  'ser': 'A2020-7743',  'iy': 2020, 'cv1': 'closed', 'p1': 11.1, 'cv2': 'closed', 'p2': 9.4, 'rv': '',          'rp': None,'lp': 79.0},
        {'n': 'Baymeadows Plaza',              'tech': 'technician', 'ini': 'JS', 'd': dt.date(2025, 11, 14), 't': dt.time(8, 30), 'dt': 'RPZ',  'ds': '2"',   'dm': 'Febco',   'dmo': '880V',    'ser': 'F2022-4456',  'iy': 2022, 'cv1': 'closed', 'p1': 10.6, 'cv2': 'closed', 'p2': 9.2, 'rv': 'opened_ok', 'rp': 2.4, 'lp': 84.0},
        {'n': 'Riverside Auto Wash',          'tech': 'technician', 'ini': 'JS', 'd': dt.date(2026, 1, 13),  't': dt.time(8,  0), 'dt': 'RPZ',  'ds': '1"',   'dm': 'Watts',   'dmo': '009',     'ser': 'W2204-8871',  'iy': 2018, 'cv1': 'closed', 'p1': 10.4, 'cv2': 'closed', 'p2': 9.0, 'rv': 'opened_ok', 'rp': 2.2, 'lp': 83.0},
        {'n': 'Fleming Island Medical Center', 'tech': 'technician', 'ini': 'JS', 'd': dt.date(2026, 2, 10),  't': dt.time(11,45), 'dt': 'RPZ',  'ds': '1.5"', 'dm': 'Ames',    'dmo': '4000SS',  'ser': 'A2022-1197',  'iy': 2022, 'cv1': 'closed', 'p1': 11.0, 'cv2': 'closed', 'p2': 9.6, 'rv': 'opened_ok', 'rp': 2.1, 'lp': 80.0},
        {'n': 'Atlantic Beach City Hall',      'tech': 'technician', 'ini': 'JS', 'd': dt.date(2026, 3, 17),  't': dt.time(9,  0), 'dt': 'RPZ',  'ds': '1"',   'dm': 'Watts',   'dmo': '909',     'ser': 'W2021-2214',  'iy': 2021, 'cv1': 'closed', 'p1': 10.8, 'cv2': 'closed', 'p2': 9.3, 'rv': 'opened_ok', 'rp': 2.3, 'lp': 82.0},
    ]

    PENDING = [
        {'n': 'Sunshine Apartments',          'd': dt.date(2026, 5, 5),  't': dt.time(9, 15), 'dt': 'DCVA', 'ds': '3/4"', 'dm': 'Febco',   'dmo': '850',    'ser': 'F2019-3341'},
        {'n': 'Orange Park Commons HOA',      'd': dt.date(2026, 5, 8),  't': dt.time(10,30), 'dt': 'RPZ',  'ds': '2"',   'dm': 'Wilkins', 'dmo': '975XL',  'ser': 'WK2021-6612'},
        {'n': 'St. Johns County Rec Center',  'd': dt.date(2026, 5, 12), 't': dt.time(13, 0), 'dt': 'PVB',  'ds': '1"',   'dm': 'Watts',   'dmo': '800M4',  'ser': 'W2020-5589'},
        {'n': 'Ponte Vedra Beach Club',       'd': dt.date(2026, 5, 15), 't': dt.time(14, 0), 'dt': 'DCVA', 'ds': '1"',   'dm': 'Febco',   'dmo': '860',    'ser': 'F2023-8823'},
        {'n': 'Neptune Beach HOA',            'd': dt.date(2026, 5, 19), 't': dt.time(10, 0), 'dt': 'PVB',  'ds': '3/4"', 'dm': 'Wilkins', 'dmo': '720A',   'ser': 'WK2019-9901'},
        {'n': 'Mandarin Presbyterian Church', 'd': dt.date(2026, 5, 27), 't': dt.time(11, 0), 'dt': 'DCVA', 'ds': '3/4"', 'dm': 'Ames',    'dmo': '2000SS', 'ser': 'A2020-7743'},
        {'n': 'Baymeadows Plaza',             'd': dt.date(2026, 6, 3),  't': dt.time(8, 30), 'dt': 'RPZ',  'ds': '2"',   'dm': 'Febco',   'dmo': '880V',   'ser': 'F2022-4456'},
    ]

    created_jobs = 0
    created_results = 0

    # Historical + 2026 completed
    if not Job.objects.filter(scheduled_date__year=2025).exists() or \
       not Job.objects.filter(scheduled_date__year=2026, status='completed').exists():
        for j in HIST:
            cust = _cust(j['n'])
            tech = TECH_MAP.get(j['tech'])
            job = Job.objects.create(
                customer_ref=cust,
                customer=j['n'],
                address=cust.address if cust else '',
                contact=cust.contact_name if cust else '',
                phone=cust.phone if cust else '',
                state='FL', county=cust.county if cust else '',
                scheduled_date=j['d'], scheduled_time=j['t'],
                status='completed', assigned_to=tech,
                device_type=j['dt'], device_size=j['ds'],
                device_make=j['dm'], device_model=j['dmo'], serial=j['ser'],
                lat=cust.lat if cust else None, lng=cust.lng if cust else None,
                device_lat=cust.device_lat if cust else None, device_lng=cust.device_lng if cust else None,
            )
            TestResult.objects.create(
                job=job, customer=j['n'], address=job.address,
                device_type=j['dt'], device_size=j['ds'],
                manufacturer=j['dm'], model=j['dmo'], serial=j['ser'],
                install_year=j['iy'], test_date=j['d'], test_time=j['t'],
                cv1_result=j['cv1'], cv1_psi=_c(j['p1']),
                cv2_result=j['cv2'], cv2_psi=_c(j['p2']),
                rv_result=j['rv'], rv_psi=_c(j['rp']),
                line_psi=_c(j['lp']),
                overall_result='pass', technician_initials=j['ini'], submitted_by=tech,
            )
            created_jobs += 1
            created_results += 1

    # Unassigned pending
    if not Job.objects.filter(scheduled_date__year=2026, assigned_to__isnull=True).exists():
        for j in PENDING:
            cust = _cust(j['n'])
            Job.objects.create(
                customer_ref=cust,
                customer=j['n'],
                address=cust.address if cust else '',
                contact=cust.contact_name if cust else '',
                phone=cust.phone if cust else '',
                state='FL', county=cust.county if cust else '',
                scheduled_date=j['d'], scheduled_time=j['t'],
                status='pending', assigned_to=None,
                device_type=j['dt'], device_size=j['ds'],
                device_make=j['dm'], device_model=j['dmo'], serial=j['ser'],
                lat=cust.lat if cust else None, lng=cust.lng if cust else None,
                device_lat=cust.device_lat if cust else None, device_lng=cust.device_lng if cust else None,
            )
            created_jobs += 1

    return JsonResponse({'ok': True, 'jobs_created': created_jobs, 'results_created': created_results})


# ── Temporary: seed / repair all demo users ──────────────────────────────────

def seed_users(request):
    import datetime
    from django.contrib.auth.models import User
    from .models import UserProfile

    DEMO_USERS = [
        # username, password, first, last, role, counties, is_licensed, license_expires
        ('technician', 'tech123',      'John',   'Smith',    'technician', ['Duval','Clay','St. Johns','Nassau'],  True,  datetime.date(2027, 6, 30)),
        ('mthompson',  'mthompson123', 'Marcus', 'Thompson', 'technician', ['Duval','Clay','St. Johns','Flagler'], True,  datetime.date(2026, 8, 15)),
        ('rdiaz',      'rdiaz123',     'Rosa',   'Diaz',     'technician', ['Duval','Clay','St. Johns','Alachua'], True,  datetime.date(2027, 3, 15)),
        ('operations', 'ops123',       'Sarah',  'Johnson',  'operations', [], False, None),
        ('manager',    'mgr123',       'Robert', 'Wolf',     'manager',    [], False, None),
        ('admin',      'admin123',     'Admin',  'Wolf',     'admin',      [], False, None),
        ('customer',   'cust123',      'James',  'Wilson',   'customer',   [], False, None),
    ]

    created_users = []
    updated_users = []

    for username, password, first, last, role, counties, is_licensed, license_expires in DEMO_USERS:
        user, created = User.objects.get_or_create(username=username)
        user.set_password(password)
        user.first_name = first
        user.last_name = last
        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': role})
        profile.role = role
        profile.counties = counties
        profile.is_licensed = is_licensed
        profile.license_expires = license_expires
        profile.save()

        if created:
            created_users.append(username)
        else:
            updated_users.append(username)

    return JsonResponse({'ok': True, 'created': created_users, 'updated': updated_users})


# ── Temporary: repair job/result assignments for historical data ──────────────

def reassign_history(request):
    import datetime as dt
    from django.contrib.auth.models import User

    TECH_MAP = {
        'technician': User.objects.filter(username='technician').first(),
        'mthompson':  User.objects.filter(username='mthompson').first(),
        'rdiaz':      User.objects.filter(username='rdiaz').first(),
    }

    ASSIGNMENTS = [
        ('Riverside Auto Wash',          dt.date(2025, 3, 10),  'technician'),
        ('Sunshine Apartments',           dt.date(2025, 4, 7),   'mthompson'),
        ('Orange Park Commons HOA',       dt.date(2025, 4, 21),  'rdiaz'),
        ('Fleming Island Medical Center', dt.date(2025, 5, 15),  'technician'),
        ('St. Johns County Rec Center',   dt.date(2025, 6, 9),   'mthompson'),
        ('Ponte Vedra Beach Club',        dt.date(2025, 7, 22),  'rdiaz'),
        ('Atlantic Beach City Hall',      dt.date(2025, 8, 11),  'technician'),
        ('Neptune Beach HOA',             dt.date(2025, 9, 18),  'mthompson'),
        ('Mandarin Presbyterian Church',  dt.date(2025, 10, 6),  'rdiaz'),
        ('Baymeadows Plaza',              dt.date(2025, 11, 14), 'technician'),
        ('Riverside Auto Wash',           dt.date(2026, 1, 13),  'technician'),
        ('Fleming Island Medical Center', dt.date(2026, 2, 10),  'technician'),
        ('Atlantic Beach City Hall',      dt.date(2026, 3, 17),  'technician'),
    ]

    updated_jobs = 0
    updated_results = 0
    missing = []

    for name, date, tech_key in ASSIGNMENTS:
        tech = TECH_MAP.get(tech_key)
        if not tech:
            missing.append(tech_key)
            continue
        job = Job.objects.filter(customer=name, scheduled_date=date).first()
        if not job:
            missing.append(f'job:{name}:{date}')
            continue
        job.assigned_to = tech
        job.save(update_fields=['assigned_to'])
        updated_jobs += 1
        for result in job.test_results.filter(submitted_by__isnull=True):
            result.submitted_by = tech
            result.save(update_fields=['submitted_by'])
            updated_results += 1

    return JsonResponse({
        'ok': True,
        'updated_jobs': updated_jobs,
        'updated_results': updated_results,
        'missing': missing,
    })


# ── Temporary: populate demo utility account numbers on TestResults ───────────

def seed_utility_fields(request):
    # Maps customer name → (utility_account_number, county) for all sample customers.
    # Account number formats mirror real utilities: JEA for Duval, CCUA for Clay,
    # SJC for St. Johns.
    ACCT_MAP = {
        'Riverside Auto Wash':          'JEA-4521-8871',
        'Sunshine Apartments':           'JEA-4521-8872',
        'Atlantic Beach City Hall':      'JEA-4521-8873',
        'Neptune Beach HOA':             'JEA-4521-8874',
        'Mandarin Presbyterian Church':  'JEA-4521-8875',
        'Baymeadows Plaza':              'JEA-4521-8876',
        'Orange Park Commons HOA':       'CCUA-20065-001',
        'Fleming Island Medical Center': 'CCUA-20003-002',
        'St. Johns County Rec Center':   'SJC-32259-001',
        'Ponte Vedra Beach Club':        'SJC-32082-002',
    }
    updated = 0
    for name, acct in ACCT_MAP.items():
        count = TestResult.objects.filter(customer=name, utility_account_number='').update(
            utility_account_number=acct
        )
        updated += count
    return JsonResponse({'ok': True, 'updated': updated})


# ── Temporary: reseed customer coordinates ────────────────────────────────────

def reseed_customer_coords(request):
    COORDS = {
        'Riverside Auto Wash':          {'lat': 30.3149,  'lng': -81.6693,  'device_lat': 30.31498,  'device_lng': -81.66915},
        'Sunshine Apartments':           {'lat': 30.3220,  'lng': -81.6580,  'device_lat': 30.32208,  'device_lng': -81.65785},
        'Orange Park Commons HOA':       {'lat': 30.1654,  'lng': -81.7065,  'device_lat': 30.16550,  'device_lng': -81.70635},
        'Fleming Island Medical Center': {'lat': 30.1010,  'lng': -81.7143,  'device_lat': 30.10108,  'device_lng': -81.71415},
        'St. Johns County Rec Center':   {'lat': 30.1580,  'lng': -81.6043,  'device_lat': 30.15808,  'device_lng': -81.60415},
        'Ponte Vedra Beach Club':        {'lat': 30.2394,  'lng': -81.3883,  'device_lat': 30.23948,  'device_lng': -81.38815},
        'Atlantic Beach City Hall':      {'lat': 30.3371,  'lng': -81.3996,  'device_lat': 30.33718,  'device_lng': -81.39945},
        'Neptune Beach HOA':             {'lat': 30.3127,  'lng': -81.4027,  'device_lat': 30.31278,  'device_lng': -81.40255},
        'Mandarin Presbyterian Church':  {'lat': 30.1580,  'lng': -81.6243,  'device_lat': 30.15808,  'device_lng': -81.62415},
        'Baymeadows Plaza':              {'lat': 30.2347,  'lng': -81.5513,  'device_lat': 30.23478,  'device_lng': -81.55115},
    }
    updated = []
    for name, coords in COORDS.items():
        c = Customer.objects.filter(business_name=name).first()
        if c:
            for k, v in coords.items():
                setattr(c, k, v)
            c.save()
            updated.append(name)
    return JsonResponse({'ok': True, 'updated': updated})


@role_required('operations', 'manager')
def geocode_customers(request):
    """Geocode Customer records missing lat/lng via Nominatim (1 req/sec, max 20 per call).

    Optional GET param `date` (YYYY-MM-DD): limits to customers linked to jobs on that date.
    Without a date, geocodes all customers missing coords.
    """
    import traceback as tb
    try:
        BATCH = 20
        date_str = request.GET.get('date', '').strip()

        if date_str:
            customer_ids = Job.objects.filter(
                scheduled_date=date_str,
                customer_ref__isnull=False,
            ).values_list('customer_ref_id', flat=True).distinct()
            candidates = list(Customer.objects.filter(pk__in=customer_ids))
        else:
            candidates = list(Customer.objects.all())

        missing  = [c for c in candidates if not c.lat or not c.lng]
        remaining = len(missing)
        skipped  = len(candidates) - remaining
        geocoded, failed = [], []
        for c in missing[:BATCH]:
            result = geocode_nominatim(c.address, c.city, c.state or 'FL')
            if result:
                c.lat, c.lng = result
                c.save(update_fields=['lat', 'lng'])
                geocoded.append(c.business_name)
            else:
                failed.append(c.business_name)
            time.sleep(1.1)
        return JsonResponse({
            'ok':            True,
            'geocoded':      len(geocoded),
            'failed':        len(failed),
            'skipped':       skipped,
            'remaining':     max(0, remaining - BATCH),
            'geocoded_names': geocoded,
            'failed_names':  failed,
        })
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc), 'trace': tb.format_exc()}, status=500)


def seed_customer_websites(request):
    """Idempotent: set website (and email when missing) on existing customers from researched data."""
    WEBSITE_DATA = [
        (4,  'https://www.flemingislandsurgerycenter.com/', ''),
        (5,  'https://www.sjcfl.us/departments/parks-recreation/', ''),
        (6,  'https://www.pontevedra.com/', ''),
        (7,  'https://www.coab.us/', ''),
        (9,  'https://mandarinpres.com/', ''),
        (13, 'https://murrayhilltheatre.com/', ''),
        (15, 'https://www.regencyplaceapts.com', ''),
        (17, 'https://www.baptistjax.com/locations/baptist-medical-center-south', ''),
        (19, 'https://www.hilton.com/en/hotels/ustsmdt-doubletree-st-augustine-historic-district/', ''),
        (20, 'https://www.golfwgv.com/', ''),
        (21, 'https://www.stjohnsgolf.com/', ''),
        (22, 'https://www.hcafloridahealthcare.com/locations/orange-park-hospital', ''),
        (25, 'https://www.ihg.com/hotelindigo/hotels/us/en/jacksonville/jaxin/hoteldetail', ''),
        (26, 'https://www.hcafloridahealthcare.com/locations/memorial-hospital', ''),
        (27, 'https://www.jacksonvillezoo.org/', ''),
        (28, 'https://www.thestrandjacksonville.com/', ''),
        (29, 'https://www.autonationfordjacksonville.com/', ''),
        (30, 'https://www.publix.com/locations/1022-mandarin-oaks-shopping-center', ''),
        (31, 'https://www.marriott.com/en-us/hotels/jaxfl-marriott-jacksonville/', ''),
        (32, 'https://fcymca.org/locations/', ''),
        (33, 'https://tpc.com/sawgrass/', ''),
        (34, 'https://www.nocatee.com/town-center', ''),
        (36, 'https://www.premiumoutlets.com/outlet/st-augustine', ''),
        (37, 'https://www.oneclay.net/o/mhs/', ''),
        (39, 'https://www.claycountygov.com/', ''),
        (41, 'https://www.flyjacksonville.com/jaa/', 'jaxactionline@flyjax.com'),
        (42, 'https://ortegariverclub.net/', ''),
        (45, 'https://www.publix.com/locations/1214-atlantic-plaza', ''),
        (46, 'https://www.deerwoodclub.com/', 'ariley@deerwoodclub.com'),
        (47, 'https://www.walmart.com/store/1082-jacksonville-fl', ''),
        (48, 'https://www.hilton.com/en/hotels/sgjvbhx-hampton-suites-st-augustine-vilano-beach/', ''),
        (49, 'https://www.palenciaclub.com/', ''),
        (50, 'https://www.nps.gov/casa/index.htm', ''),
        (52, 'https://www.hcafloridahealthcare.com/locations/orange-park-hospital', ''),
    ]
    updated = 0
    for cid, website, email in WEBSITE_DATA:
        c = Customer.objects.filter(pk=cid).first()
        if c:
            c.website = website
            if email and not c.email:
                c.email = email
            c.save(update_fields=['website', 'email'])
            updated += 1
    return JsonResponse({'ok': True, 'updated': updated})


def seed_upcoming_jobs(request):
    """Create 45 pending jobs across May 6-8 2026 in Duval, St. Johns, Clay counties."""
    if Job.objects.filter(scheduled_date='2026-05-06', customer='Riverside Towers Apartments').exists():
        return JsonResponse({'ok': True, 'msg': 'Already seeded — skipping'})

    # (customer, address, city, county, date, time, device_type, device_size)
    JOBS = [
        # ── May 6 ─────────────────────────────────────────────────────────────
        ('Riverside Towers Apartments',   '1500 Riverside Ave',          'Jacksonville',      'Duval',     '2026-05-06', '08:00', 'RPZ',  '1"'),
        ('Baymeadows Corporate Center',   '7545 Baymeadows Way',         'Jacksonville',      'Duval',     '2026-05-06', '08:30', 'DCVA', '2"'),
        ('Murray Hill Theatre',           '932 Edgewood Ave S',          'Jacksonville',      'Duval',     '2026-05-06', '09:00', 'RPZ',  '3/4"'),
        ('Main Street Hotel Jacksonville','565 Main St',                 'Jacksonville',      'Duval',     '2026-05-06', '09:30', 'RPZ',  '2"'),
        ('Regency Square Apartments',     '8800 Baymeadows Rd',          'Jacksonville',      'Duval',     '2026-05-06', '10:00', 'DCVA', '1"'),
        ('Gateway Town Center',           '5210 Norwood Ave',            'Jacksonville',      'Duval',     '2026-05-06', '10:30', 'RPZ',  '1-1/2"'),
        ('Baptist Medical Center South',  '14550 St. Augustine Rd',      'Jacksonville',      'Duval',     '2026-05-06', '11:00', 'RPZ',  '2"'),
        ('Avenues Walk Apartments',       '10300 Southside Blvd',        'Jacksonville',      'Duval',     '2026-05-06', '11:30', 'DCVA', '1"'),
        ('St. Augustine Marriott',        '116 San Marco Ave',           'St. Augustine',     'St. Johns', '2026-05-06', '12:00', 'RPZ',  '1"'),
        ('World Golf Village Resort',     '2 World Golf Pl',             'St. Augustine',     'St. Johns', '2026-05-06', '12:30', 'RPZ',  '1-1/2"'),
        ('Ponte Vedra Beach Club',        '100 Ponte Vedra Blvd',        'Ponte Vedra Beach', 'St. Johns', '2026-05-06', '13:00', 'RPZ',  '1"'),
        ('St. Johns Golf & Country Club', '775 Hana Rd',                 'St. Augustine',     'St. Johns', '2026-05-06', '13:30', 'DCVA', '1"'),
        ('Orange Park Medical Center',    '2001 Kingsley Ave',           'Orange Park',       'Clay',      '2026-05-06', '14:00', 'DCVA', '1-1/2"'),
        ('Fleming Island Town Center',    '1570 Town Center Blvd',       'Fleming Island',    'Clay',      '2026-05-06', '14:30', 'DCVA', '2"'),
        ('Oakleaf Town Center',           '9735 Crosshill Blvd',         'Jacksonville',      'Clay',      '2026-05-06', '15:00', 'RPZ',  '1"'),
        # ── May 7 ─────────────────────────────────────────────────────────────
        ('Hotel Indigo Jacksonville',     '9840 Tapestry Park Cir',      'Jacksonville',      'Duval',     '2026-05-07', '08:00', 'RPZ',  '1"'),
        ('Memorial Hospital Jacksonville','3625 University Blvd S',      'Jacksonville',      'Duval',     '2026-05-07', '08:30', 'DCVA', '3"'),
        ('Jacksonville Zoo & Gardens',    '370 Zoo Pkwy',                'Jacksonville',      'Duval',     '2026-05-07', '09:00', 'RPZ',  '2"'),
        ('The Strand Apartments',         '4700 Beach Blvd',             'Jacksonville',      'Duval',     '2026-05-07', '09:30', 'RPZ',  '1"'),
        ('AutoNation Ford Jacksonville',  '10680 Philips Hwy',           'Jacksonville',      'Duval',     '2026-05-07', '10:00', 'DCVA', '1-1/2"'),
        ('Mandarin Publix',               '11700 San Jose Blvd',         'Jacksonville',      'Duval',     '2026-05-07', '10:30', 'RPZ',  '3/4"'),
        ('Town Center Marriott',          '4670 Town Center Pkwy',       'Jacksonville',      'Duval',     '2026-05-07', '11:00', 'DCVA', '2"'),
        ('YMCA Southside',                '11111 Old St Augustine Rd',   'Jacksonville',      'Duval',     '2026-05-07', '11:30', 'RPZ',  '1"'),
        ('TPC Sawgrass',                  '110 Championship Way',        'Ponte Vedra Beach', 'St. Johns', '2026-05-07', '12:00', 'RPZ',  '1-1/2"'),
        ('Nocatee Town Center',           '250 Town Center Blvd',        'Ponte Vedra',       'St. Johns', '2026-05-07', '12:30', 'RPZ',  '1"'),
        ('Vilano Beach Motel',            '750 A1A Beach Blvd',          'St. Augustine',     'St. Johns', '2026-05-07', '13:00', 'RPZ',  '3/4"'),
        ('St. Augustine Premium Outlets', '2700 State Rd 16',            'St. Augustine',     'St. Johns', '2026-05-07', '13:30', 'DCVA', '1"'),
        ('Middleburg High School',        '4250 Section St',             'Middleburg',        'Clay',      '2026-05-07', '14:00', 'DCVA', '1"'),
        ('Orange Park Brewing Company',   '148 Blanding Blvd',           'Orange Park',       'Clay',      '2026-05-07', '14:30', 'RPZ',  '3/4"'),
        ('Clay County Administration',    '477 Houston St',              'Green Cove Springs','Clay',      '2026-05-07', '15:00', 'RPZ',  '1"'),
        # ── May 8 ─────────────────────────────────────────────────────────────
        ('Deerwood Park Office Complex',  '10150 Deerwood Park Blvd',    'Jacksonville',      'Duval',     '2026-05-08', '08:00', 'DCVA', '2"'),
        ('Jacksonville Executive Airport','14201 Pecan Park Rd',         'Jacksonville',      'Duval',     '2026-05-08', '08:30', 'RPZ',  '1-1/2"'),
        ('Ortega River Club',             '4457 Ortega Blvd',            'Jacksonville',      'Duval',     '2026-05-08', '09:00', 'RPZ',  '1"'),
        ('River City Brewing Company',    '835 Museum Cir',              'Jacksonville',      'Duval',     '2026-05-08', '09:30', 'RPZ',  '1"'),
        ('Lakeshore Inn',                 '8001 Lakeshore Dr',           'Jacksonville',      'Duval',     '2026-05-08', '10:00', 'DCVA', '1"'),
        ('Atlantic Beach Publix',         '395 Atlantic Blvd',           'Atlantic Beach',    'Duval',     '2026-05-08', '10:30', 'RPZ',  '3/4"'),
        ('Deerwood Country Club',         '10239 Golf Club Dr',          'Jacksonville',      'Duval',     '2026-05-08', '11:00', 'RPZ',  '2"'),
        ('Southside Walmart Supercenter', '10991 San Jose Blvd',         'Jacksonville',      'Duval',     '2026-05-08', '11:30', 'DCVA', '1-1/2"'),
        ('Anastasia Island Hampton Inn',  '105 Anastasia Blvd',          'St. Augustine',     'St. Johns', '2026-05-08', '12:00', 'DCVA', '1"'),
        ('Palencia Golf Club',            '600 Palencia Club Dr',        'St. Augustine',     'St. Johns', '2026-05-08', '12:30', 'RPZ',  '1-1/2"'),
        ('Castillo de San Marcos',        '1 S Castillo Dr',             'St. Augustine',     'St. Johns', '2026-05-08', '13:00', 'RPZ',  '3/4"'),
        ('Vilano Beach Apartments',       '280 Vilano Rd',               'St. Augustine',     'St. Johns', '2026-05-08', '13:30', 'RPZ',  '1"'),
        ('Hibernia Medical Center',       '1781 Town Park Blvd',         'Orange Park',       'Clay',      '2026-05-08', '14:00', 'RPZ',  '1"'),
        ('Black Creek Elementary School', '1770 Black Creek Dr',         'Orange Park',       'Clay',      '2026-05-08', '14:30', 'DCVA', '1"'),
        ('Blanding Blvd Shopping Center', '1985 Blanding Blvd',          'Middleburg',        'Clay',      '2026-05-08', '15:00', 'DCVA', '1"'),
    ]

    created = 0
    for (cust_name, address, city, county, date, time,
         device_type, device_size) in JOBS:
        customer, _ = Customer.objects.get_or_create(
            business_name=cust_name,
            defaults={
                'address': address, 'city': city,
                'state': 'FL', 'county': county,
            },
        )
        if not Job.objects.filter(customer=cust_name, scheduled_date=date).exists():
            Job.objects.create(
                customer_ref=customer,
                customer=cust_name,
                address=address,
                state='FL',
                county=county,
                scheduled_date=date,
                scheduled_time=time,
                status='pending',
                assigned_to=None,
                device_type=device_type,
                device_size=device_size,
            )
            created += 1

    return JsonResponse({'ok': True, 'created': created, 'total_defined': len(JOBS)})


# ── Import views ──────────────────────────────────────────────────────────────

_IMPORT_COLUMNS = [
    'business_name', 'contact_name', 'phone', 'email',
    'address', 'city', 'state', 'county', 'zip_code',
    'scheduled_date', 'scheduled_time', 'status',
    'device_type', 'device_size', 'device_make', 'device_model', 'serial',
    'test_date', 'test_time',
    'cv1_result', 'cv1_psi', 'cv2_result', 'cv2_psi',
    'rv_result', 'rv_psi', 'line_psi',
    'overall_result', 'technician_initials', 'utility_account_number', 'notes',
]

_SAMPLE_ROWS = [
    {
        'business_name': 'Sunshine Plumbing', 'contact_name': 'Mike Chen',
        'phone': '904-555-1234', 'email': 'mike@sunshine.com',
        'address': '123 Main St', 'city': 'Jacksonville', 'state': 'FL',
        'county': 'Duval', 'zip_code': '32202',
        'scheduled_date': '2026-06-01', 'scheduled_time': '09:00', 'status': 'pending',
        'device_type': 'RPZ', 'device_size': '1"', 'device_make': 'Watts',
        'device_model': '909', 'serial': 'SN123456',
        'test_date': '', 'test_time': '', 'cv1_result': '', 'cv1_psi': '',
        'cv2_result': '', 'cv2_psi': '', 'rv_result': '', 'rv_psi': '',
        'line_psi': '', 'overall_result': '', 'technician_initials': '',
        'utility_account_number': '', 'notes': '',
    },
    {
        'business_name': 'Harbor Irrigation', 'contact_name': 'Tom Brown',
        'phone': '904-555-5678', 'email': '',
        'address': '456 Oak Ave', 'city': 'St. Augustine', 'state': 'FL',
        'county': 'St. Johns', 'zip_code': '32084',
        'scheduled_date': '2025-12-15', 'scheduled_time': '10:30', 'status': 'completed',
        'device_type': 'DCVA', 'device_size': '2"', 'device_make': 'Febco',
        'device_model': '850', 'serial': 'SN789012',
        'test_date': '2025-12-15', 'test_time': '10:45',
        'cv1_result': 'closed', 'cv1_psi': '12.5',
        'cv2_result': 'closed', 'cv2_psi': '12.5',
        'rv_result': 'opened_ok', 'rv_psi': '8.0', 'line_psi': '95.0',
        'overall_result': 'pass', 'technician_initials': 'TB',
        'utility_account_number': '', 'notes': '',
    },
]


def _parse_import_csv(file_obj):
    rows = []
    errors = []
    try:
        text = file_obj.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        for i, raw in enumerate(reader, start=2):  # row 1 = header
            row = {k.strip().lower().replace(' ', '_'): (v.strip() if v else '') for k, v in raw.items()}
            warnings = []
            if not row.get('business_name'):
                warnings.append('Missing business_name')
            if not row.get('address'):
                warnings.append('Missing address')
            if not row.get('scheduled_date'):
                warnings.append('Missing scheduled_date')
            status = row.get('status', 'pending').lower()
            if status not in ('pending', 'in_progress', 'completed', 'cancelled'):
                warnings.append(f'Unknown status "{status}" — defaulting to pending')
                status = 'pending'
            row['status'] = status
            if not row.get('state'):
                row['state'] = 'FL'
            if not row.get('scheduled_time'):
                row['scheduled_time'] = '08:00'
            if status == 'completed' and not row.get('overall_result'):
                warnings.append('Status is completed but overall_result is missing')
            row['row_num'] = i
            row['warnings'] = warnings
            rows.append(row)
    except Exception as exc:
        errors.append(f'Could not parse file: {exc}')
    return rows, errors


@role_required('operations', 'manager')
def ops_import(request):
    if request.method == 'POST' and request.FILES.get('csv_file'):
        rows, parse_errors = _parse_import_csv(request.FILES['csv_file'])
        for row in rows:
            row['customer_exists'] = Customer.objects.filter(
                business_name__iexact=row.get('business_name', '')
            ).exists()
        # Store serialisable copy in session (strip non-JSON-safe keys if needed)
        request.session['pending_import'] = rows
        return render(request, 'technician/ops_import.html', {
            'rows': rows,
            'parse_errors': parse_errors,
            'preview_mode': True,
        })
    request.session.pop('pending_import', None)
    return render(request, 'technician/ops_import.html', {'preview_mode': False})


@role_required('operations', 'manager')
def ops_import_confirm(request):
    if request.method != 'POST':
        return redirect('ops_import')
    rows = request.session.pop('pending_import', [])
    selected_indices = set(request.POST.getlist('selected'))
    created_customers = created_jobs = created_tests = skipped = 0

    for row in rows:
        if str(row.get('row_num', '')) not in selected_indices:
            skipped += 1
            continue
        if not row.get('business_name') or not row.get('scheduled_date'):
            skipped += 1
            continue

        customer = Customer.objects.filter(
            business_name__iexact=row['business_name']
        ).first()
        if not customer:
            customer = Customer.objects.create(
                business_name=row['business_name'],
                contact_name=row.get('contact_name', ''),
                phone=row.get('phone', ''),
                email=row.get('email', ''),
                address=row.get('address', ''),
                city=row.get('city', ''),
                state=row.get('state', 'FL'),
                county=row.get('county', ''),
                zip_code=row.get('zip_code', ''),
            )
            created_customers += 1

        def _decimal(val):
            try: return float(val) if val else None
            except (ValueError, TypeError): return None

        def _int(val):
            try: return int(val) if val else None
            except (ValueError, TypeError): return None

        job = Job.objects.create(
            customer_ref=customer,
            customer=customer.business_name,
            address=row.get('address') or customer.address,
            contact=row.get('contact_name') or customer.contact_name,
            phone=row.get('phone') or customer.phone,
            state=row.get('state', 'FL'),
            county=row.get('county', ''),
            scheduled_date=row['scheduled_date'],
            scheduled_time=row.get('scheduled_time', '08:00'),
            status=row.get('status', 'pending'),
            device_type=row.get('device_type', 'RPZ'),
            device_size=row.get('device_size', ''),
            device_make=row.get('device_make', ''),
            device_model=row.get('device_model', ''),
            serial=row.get('serial', ''),
            notes=row.get('notes', ''),
        )
        created_jobs += 1

        if row.get('status') == 'completed' and row.get('overall_result'):
            TestResult.objects.create(
                job=job,
                customer=customer.business_name,
                address=row.get('address') or customer.address,
                device_type=row.get('device_type', 'RPZ'),
                device_size=row.get('device_size', ''),
                manufacturer=row.get('device_make', ''),
                model=row.get('device_model', ''),
                serial=row.get('serial', ''),
                test_date=row.get('test_date') or row['scheduled_date'],
                test_time=row.get('test_time') or row.get('scheduled_time', '08:00'),
                cv1_result=row.get('cv1_result', ''),
                cv1_psi=_decimal(row.get('cv1_psi')),
                cv2_result=row.get('cv2_result', ''),
                cv2_psi=_decimal(row.get('cv2_psi')),
                rv_result=row.get('rv_result', ''),
                rv_psi=_decimal(row.get('rv_psi')),
                line_psi=_decimal(row.get('line_psi')),
                overall_result=row.get('overall_result', 'pass'),
                notes=row.get('notes', ''),
                technician_initials=row.get('technician_initials', '').upper(),
                submitted_by=request.user,
                utility_account_number=row.get('utility_account_number', ''),
            )
            created_tests += 1

    request.session['import_summary'] = {
        'jobs': created_jobs,
        'customers': created_customers,
        'tests': created_tests,
        'skipped': skipped,
    }
    return redirect('ops_dashboard')


@role_required('operations', 'manager')
def ops_download_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="wolf_import_template.csv"'
    writer = csv.DictWriter(response, fieldnames=_IMPORT_COLUMNS)
    writer.writeheader()
    for row in _SAMPLE_ROWS:
        writer.writerow(row)
    return response


# ── Admin views ───────────────────────────────────────────────────────────────

@role_required('admin')
def admin_users(request):
    from datetime import timedelta
    users = User.objects.select_related('profile').order_by('profile__role', 'first_name')
    role_counts = {}
    for role, label in UserProfile.ROLES:
        role_counts[role] = users.filter(profile__role=role).count()
    today = timezone.localdate()
    return render(request, 'technician/admin_users.html', {
        'users': users,
        'role_counts': role_counts,
        'total': users.count(),
        'ROLES': UserProfile.ROLES,
        'today': today,
        'warn_date': today + timedelta(days=90),
    })


@role_required('admin')
def admin_user_form(request, user_id=None):
    from datetime import date as _date
    target = get_object_or_404(User, pk=user_id) if user_id else None
    error = None

    if request.method == 'POST':
        p = request.POST
        username = p.get('username', '').strip()
        first_name = p.get('first_name', '').strip()
        last_name = p.get('last_name', '').strip()
        email = p.get('email', '').strip()
        role = p.get('role', 'technician')
        password = p.get('password', '')
        confirm = p.get('confirm_password', '')

        counties = p.getlist('counties') if role == 'technician' else []
        is_licensed = 'is_licensed' in p and role == 'technician'
        license_expires = None
        if is_licensed and p.get('license_expires'):
            try:
                license_expires = _date.fromisoformat(p['license_expires'])
            except ValueError:
                pass

        if not target and User.objects.filter(username=username).exists():
            error = f'Username "{username}" is already taken.'
        elif password and password != confirm:
            error = 'Passwords do not match.'
        else:
            if target:
                target.username = username
                target.first_name = first_name
                target.last_name = last_name
                target.email = email
                if password:
                    target.set_password(password)
                    if target == request.user:
                        update_session_auth_hash(request, target)
                target.save()
                target.profile.role = role
                target.profile.counties = counties
                target.profile.is_licensed = is_licensed
                target.profile.license_expires = license_expires
                target.profile.save()
            else:
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                )
                UserProfile.objects.create(
                    user=user, role=role,
                    counties=counties,
                    is_licensed=is_licensed,
                    license_expires=license_expires,
                )
            return redirect('admin_users')

    return render(request, 'technician/admin_user_form.html', {
        'target': target,
        'ROLES': UserProfile.ROLES,
        'FL_COUNTIES': FL_COUNTIES,
        'error': error,
    })


# ── Smoke tests ───────────────────────────────────────────────────────────────

@role_required('admin')
def admin_smoke_tests(request):
    from . import smoke_tests as st
    from .models import SmokeTestRun
    if request.method == 'POST':
        st.run_all(triggered_by=request.user)
        return redirect('admin_smoke_tests')
    runs = SmokeTestRun.objects.prefetch_related('cases').order_by('-run_at')[:10]
    latest = runs[0] if runs else None
    return render(request, 'technician/admin_smoke_tests.html', {
        'latest': latest,
        'runs': runs,
    })


# ── Process mining ───────────────────────────────────────────────────────────

@role_required('admin')
def admin_process_mining(request):
    logs = ActivityLog.objects.select_related('user', 'user__profile').order_by('-timestamp')

    role_filter     = request.GET.get('role', '')
    user_filter     = request.GET.get('user', '')
    activity_filter = request.GET.get('activity', '')

    if role_filter:
        logs = logs.filter(user__profile__role=role_filter)
    if user_filter:
        logs = logs.filter(user__id=user_filter)
    if activity_filter:
        logs = logs.filter(activity=activity_filter)

    all_users = User.objects.select_related('profile').order_by('first_name', 'last_name')
    today = timezone.localdate()
    today_count = ActivityLog.objects.filter(timestamp__date=today).count()

    return render(request, 'technician/admin_process_mining.html', {
        'logs': logs[:200],
        'total': ActivityLog.objects.count(),
        'today_count': today_count,
        'unique_users': ActivityLog.objects.values('user').distinct().count(),
        'all_users': all_users,
        'ROLES': UserProfile.ROLES,
        'ACTIVITIES': ActivityLog.ACTIVITIES,
        'role_filter': role_filter,
        'user_filter': user_filter,
        'activity_filter': activity_filter,
    })


# ── Customer views ────────────────────────────────────────────────────────────

@role_required('customer')
def customer_dashboard(request):
    recent_results = TestResult.objects.filter(
        customer__icontains=request.user.get_full_name() or request.user.username
    ).order_by('-submitted_at')[:10]
    upcoming_jobs = Job.objects.filter(
        status__in=('pending', 'in_progress')
    ).filter(
        customer__icontains=request.user.get_full_name() or request.user.username
    ).order_by('scheduled_date', 'scheduled_time')[:5]
    return render(request, 'technician/customer_dashboard.html', {
        'recent_results': recent_results,
        'upcoming_jobs': upcoming_jobs,
    })