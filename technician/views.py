from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.utils import timezone
from functools import wraps
from .models import UserProfile, Job, TestResult


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


def db_status(request):
    from django.http import JsonResponse
    from django.db import connection
    try:
        user_count = User.objects.count()
        profile_count = UserProfile.objects.count()
        db_name = connection.settings_dict.get('NAME', 'unknown')
        engine = connection.settings_dict.get('ENGINE', 'unknown')
        return JsonResponse({
            'engine': engine,
            'db': db_name,
            'users': user_count,
            'profiles': profile_count,
            'usernames': list(User.objects.values_list('username', flat=True)),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


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
    date_filter = request.GET.get('date', str(timezone.localdate()))
    status_filter = request.GET.get('status', '')
    tech_filter = request.GET.get('tech', '')

    jobs = Job.objects.select_related('assigned_to').all()
    if date_filter:
        jobs = jobs.filter(scheduled_date=date_filter)
    if status_filter:
        jobs = jobs.filter(status=status_filter)
    if tech_filter:
        jobs = jobs.filter(assigned_to__id=tech_filter)

    technicians = User.objects.filter(profile__role='technician').order_by('first_name')
    total = jobs.count()
    unassigned = jobs.filter(assigned_to__isnull=True).count()
    completed = jobs.filter(status='completed').count()
    pending = jobs.filter(status='pending').count()

    return render(request, 'technician/ops_dashboard.html', {
        'jobs': jobs,
        'technicians': technicians,
        'date_filter': date_filter,
        'status_filter': status_filter,
        'tech_filter': tech_filter,
        'total': total,
        'unassigned': unassigned,
        'completed': completed,
        'pending': pending,
    })


@role_required('operations', 'manager')
def ops_job_form(request, job_id=None):
    job = get_object_or_404(Job, pk=job_id) if job_id else None
    technicians = User.objects.filter(profile__role='technician').order_by('first_name')

    if request.method == 'POST':
        p = request.POST

        def flt(f):
            try: return float(p[f]) if p.get(f) else None
            except ValueError: return None

        assigned_id = p.get('assigned_to')
        assigned = User.objects.filter(pk=assigned_id).first() if assigned_id else None

        data = dict(
            customer=p.get('customer', ''),
            address=p.get('address', ''),
            contact=p.get('contact', ''),
            phone=p.get('phone', ''),
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
            lat=flt('lat'),
            lng=flt('lng'),
            device_lat=flt('device_lat'),
            device_lng=flt('device_lng'),
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
        'DEVICE_TYPES': Job.DEVICE_TYPES,
        'STATUS_CHOICES': Job.STATUS_CHOICES,
    })


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