import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.utils import timezone
from django.views.decorators.http import require_POST
from functools import wraps
from .models import UserProfile, Job, TestResult, Customer

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
    jobs = Job.objects.filter(assigned_to=request.user, scheduled_date=today)
    completed = jobs.filter(status='completed').count()
    in_progress = jobs.filter(status='in_progress').count()
    pending = jobs.filter(status='pending').count()
    return render(request, 'technician/dashboard.html', {
        'jobs': jobs,
        'completed': completed,
        'in_progress': in_progress,
        'pending': pending,
        'total': jobs.count(),
        'today': today,
    })


@role_required('technician', 'manager')
def tech_job_detail(request, job_id):
    job = get_object_or_404(Job, pk=job_id)
    submitted = False

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
        )
        job.status = 'completed'
        job.save()
        submitted = True

    prior_results = job.test_results.all()
    return render(request, 'technician/job_detail.html', {
        'job': job,
        'submitted': submitted,
        'prior_results': prior_results,
    })


# ── Operations views ──────────────────────────────────────────────────────────

@role_required('operations', 'manager')
def ops_dashboard(request):
    tab = request.GET.get('tab', 'jobs')

    # ── Jobs tab ──
    date_filter   = request.GET.get('date', str(timezone.localdate()))
    status_filter = request.GET.get('status', '')
    tech_filter   = request.GET.get('tech', '')

    jobs = Job.objects.select_related('assigned_to', 'customer_ref').all()
    if date_filter:
        jobs = jobs.filter(scheduled_date=date_filter)
    if status_filter:
        jobs = jobs.filter(status=status_filter)
    if tech_filter:
        jobs = jobs.filter(assigned_to__id=tech_filter)

    technicians = User.objects.filter(profile__role='technician').order_by('first_name')
    total       = jobs.count()
    unassigned  = jobs.filter(assigned_to__isnull=True).count()
    completed   = jobs.filter(status='completed').count()
    pending     = jobs.filter(status='pending').count()

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
        'jobs': jobs, 'technicians': technicians,
        'date_filter': date_filter, 'status_filter': status_filter, 'tech_filter': tech_filter,
        'total': total, 'unassigned': unassigned, 'completed': completed, 'pending': pending,
        # customers
        'customer_rows': customer_rows, 'csearch': csearch,
        'total_customers': Customer.objects.count(),
    })


@role_required('operations', 'manager')
def ops_job_form(request, job_id=None):
    job = get_object_or_404(Job, pk=job_id) if job_id else None
    technicians = User.objects.filter(profile__role='technician').order_by('first_name')
    customers = Customer.objects.all()
    customers_json = json.dumps([{
        'id': c.id, 'business_name': c.business_name, 'contact_name': c.contact_name,
        'phone': c.phone, 'email': c.email, 'address': c.address,
        'city': c.city, 'state': c.state, 'county': c.county,
        'zip_code': c.zip_code, 'notes': c.notes,
    } for c in customers])

    if request.method == 'POST':
        p = request.POST

        def flt(f):
            try: return float(p[f]) if p.get(f) else None
            except ValueError: return None

        assigned_id = p.get('assigned_to')
        assigned = User.objects.filter(pk=assigned_id).first() if assigned_id else None
        customer_ref_id = p.get('customer_ref') or None
        customer_ref = Customer.objects.filter(pk=customer_ref_id).first() if customer_ref_id else None

        data = dict(
            customer_ref=customer_ref,
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
        'DEVICE_TYPES': Job.DEVICE_TYPES,
        'STATUS_CHOICES': Job.STATUS_CHOICES,
        'US_STATES': US_STATES,
        'FL_COUNTIES': FL_COUNTIES,
    })


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
            customer.address       = p.get('address', '').strip()
            customer.city          = p.get('city', '').strip()
            customer.state         = p.get('state', 'FL')
            customer.county        = p.get('county', '').strip()
            customer.zip_code      = p.get('zip_code', '').strip()
            customer.notes         = p.get('notes', '').strip()
            customer.save()
            return redirect('/tech/ops/?tab=customers')

    job_history = []
    if customer:
        job_history = Job.objects.filter(customer_ref=customer)\
                         .prefetch_related('test_results')\
                         .order_by('-scheduled_date')[:20]

    return render(request, 'technician/ops_customer_form.html', {
        'customer':    customer,
        'job_history': job_history,
        'US_STATES':   US_STATES,
        'FL_COUNTIES': FL_COUNTIES,
        'error':       error,
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
    customer.address = data.get('address', '').strip()
    customer.city = data.get('city', '').strip()
    customer.state = data.get('state', 'FL').strip()
    customer.county = data.get('county', '').strip()
    customer.zip_code = data.get('zip_code', '').strip()
    customer.notes = data.get('notes', '').strip()
    customer.save()

    return JsonResponse({'ok': True, 'customer': {
        'id': customer.id, 'business_name': customer.business_name,
        'contact_name': customer.contact_name, 'phone': customer.phone,
        'email': customer.email, 'address': customer.address,
        'city': customer.city, 'state': customer.state,
        'county': customer.county, 'zip_code': customer.zip_code,
        'notes': customer.notes,
    }})


# ── Admin views ───────────────────────────────────────────────────────────────

@role_required('admin')
def admin_users(request):
    users = User.objects.select_related('profile').order_by('profile__role', 'first_name')
    role_counts = {}
    for role, label in UserProfile.ROLES:
        role_counts[role] = users.filter(profile__role=role).count()
    return render(request, 'technician/admin_users.html', {
        'users': users,
        'role_counts': role_counts,
        'total': users.count(),
        'ROLES': UserProfile.ROLES,
    })


@role_required('admin')
def admin_user_form(request, user_id=None):
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
                target.profile.save()
            else:
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                )
                UserProfile.objects.create(user=user, role=role)
            return redirect('admin_users')

    return render(request, 'technician/admin_user_form.html', {
        'target': target,
        'ROLES': UserProfile.ROLES,
        'error': error,
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