from django.apps import AppConfig


class TechnicianConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "technician"

    def ready(self):
        import os
        # Only seed in the main web process, not during migrate/collectstatic
        if os.environ.get('DJANGO_SEED_ON_READY', '') == '1':
            try:
                self._seed_demo_users()
            except Exception:
                pass
            try:
                self._seed_sample_customers()
            except Exception:
                pass

    def _seed_demo_users(self):
        from django.contrib.auth.models import User
        from .models import UserProfile
        DEMO_USERS = [
            ('technician', 'tech123',      'John',   'Smith',    'technician'),
            ('operations', 'ops123',       'Sarah',  'Johnson',  'operations'),
            ('manager',    'mgr123',       'Robert', 'Wolf',     'manager'),
            ('admin',      'admin123',     'Admin',  'Wolf',     'admin'),
            ('customer',   'cust123',      'James',  'Wilson',   'customer'),
            ('mthompson',  'mthompson123', 'Marcus', 'Thompson', 'technician'),
            ('rdiaz',      'rdiaz123',     'Rosa',   'Diaz',     'technician'),
        ]
        for username, password, first, last, role in DEMO_USERS:
            user, _ = User.objects.get_or_create(username=username)
            user.set_password(password)
            user.first_name = first
            user.last_name = last
            user.save()
            profile, created = UserProfile.objects.get_or_create(user=user, defaults={'role': role})
            if not created and profile.role != role:
                profile.role = role
                profile.save()

    def _seed_sample_customers(self):
        from .models import Customer
        SAMPLE_CUSTOMERS = [
            {'business_name': 'Riverside Auto Wash',          'contact_name': 'Mike Johnson',       'phone': '(904) 555-0142', 'city': 'Jacksonville',      'state': 'FL', 'county': 'Duval',     'zip_code': '32204', 'lat': 30.3149,  'lng': -81.6693,  'device_lat': 30.31498,  'device_lng': -81.66915},
            {'business_name': 'Sunshine Apartments',           'contact_name': 'Sandra Lee',         'phone': '(904) 555-0198', 'city': 'Jacksonville',      'state': 'FL', 'county': 'Duval',     'zip_code': '32204', 'lat': 30.3220,  'lng': -81.6580,  'device_lat': 30.32208,  'device_lng': -81.65785},
            {'business_name': 'Orange Park Commons HOA',       'contact_name': 'Tom Rivera',         'phone': '(904) 555-0211', 'city': 'Orange Park',       'state': 'FL', 'county': 'Clay',      'zip_code': '32065', 'lat': 30.1654,  'lng': -81.7065,  'device_lat': 30.16550,  'device_lng': -81.70635},
            {'business_name': 'Fleming Island Medical Center', 'contact_name': 'Dr. Patricia Holt',  'phone': '(904) 555-0334', 'city': 'Fleming Island',    'state': 'FL', 'county': 'Clay',      'zip_code': '32003', 'lat': 30.1010,  'lng': -81.7143,  'device_lat': 30.10108,  'device_lng': -81.71415},
            {'business_name': 'St. Johns County Rec Center',   'contact_name': 'Gary Simmons',       'phone': '(904) 555-0455', 'city': 'St. Johns',         'state': 'FL', 'county': 'St. Johns', 'zip_code': '32259', 'lat': 30.1580,  'lng': -81.6043,  'device_lat': 30.15808,  'device_lng': -81.60415},
            {'business_name': 'Ponte Vedra Beach Club',        'contact_name': 'Claire Ashford',     'phone': '(904) 555-0567', 'city': 'Ponte Vedra Beach', 'state': 'FL', 'county': 'St. Johns', 'zip_code': '32082', 'lat': 30.2394,  'lng': -81.3883,  'device_lat': 30.23948,  'device_lng': -81.38815},
            {'business_name': 'Atlantic Beach City Hall',      'contact_name': 'Derrick Fowler',     'phone': '(904) 555-0688', 'city': 'Atlantic Beach',    'state': 'FL', 'county': 'Duval',     'zip_code': '32233', 'lat': 30.3371,  'lng': -81.3996,  'device_lat': 30.33718,  'device_lng': -81.39945},
            {'business_name': 'Neptune Beach HOA',             'contact_name': 'Beth Calloway',      'phone': '(904) 555-0712', 'city': 'Neptune Beach',     'state': 'FL', 'county': 'Duval',     'zip_code': '32266', 'lat': 30.3127,  'lng': -81.4027,  'device_lat': 30.31278,  'device_lng': -81.40255},
            {'business_name': 'Mandarin Presbyterian Church',  'contact_name': 'Pastor Dale Norris', 'phone': '(904) 555-0834', 'city': 'Jacksonville',      'state': 'FL', 'county': 'Duval',     'zip_code': '32223', 'lat': 30.1580,  'lng': -81.6243,  'device_lat': 30.15808,  'device_lng': -81.62415},
            {'business_name': 'Baymeadows Plaza',              'contact_name': 'Lisa Crane',         'phone': '(904) 555-0956', 'city': 'Jacksonville',      'state': 'FL', 'county': 'Duval',     'zip_code': '32256', 'lat': 30.2347,  'lng': -81.5513,  'device_lat': 30.23478,  'device_lng': -81.55115},
        ]
        for sc in SAMPLE_CUSTOMERS:
            Customer.objects.get_or_create(business_name=sc['business_name'], defaults=sc)
