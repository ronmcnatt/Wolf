"""
Smoke tests run after each deployment to verify core workflows are intact.
Each test returns (passed: bool, detail: str).
Add new tests by decorating a function with @register(...).
"""
from django.utils import timezone
from django.contrib.auth.models import User

_REGISTRY = []


def register(name, label, category):
    def decorator(fn):
        _REGISTRY.append({'name': name, 'label': label, 'category': category, 'fn': fn})
        return fn
    return decorator


# ── Technician ────────────────────────────────────────────────────────────────

@register(
    'tech_users_exist',
    'Technician users exist in the database',
    'technician',
)
def tech_users_exist():
    from .models import UserProfile
    techs = list(UserProfile.objects.filter(role='technician').select_related('user'))
    if not techs:
        return False, 'No users with role=technician found'
    names = ', '.join(t.user.get_full_name() or t.user.username for t in techs)
    return True, f'{len(techs)} technician(s): {names}'


@register(
    'tech_credentials_set',
    'All technicians have license status and expiry date set',
    'technician',
)
def tech_credentials_set():
    from .models import UserProfile
    techs = list(UserProfile.objects.filter(role='technician').select_related('user'))
    if not techs:
        return False, 'No technicians found'
    missing = [
        t.user.get_full_name() or t.user.username
        for t in techs
        if not t.is_licensed or not t.license_expires
    ]
    if missing:
        return False, f'Missing credentials: {", ".join(missing)}'
    return True, f'All {len(techs)} technician(s) have is_licensed=True and license_expires set'


@register(
    'tech_counties_set',
    'All technicians have at least one county assigned',
    'technician',
)
def tech_counties_set():
    from .models import UserProfile
    techs = list(UserProfile.objects.filter(role='technician').select_related('user'))
    if not techs:
        return False, 'No technicians found'
    missing = [
        t.user.get_full_name() or t.user.username
        for t in techs
        if not t.counties
    ]
    if missing:
        return False, f'No counties assigned to: {", ".join(missing)}'
    total_counties = sum(len(t.counties) for t in techs)
    return True, f'All {len(techs)} technician(s) have counties set ({total_counties} total assignments)'


@register(
    'tech_dropdown_coverage',
    'Technicians with counties will appear in job assignment dropdown',
    'technician',
)
def tech_dropdown_coverage():
    from .models import UserProfile
    techs = list(UserProfile.objects.filter(role='technician').select_related('user'))
    if not techs:
        return False, 'No technicians found'
    covered = [t for t in techs if t.counties]
    uncovered = [
        t.user.get_full_name() or t.user.username
        for t in techs
        if not t.counties
    ]
    if not covered:
        return False, 'No technicians have counties — dropdown will always be empty'
    detail = f'{len(covered)} technician(s) will appear in dropdown'
    if uncovered:
        detail += f'; {len(uncovered)} excluded (no counties): {", ".join(uncovered)}'
    return True, detail


@register(
    'tech_jobs_assigned',
    'At least one job is assigned to a technician',
    'technician',
)
def tech_jobs_assigned():
    from .models import Job
    tech_users = User.objects.filter(profile__role='technician')
    count = Job.objects.filter(assigned_to__in=tech_users).count()
    if count == 0:
        return False, 'No jobs are assigned to any technician'
    return True, f'{count} job(s) assigned to technicians'


@register(
    'tech_open_jobs_exist',
    'Open jobs (pending/in-progress) exist from today forward',
    'technician',
)
def tech_open_jobs_exist():
    from .models import Job
    today = timezone.localdate()
    count = Job.objects.filter(
        scheduled_date__gte=today,
        status__in=('pending', 'in_progress'),
    ).count()
    if count == 0:
        return False, f'No pending or in-progress jobs scheduled from {today} forward'
    return True, f'{count} open job(s) from {today} forward'


# ── Runner ────────────────────────────────────────────────────────────────────

def run_all(triggered_by=None):
    from .models import SmokeTestRun, SmokeTestCase
    run = SmokeTestRun.objects.create(triggered_by=triggered_by)
    passed = 0
    failed = 0
    for t in _REGISTRY:
        try:
            ok, detail = t['fn']()
        except Exception as exc:
            ok, detail = False, f'Error: {exc}'
        SmokeTestCase.objects.create(
            run=run,
            name=t['name'],
            label=t['label'],
            category=t['category'],
            passed=ok,
            detail=detail,
        )
        if ok:
            passed += 1
        else:
            failed += 1
    run.passed = passed
    run.failed = failed
    run.save()
    return run
