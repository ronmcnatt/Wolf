from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from technician.models import UserProfile, Job
import datetime


SAMPLE_JOBS = [
    {
        'customer': 'Riverside Auto Wash', 'address': '1234 Riverside Ave, Jacksonville, FL 32204',
        'contact': 'Mike Johnson', 'phone': '(904) 555-0142', 'time': '08:00',
        'device_type': 'RPZ', 'device_size': '1"', 'device_make': 'Watts',
        'device_model': '009', 'serial': 'W2204-8871',
        'device_notes': 'Behind fence, NE corner of building',
        'lat': 30.3149, 'lng': -81.6693, 'device_lat': 30.31498, 'device_lng': -81.66915,
    },
    {
        'customer': 'Sunshine Apartments', 'address': '567 Park St, Jacksonville, FL 32204',
        'contact': 'Sandra Lee', 'phone': '(904) 555-0198', 'time': '09:15',
        'device_type': 'DCVA', 'device_size': '3/4"', 'device_make': 'Febco',
        'device_model': '850', 'serial': 'F2019-3341',
        'device_notes': 'Utility room, ground floor, west wing',
        'lat': 30.3220, 'lng': -81.6580, 'device_lat': 30.32208, 'device_lng': -81.65785,
    },
    {
        'customer': 'Orange Park Commons HOA', 'address': '890 Blanding Blvd, Orange Park, FL 32065',
        'contact': 'Tom Rivera', 'phone': '(904) 555-0211', 'time': '10:30',
        'device_type': 'RPZ', 'device_size': '2"', 'device_make': 'Wilkins',
        'device_model': '975XL', 'serial': 'WK2021-6612',
        'device_notes': 'Irrigation backflow, behind clubhouse',
        'lat': 30.1654, 'lng': -81.7065, 'device_lat': 30.16550, 'device_lng': -81.70635,
    },
    {
        'customer': 'Fleming Island Medical Center', 'address': '234 Town Center Blvd, Fleming Island, FL 32003',
        'contact': 'Dr. Patricia Holt', 'phone': '(904) 555-0334', 'time': '11:45',
        'device_type': 'RPZ', 'device_size': '1.5"', 'device_make': 'Ames',
        'device_model': '4000SS', 'serial': 'A2022-1197',
        'device_notes': 'Mechanical room, lower level, south entrance',
        'lat': 30.1010, 'lng': -81.7143, 'device_lat': 30.10108, 'device_lng': -81.71415,
    },
    {
        'customer': 'St. Johns County Recreation Center', 'address': '456 Race Track Rd, St. Johns, FL 32259',
        'contact': 'Gary Simmons', 'phone': '(904) 555-0455', 'time': '13:00',
        'device_type': 'PVB', 'device_size': '1"', 'device_make': 'Watts',
        'device_model': '800M4', 'serial': 'W2020-5589',
        'device_notes': 'Exterior east side, near irrigation valve box',
        'lat': 30.1580, 'lng': -81.6043, 'device_lat': 30.15808, 'device_lng': -81.60415,
    },
    {
        'customer': 'Ponte Vedra Beach Club', 'address': '789 A1A N, Ponte Vedra Beach, FL 32082',
        'contact': 'Claire Ashford', 'phone': '(904) 555-0567', 'time': '14:00',
        'device_type': 'DCVA', 'device_size': '1"', 'device_make': 'Febco',
        'device_model': '860', 'serial': 'F2023-8823',
        'device_notes': 'Pool equipment room, north end of clubhouse',
        'lat': 30.2394, 'lng': -81.3883, 'device_lat': 30.23948, 'device_lng': -81.38815,
    },
    {
        'customer': 'Atlantic Beach City Hall', 'address': '800 Seminole Rd, Atlantic Beach, FL 32233',
        'contact': 'Derrick Fowler', 'phone': '(904) 555-0688', 'time': '15:00',
        'device_type': 'RPZ', 'device_size': '1"', 'device_make': 'Watts',
        'device_model': '909', 'serial': 'W2021-2214',
        'device_notes': 'Exterior east wall, padlocked enclosure',
        'lat': 30.3371, 'lng': -81.3996, 'device_lat': 30.33718, 'device_lng': -81.39945,
    },
    {
        'customer': 'Neptune Beach HOA', 'address': '123 Neptune Ave, Neptune Beach, FL 32266',
        'contact': 'Beth Calloway', 'phone': '(904) 555-0712', 'time': '15:45',
        'device_type': 'PVB', 'device_size': '3/4"', 'device_make': 'Wilkins',
        'device_model': '720A', 'serial': 'WK2019-9901',
        'device_notes': 'Irrigation system, near front entrance sign',
        'lat': 30.3127, 'lng': -81.4027, 'device_lat': 30.31278, 'device_lng': -81.40255,
    },
    {
        'customer': 'Mandarin Presbyterian Church', 'address': '11946 Mandarin Rd, Jacksonville, FL 32223',
        'contact': 'Pastor Dale Norris', 'phone': '(904) 555-0834', 'time': '16:30',
        'device_type': 'DCVA', 'device_size': '3/4"', 'device_make': 'Ames',
        'device_model': '2000SS', 'serial': 'A2020-7743',
        'device_notes': 'Exterior south side, near garden beds',
        'lat': 30.1580, 'lng': -81.6243, 'device_lat': 30.15808, 'device_lng': -81.62415,
    },
    {
        'customer': 'Baymeadows Plaza', 'address': '8550 Baymeadows Rd, Jacksonville, FL 32256',
        'contact': 'Lisa Crane', 'phone': '(904) 555-0956', 'time': '17:15',
        'device_type': 'RPZ', 'device_size': '2"', 'device_make': 'Febco',
        'device_model': '880V', 'serial': 'F2022-4456',
        'device_notes': 'Loading dock utility room, rear of building',
        'lat': 30.2347, 'lng': -81.5513, 'device_lat': 30.23478, 'device_lng': -81.55115,
    },
]


class Command(BaseCommand):
    help = 'Create demo users (technician / operations / manager) and seed sample jobs'

    def handle(self, *args, **options):
        today = timezone.localdate()

        # Create users
        users = [
            ('technician', 'tech123', 'John', 'Smith', 'technician'),
            ('operations', 'ops123', 'Sarah', 'Johnson', 'operations'),
            ('manager', 'mgr123', 'Robert', 'Wolf', 'manager'),
        ]
        tech_user = None
        for username, password, first, last, role in users:
            user, created = User.objects.get_or_create(username=username)
            if created:
                user.set_password(password)
                user.first_name = first
                user.last_name = last
                user.save()
            UserProfile.objects.get_or_create(user=user, defaults={'role': role})
            if username == 'technician':
                tech_user = user
            action = 'Created' if created else 'Already exists'
            self.stdout.write(f'{action}: {username} ({role})')

        # Seed today's jobs assigned to the technician
        if not Job.objects.filter(scheduled_date=today).exists():
            for j in SAMPLE_JOBS:
                Job.objects.create(
                    customer=j['customer'],
                    address=j['address'],
                    contact=j['contact'],
                    phone=j['phone'],
                    scheduled_date=today,
                    scheduled_time=datetime.time(*map(int, j['time'].split(':'))),
                    assigned_to=tech_user,
                    device_type=j['device_type'],
                    device_size=j['device_size'],
                    device_make=j['device_make'],
                    device_model=j['device_model'],
                    serial=j['serial'],
                    device_notes=j['device_notes'],
                    lat=j['lat'], lng=j['lng'],
                    device_lat=j['device_lat'], device_lng=j['device_lng'],
                )
            self.stdout.write(self.style.SUCCESS(f'Seeded {len(SAMPLE_JOBS)} jobs for {today}'))
        else:
            self.stdout.write(f'Jobs for {today} already exist — skipping seed')

        self.stdout.write(self.style.SUCCESS('Done.'))