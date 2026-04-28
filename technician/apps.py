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

    def _seed_demo_users(self):
        from django.contrib.auth.models import User
        from .models import UserProfile
        DEMO_USERS = [
            ('technician', 'tech123', 'John',   'Smith',   'technician'),
            ('operations', 'ops123',  'Sarah',  'Johnson', 'operations'),
            ('manager',    'mgr123',  'Robert', 'Wolf',    'manager'),
            ('admin',      'admin123','Admin',  'Wolf',    'admin'),
            ('customer',   'cust123', 'James',  'Wilson',  'customer'),
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
