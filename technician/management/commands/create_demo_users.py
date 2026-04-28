from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from technician.models import UserProfile, Job, TestResult, Customer
import datetime
import decimal


DEMO_USERS = [
    ('technician', 'tech123',      'John',   'Smith',    'technician'),
    ('operations', 'ops123',       'Sarah',  'Johnson',  'operations'),
    ('manager',    'mgr123',       'Robert', 'Wolf',     'manager'),
    ('admin',      'admin123',     'Admin',  'Wolf',     'admin'),
    ('customer',   'cust123',      'James',  'Wilson',   'customer'),
    ('mthompson',  'mthompson123', 'Marcus', 'Thompson', 'technician'),
    ('rdiaz',      'rdiaz123',     'Rosa',   'Diaz',     'technician'),
]

SAMPLE_CUSTOMERS = [
    {'business_name': 'Riverside Auto Wash',          'contact_name': 'Mike Johnson',      'phone': '(904) 555-0142', 'email': 'mjohnson@riversideautowash.com', 'address': '1234 Riverside Ave',   'city': 'Jacksonville',      'state': 'FL', 'county': 'Duval',     'zip_code': '32204', 'lat': 30.3149,  'lng': -81.6693,  'device_lat': 30.31498,  'device_lng': -81.66915},
    {'business_name': 'Sunshine Apartments',           'contact_name': 'Sandra Lee',        'phone': '(904) 555-0198', 'email': 'slee@sunshineapts.com',         'address': '567 Park St',           'city': 'Jacksonville',      'state': 'FL', 'county': 'Duval',     'zip_code': '32204', 'lat': 30.3220,  'lng': -81.6580,  'device_lat': 30.32208,  'device_lng': -81.65785},
    {'business_name': 'Orange Park Commons HOA',       'contact_name': 'Tom Rivera',        'phone': '(904) 555-0211', 'email': 'trivera@opcommons.org',         'address': '890 Blanding Blvd',    'city': 'Orange Park',       'state': 'FL', 'county': 'Clay',      'zip_code': '32065', 'lat': 30.1654,  'lng': -81.7065,  'device_lat': 30.16550,  'device_lng': -81.70635},
    {'business_name': 'Fleming Island Medical Center', 'contact_name': 'Dr. Patricia Holt', 'phone': '(904) 555-0334', 'email': 'pholt@fimedical.com',           'address': '234 Town Center Blvd', 'city': 'Fleming Island',    'state': 'FL', 'county': 'Clay',      'zip_code': '32003', 'lat': 30.1010,  'lng': -81.7143,  'device_lat': 30.10108,  'device_lng': -81.71415},
    {'business_name': 'St. Johns County Rec Center',   'contact_name': 'Gary Simmons',      'phone': '(904) 555-0455', 'email': 'gsimmons@stjohns.gov',          'address': '456 Race Track Rd',    'city': 'St. Johns',         'state': 'FL', 'county': 'St. Johns', 'zip_code': '32259', 'lat': 30.1580,  'lng': -81.6043,  'device_lat': 30.15808,  'device_lng': -81.60415},
    {'business_name': 'Ponte Vedra Beach Club',        'contact_name': 'Claire Ashford',    'phone': '(904) 555-0567', 'email': 'cashford@pvbeachclub.com',      'address': '789 A1A N',            'city': 'Ponte Vedra Beach', 'state': 'FL', 'county': 'St. Johns', 'zip_code': '32082', 'lat': 30.2394,  'lng': -81.3883,  'device_lat': 30.23948,  'device_lng': -81.38815},
    {'business_name': 'Atlantic Beach City Hall',      'contact_name': 'Derrick Fowler',    'phone': '(904) 555-0688', 'email': 'dfowler@atlanticbeachfl.gov',   'address': '800 Seminole Rd',      'city': 'Atlantic Beach',    'state': 'FL', 'county': 'Duval',     'zip_code': '32233', 'lat': 30.3371,  'lng': -81.3996,  'device_lat': 30.33718,  'device_lng': -81.39945},
    {'business_name': 'Neptune Beach HOA',             'contact_name': 'Beth Calloway',     'phone': '(904) 555-0712', 'email': 'bcalloway@neptunebeachhoa.org', 'address': '123 Neptune Ave',      'city': 'Neptune Beach',     'state': 'FL', 'county': 'Duval',     'zip_code': '32266', 'lat': 30.3127,  'lng': -81.4027,  'device_lat': 30.31278,  'device_lng': -81.40255},
    {'business_name': 'Mandarin Presbyterian Church',  'contact_name': 'Pastor Dale Norris','phone': '(904) 555-0834', 'email': 'dnorris@mandarinpres.org',      'address': '11946 Mandarin Rd',    'city': 'Jacksonville',      'state': 'FL', 'county': 'Duval',     'zip_code': '32223', 'lat': 30.1580,  'lng': -81.6243,  'device_lat': 30.15808,  'device_lng': -81.62415},
    {'business_name': 'Baymeadows Plaza',              'contact_name': 'Lisa Crane',        'phone': '(904) 555-0956', 'email': 'lcrane@baymeadowsplaza.com',    'address': '8550 Baymeadows Rd',   'city': 'Jacksonville',      'state': 'FL', 'county': 'Duval',     'zip_code': '32256', 'lat': 30.2347,  'lng': -81.5513,  'device_lat': 30.23478,  'device_lng': -81.55115},
]

# 2025 historical jobs — one per customer, all completed/passed
# Tech distribution: John Smith (JS) × 4, Marcus Thompson (MT) × 3, Rosa Diaz (RD) × 3
HISTORICAL_2025_JOBS = [
    {
        'customer_name': 'Riverside Auto Wash', 'tech': 'technician', 'initials': 'JS',
        'date': datetime.date(2025, 3, 10), 'time': datetime.time(8, 0),
        'device_type': 'RPZ',  'device_size': '1"',   'device_make': 'Watts',   'device_model': '009',     'serial': 'W2204-8871', 'install_year': 2018,
        'device_notes': 'Behind fence, NE corner of building',
        'lat': 30.3149, 'lng': -81.6693, 'device_lat': 30.31498, 'device_lng': -81.66915,
        'cv1_result': 'closed', 'cv1_psi': 10.2, 'cv2_result': 'closed', 'cv2_psi': 9.1,
        'rv_result': 'opened_ok', 'rv_psi': 2.1, 'line_psi': 82.0,
    },
    {
        'customer_name': 'Sunshine Apartments', 'tech': 'mthompson', 'initials': 'MT',
        'date': datetime.date(2025, 4, 7), 'time': datetime.time(9, 15),
        'device_type': 'DCVA', 'device_size': '3/4"', 'device_make': 'Febco',   'device_model': '850',     'serial': 'F2019-3341', 'install_year': 2019,
        'device_notes': 'Utility room, ground floor, west wing',
        'lat': 30.3220, 'lng': -81.6580, 'device_lat': 30.32208, 'device_lng': -81.65785,
        'cv1_result': 'closed', 'cv1_psi': 11.0, 'cv2_result': 'closed', 'cv2_psi': 9.8,
        'rv_result': '', 'rv_psi': None, 'line_psi': 78.0,
    },
    {
        'customer_name': 'Orange Park Commons HOA', 'tech': 'rdiaz', 'initials': 'RD',
        'date': datetime.date(2025, 4, 21), 'time': datetime.time(10, 30),
        'device_type': 'RPZ',  'device_size': '2"',   'device_make': 'Wilkins', 'device_model': '975XL',   'serial': 'WK2021-6612', 'install_year': 2021,
        'device_notes': 'Irrigation backflow, behind clubhouse',
        'lat': 30.1654, 'lng': -81.7065, 'device_lat': 30.16550, 'device_lng': -81.70635,
        'cv1_result': 'closed', 'cv1_psi': 10.8, 'cv2_result': 'closed', 'cv2_psi': 9.3,
        'rv_result': 'opened_ok', 'rv_psi': 2.3, 'line_psi': 85.0,
    },
    {
        'customer_name': 'Fleming Island Medical Center', 'tech': 'technician', 'initials': 'JS',
        'date': datetime.date(2025, 5, 15), 'time': datetime.time(11, 45),
        'device_type': 'RPZ',  'device_size': '1.5"', 'device_make': 'Ames',    'device_model': '4000SS',  'serial': 'A2022-1197', 'install_year': 2022,
        'device_notes': 'Mechanical room, lower level, south entrance',
        'lat': 30.1010, 'lng': -81.7143, 'device_lat': 30.10108, 'device_lng': -81.71415,
        'cv1_result': 'closed', 'cv1_psi': 11.2, 'cv2_result': 'closed', 'cv2_psi': 9.7,
        'rv_result': 'opened_ok', 'rv_psi': 2.0, 'line_psi': 80.0,
    },
    {
        'customer_name': 'St. Johns County Rec Center', 'tech': 'mthompson', 'initials': 'MT',
        'date': datetime.date(2025, 6, 9), 'time': datetime.time(13, 0),
        'device_type': 'PVB',  'device_size': '1"',   'device_make': 'Watts',   'device_model': '800M4',   'serial': 'W2020-5589', 'install_year': 2020,
        'device_notes': 'Exterior east side, near irrigation valve box',
        'lat': 30.1580, 'lng': -81.6043, 'device_lat': 30.15808, 'device_lng': -81.60415,
        'cv1_result': 'closed', 'cv1_psi': 10.5, 'cv2_result': '', 'cv2_psi': None,
        'rv_result': 'opened_ok', 'rv_psi': 1.8, 'line_psi': 76.0,
    },
    {
        'customer_name': 'Ponte Vedra Beach Club', 'tech': 'rdiaz', 'initials': 'RD',
        'date': datetime.date(2025, 7, 22), 'time': datetime.time(14, 0),
        'device_type': 'DCVA', 'device_size': '1"',   'device_make': 'Febco',   'device_model': '860',     'serial': 'F2023-8823', 'install_year': 2023,
        'device_notes': 'Pool equipment room, north end of clubhouse',
        'lat': 30.2394, 'lng': -81.3883, 'device_lat': 30.23948, 'device_lng': -81.38815,
        'cv1_result': 'closed', 'cv1_psi': 10.9, 'cv2_result': 'closed', 'cv2_psi': 9.5,
        'rv_result': '', 'rv_psi': None, 'line_psi': 88.0,
    },
    {
        'customer_name': 'Atlantic Beach City Hall', 'tech': 'technician', 'initials': 'JS',
        'date': datetime.date(2025, 8, 11), 'time': datetime.time(9, 0),
        'device_type': 'RPZ',  'device_size': '1"',   'device_make': 'Watts',   'device_model': '909',     'serial': 'W2021-2214', 'install_year': 2021,
        'device_notes': 'Exterior east wall, padlocked enclosure',
        'lat': 30.3371, 'lng': -81.3996, 'device_lat': 30.33718, 'device_lng': -81.39945,
        'cv1_result': 'closed', 'cv1_psi': 10.3, 'cv2_result': 'closed', 'cv2_psi': 9.0,
        'rv_result': 'opened_ok', 'rv_psi': 2.2, 'line_psi': 81.0,
    },
    {
        'customer_name': 'Neptune Beach HOA', 'tech': 'mthompson', 'initials': 'MT',
        'date': datetime.date(2025, 9, 18), 'time': datetime.time(10, 0),
        'device_type': 'PVB',  'device_size': '3/4"', 'device_make': 'Wilkins', 'device_model': '720A',    'serial': 'WK2019-9901', 'install_year': 2019,
        'device_notes': 'Irrigation system, near front entrance sign',
        'lat': 30.3127, 'lng': -81.4027, 'device_lat': 30.31278, 'device_lng': -81.40255,
        'cv1_result': 'closed', 'cv1_psi': 10.7, 'cv2_result': '', 'cv2_psi': None,
        'rv_result': 'opened_ok', 'rv_psi': 1.9, 'line_psi': 77.0,
    },
    {
        'customer_name': 'Mandarin Presbyterian Church', 'tech': 'rdiaz', 'initials': 'RD',
        'date': datetime.date(2025, 10, 6), 'time': datetime.time(11, 0),
        'device_type': 'DCVA', 'device_size': '3/4"', 'device_make': 'Ames',    'device_model': '2000SS',  'serial': 'A2020-7743', 'install_year': 2020,
        'device_notes': 'Exterior south side, near garden beds',
        'lat': 30.1580, 'lng': -81.6243, 'device_lat': 30.15808, 'device_lng': -81.62415,
        'cv1_result': 'closed', 'cv1_psi': 11.1, 'cv2_result': 'closed', 'cv2_psi': 9.4,
        'rv_result': '', 'rv_psi': None, 'line_psi': 79.0,
    },
    {
        'customer_name': 'Baymeadows Plaza', 'tech': 'technician', 'initials': 'JS',
        'date': datetime.date(2025, 11, 14), 'time': datetime.time(8, 30),
        'device_type': 'RPZ',  'device_size': '2"',   'device_make': 'Febco',   'device_model': '880V',    'serial': 'F2022-4456', 'install_year': 2022,
        'device_notes': 'Loading dock utility room, rear of building',
        'lat': 30.2347, 'lng': -81.5513, 'device_lat': 30.23478, 'device_lng': -81.55115,
        'cv1_result': 'closed', 'cv1_psi': 10.6, 'cv2_result': 'closed', 'cv2_psi': 9.2,
        'rv_result': 'opened_ok', 'rv_psi': 2.4, 'line_psi': 84.0,
    },
]

# 2026 completed jobs — 3 by John Smith (Jan–Mar)
COMPLETED_2026_JOBS = [
    {
        'customer_name': 'Riverside Auto Wash', 'tech': 'technician', 'initials': 'JS',
        'date': datetime.date(2026, 1, 13), 'time': datetime.time(8, 0),
        'device_type': 'RPZ',  'device_size': '1"',   'device_make': 'Watts',   'device_model': '009',     'serial': 'W2204-8871', 'install_year': 2018,
        'device_notes': 'Behind fence, NE corner of building',
        'lat': 30.3149, 'lng': -81.6693, 'device_lat': 30.31498, 'device_lng': -81.66915,
        'cv1_result': 'closed', 'cv1_psi': 10.4, 'cv2_result': 'closed', 'cv2_psi': 9.0,
        'rv_result': 'opened_ok', 'rv_psi': 2.2, 'line_psi': 83.0,
    },
    {
        'customer_name': 'Fleming Island Medical Center', 'tech': 'technician', 'initials': 'JS',
        'date': datetime.date(2026, 2, 10), 'time': datetime.time(11, 45),
        'device_type': 'RPZ',  'device_size': '1.5"', 'device_make': 'Ames',    'device_model': '4000SS',  'serial': 'A2022-1197', 'install_year': 2022,
        'device_notes': 'Mechanical room, lower level, south entrance',
        'lat': 30.1010, 'lng': -81.7143, 'device_lat': 30.10108, 'device_lng': -81.71415,
        'cv1_result': 'closed', 'cv1_psi': 11.0, 'cv2_result': 'closed', 'cv2_psi': 9.6,
        'rv_result': 'opened_ok', 'rv_psi': 2.1, 'line_psi': 80.0,
    },
    {
        'customer_name': 'Atlantic Beach City Hall', 'tech': 'technician', 'initials': 'JS',
        'date': datetime.date(2026, 3, 17), 'time': datetime.time(9, 0),
        'device_type': 'RPZ',  'device_size': '1"',   'device_make': 'Watts',   'device_model': '909',     'serial': 'W2021-2214', 'install_year': 2021,
        'device_notes': 'Exterior east wall, padlocked enclosure',
        'lat': 30.3371, 'lng': -81.3996, 'device_lat': 30.33718, 'device_lng': -81.39945,
        'cv1_result': 'closed', 'cv1_psi': 10.8, 'cv2_result': 'closed', 'cv2_psi': 9.3,
        'rv_result': 'opened_ok', 'rv_psi': 2.3, 'line_psi': 82.0,
    },
]

# 2026 unassigned pending jobs — remaining 7 customers, scheduled May–Jun 2026
PENDING_2026_JOBS = [
    {
        'customer_name': 'Sunshine Apartments',
        'date': datetime.date(2026, 5, 5), 'time': datetime.time(9, 15),
        'device_type': 'DCVA', 'device_size': '3/4"', 'device_make': 'Febco',   'device_model': '850',   'serial': 'F2019-3341',
        'device_notes': 'Utility room, ground floor, west wing',
        'lat': 30.3220, 'lng': -81.6580, 'device_lat': 30.32208, 'device_lng': -81.65785,
    },
    {
        'customer_name': 'Orange Park Commons HOA',
        'date': datetime.date(2026, 5, 8), 'time': datetime.time(10, 30),
        'device_type': 'RPZ',  'device_size': '2"',   'device_make': 'Wilkins', 'device_model': '975XL', 'serial': 'WK2021-6612',
        'device_notes': 'Irrigation backflow, behind clubhouse',
        'lat': 30.1654, 'lng': -81.7065, 'device_lat': 30.16550, 'device_lng': -81.70635,
    },
    {
        'customer_name': 'St. Johns County Rec Center',
        'date': datetime.date(2026, 5, 12), 'time': datetime.time(13, 0),
        'device_type': 'PVB',  'device_size': '1"',   'device_make': 'Watts',   'device_model': '800M4', 'serial': 'W2020-5589',
        'device_notes': 'Exterior east side, near irrigation valve box',
        'lat': 30.1580, 'lng': -81.6043, 'device_lat': 30.15808, 'device_lng': -81.60415,
    },
    {
        'customer_name': 'Ponte Vedra Beach Club',
        'date': datetime.date(2026, 5, 15), 'time': datetime.time(14, 0),
        'device_type': 'DCVA', 'device_size': '1"',   'device_make': 'Febco',   'device_model': '860',   'serial': 'F2023-8823',
        'device_notes': 'Pool equipment room, north end of clubhouse',
        'lat': 30.2394, 'lng': -81.3883, 'device_lat': 30.23948, 'device_lng': -81.38815,
    },
    {
        'customer_name': 'Neptune Beach HOA',
        'date': datetime.date(2026, 5, 19), 'time': datetime.time(10, 0),
        'device_type': 'PVB',  'device_size': '3/4"', 'device_make': 'Wilkins', 'device_model': '720A',  'serial': 'WK2019-9901',
        'device_notes': 'Irrigation system, near front entrance sign',
        'lat': 30.3127, 'lng': -81.4027, 'device_lat': 30.31278, 'device_lng': -81.40255,
    },
    {
        'customer_name': 'Mandarin Presbyterian Church',
        'date': datetime.date(2026, 5, 27), 'time': datetime.time(11, 0),
        'device_type': 'DCVA', 'device_size': '3/4"', 'device_make': 'Ames',    'device_model': '2000SS','serial': 'A2020-7743',
        'device_notes': 'Exterior south side, near garden beds',
        'lat': 30.1580, 'lng': -81.6243, 'device_lat': 30.15808, 'device_lng': -81.62415,
    },
    {
        'customer_name': 'Baymeadows Plaza',
        'date': datetime.date(2026, 6, 3), 'time': datetime.time(8, 30),
        'device_type': 'RPZ',  'device_size': '2"',   'device_make': 'Febco',   'device_model': '880V',  'serial': 'F2022-4456',
        'device_notes': 'Loading dock utility room, rear of building',
        'lat': 30.2347, 'lng': -81.5513, 'device_lat': 30.23478, 'device_lng': -81.55115,
    },
]


def _make_decimal(val):
    return decimal.Decimal(str(val)) if val is not None else None


class Command(BaseCommand):
    help = 'Create demo users and seed historical job/test data'

    def handle(self, *args, **options):
        # ── Users ─────────────────────────────────────────────────────────────
        tech_users = {}
        for username, password, first, last, role in DEMO_USERS:
            user, created = User.objects.get_or_create(username=username)
            user.set_password(password)
            user.first_name = first
            user.last_name = last
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user, defaults={'role': role})
            if profile.role != role:
                profile.role = role
                profile.save()
            if role == 'technician':
                tech_users[username] = user
            action = 'Created' if created else 'Reset'
            self.stdout.write(f'{action}: {username} ({role})')

        # ── Customers ─────────────────────────────────────────────────────────
        customer_map = {}
        for sc in SAMPLE_CUSTOMERS:
            obj, created = Customer.objects.get_or_create(
                business_name=sc['business_name'], defaults=sc,
            )
            if not created:
                for field in ('lat', 'lng', 'device_lat', 'device_lng'):
                    setattr(obj, field, sc[field])
                obj.save(update_fields=['lat', 'lng', 'device_lat', 'device_lng'])
            customer_map[sc['business_name']] = obj
        self.stdout.write(self.style.SUCCESS(f'Customers ready: {len(customer_map)}'))

        # ── 2025 historical jobs ───────────────────────────────────────────────
        if not Job.objects.filter(scheduled_date__year=2025).exists():
            for j in HISTORICAL_2025_JOBS:
                cust = customer_map.get(j['customer_name'])
                tech = tech_users.get(j['tech'])
                job = Job.objects.create(
                    customer_ref=cust,
                    customer=j['customer_name'],
                    address=cust.address if cust else '',
                    contact=cust.contact_name if cust else '',
                    phone=cust.phone if cust else '',
                    state='FL',
                    county=cust.county if cust else '',
                    scheduled_date=j['date'],
                    scheduled_time=j['time'],
                    status='completed',
                    assigned_to=tech,
                    device_type=j['device_type'],
                    device_size=j['device_size'],
                    device_make=j['device_make'],
                    device_model=j['device_model'],
                    serial=j['serial'],
                    device_notes=j['device_notes'],
                    lat=j['lat'], lng=j['lng'],
                    device_lat=j['device_lat'], device_lng=j['device_lng'],
                )
                TestResult.objects.create(
                    job=job,
                    customer=j['customer_name'],
                    address=job.address,
                    device_type=j['device_type'],
                    device_size=j['device_size'],
                    manufacturer=j['device_make'],
                    model=j['device_model'],
                    serial=j['serial'],
                    install_year=j['install_year'],
                    test_date=j['date'],
                    test_time=j['time'],
                    cv1_result=j['cv1_result'],
                    cv1_psi=_make_decimal(j['cv1_psi']),
                    cv2_result=j.get('cv2_result', ''),
                    cv2_psi=_make_decimal(j.get('cv2_psi')),
                    rv_result=j.get('rv_result', ''),
                    rv_psi=_make_decimal(j.get('rv_psi')),
                    line_psi=_make_decimal(j['line_psi']),
                    overall_result='pass',
                    technician_initials=j['initials'],
                    submitted_by=tech,
                )
            self.stdout.write(self.style.SUCCESS(f'Seeded {len(HISTORICAL_2025_JOBS)} historical 2025 jobs'))
        else:
            self.stdout.write('2025 jobs already exist — skipping')

        # ── 2026 completed jobs ────────────────────────────────────────────────
        if not Job.objects.filter(scheduled_date__year=2026, status='completed').exists():
            john = tech_users.get('technician')
            for j in COMPLETED_2026_JOBS:
                cust = customer_map.get(j['customer_name'])
                job = Job.objects.create(
                    customer_ref=cust,
                    customer=j['customer_name'],
                    address=cust.address if cust else '',
                    contact=cust.contact_name if cust else '',
                    phone=cust.phone if cust else '',
                    state='FL',
                    county=cust.county if cust else '',
                    scheduled_date=j['date'],
                    scheduled_time=j['time'],
                    status='completed',
                    assigned_to=john,
                    device_type=j['device_type'],
                    device_size=j['device_size'],
                    device_make=j['device_make'],
                    device_model=j['device_model'],
                    serial=j['serial'],
                    device_notes=j['device_notes'],
                    lat=j['lat'], lng=j['lng'],
                    device_lat=j['device_lat'], device_lng=j['device_lng'],
                )
                TestResult.objects.create(
                    job=job,
                    customer=j['customer_name'],
                    address=job.address,
                    device_type=j['device_type'],
                    device_size=j['device_size'],
                    manufacturer=j['device_make'],
                    model=j['device_model'],
                    serial=j['serial'],
                    install_year=j['install_year'],
                    test_date=j['date'],
                    test_time=j['time'],
                    cv1_result=j['cv1_result'],
                    cv1_psi=_make_decimal(j['cv1_psi']),
                    cv2_result=j.get('cv2_result', ''),
                    cv2_psi=_make_decimal(j.get('cv2_psi')),
                    rv_result=j.get('rv_result', ''),
                    rv_psi=_make_decimal(j.get('rv_psi')),
                    line_psi=_make_decimal(j['line_psi']),
                    overall_result='pass',
                    technician_initials=j['initials'],
                    submitted_by=john,
                )
            self.stdout.write(self.style.SUCCESS(f'Seeded {len(COMPLETED_2026_JOBS)} completed 2026 jobs'))
        else:
            self.stdout.write('2026 completed jobs already exist — skipping')

        # ── 2026 unassigned pending jobs ───────────────────────────────────────
        if not Job.objects.filter(scheduled_date__year=2026, assigned_to__isnull=True).exists():
            for j in PENDING_2026_JOBS:
                cust = customer_map.get(j['customer_name'])
                Job.objects.create(
                    customer_ref=cust,
                    customer=j['customer_name'],
                    address=cust.address if cust else '',
                    contact=cust.contact_name if cust else '',
                    phone=cust.phone if cust else '',
                    state='FL',
                    county=cust.county if cust else '',
                    scheduled_date=j['date'],
                    scheduled_time=j['time'],
                    status='pending',
                    assigned_to=None,
                    device_type=j['device_type'],
                    device_size=j['device_size'],
                    device_make=j['device_make'],
                    device_model=j['device_model'],
                    serial=j['serial'],
                    device_notes=j['device_notes'],
                    lat=j['lat'], lng=j['lng'],
                    device_lat=j['device_lat'], device_lng=j['device_lng'],
                )
            self.stdout.write(self.style.SUCCESS(f'Seeded {len(PENDING_2026_JOBS)} unassigned 2026 jobs'))
        else:
            self.stdout.write('2026 unassigned jobs already exist — skipping')

        # ── Today's jobs for technician dashboard ─────────────────────────────
        today = timezone.localdate()
        if not Job.objects.filter(scheduled_date=today).exists():
            john = tech_users.get('technician')
            for sc in SAMPLE_CUSTOMERS:
                cust = customer_map.get(sc['business_name'])
                Job.objects.create(
                    customer_ref=cust,
                    customer=sc['business_name'],
                    address=sc['address'],
                    contact=sc['contact_name'],
                    phone=sc['phone'],
                    state='FL',
                    county=sc['county'],
                    scheduled_date=today,
                    scheduled_time=datetime.time(9, 0),
                    status='pending',
                    assigned_to=john,
                    device_type='RPZ',
                    device_size='1"',
                    lat=sc['lat'], lng=sc['lng'],
                    device_lat=sc['device_lat'], device_lng=sc['device_lng'],
                )
            self.stdout.write(self.style.SUCCESS(f"Seeded {len(SAMPLE_CUSTOMERS)} jobs for today ({today})"))
        else:
            self.stdout.write(f"Jobs for {today} already exist — skipping")

        self.stdout.write(self.style.SUCCESS('Done.'))
