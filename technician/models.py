from django.db import models
from django.contrib.auth.models import User


class UserProfile(models.Model):
    ROLES = [
        ('technician', 'Technician'),
        ('operations', 'Operations'),
        ('manager', 'Manager'),
        ('admin', 'Administrator'),
        ('customer', 'Customer'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLES, default='technician')
    phone = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.role})"


class Customer(models.Model):
    business_name = models.CharField(max_length=200)
    contact_name = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=300, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, default='FL')
    county = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['business_name']

    def __str__(self):
        return self.business_name


class Job(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    DEVICE_TYPES = [
        ('RPZ', 'RPZ — Reduced Pressure Zone'),
        ('DCVA', 'DCVA — Double Check Valve'),
        ('PVB', 'PVB — Pressure Vacuum Breaker'),
        ('SVB', 'SVB — Spill-Resistant Vacuum Breaker'),
        ('RPDA', 'RPDA — Reduced Pressure Detector'),
    ]

    customer_ref = models.ForeignKey(
        Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name='jobs'
    )
    customer = models.CharField(max_length=200)
    address = models.CharField(max_length=300)
    contact = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    state = models.CharField(max_length=2, default='FL', blank=True)
    county = models.CharField(max_length=100, blank=True)

    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_jobs'
    )

    device_type = models.CharField(max_length=10, choices=DEVICE_TYPES, default='RPZ')
    device_size = models.CharField(max_length=10, blank=True)
    device_make = models.CharField(max_length=100, blank=True)
    device_model = models.CharField(max_length=100, blank=True)
    serial = models.CharField(max_length=100, blank=True)
    device_notes = models.TextField(blank=True)

    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    device_lat = models.FloatField(null=True, blank=True)
    device_lng = models.FloatField(null=True, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['scheduled_date', 'scheduled_time']

    def __str__(self):
        return f"{self.customer} — {self.scheduled_date} {self.scheduled_time}"


class TestResult(models.Model):
    CV_RESULTS = [
        ('closed', 'Closed'),
        ('leaked', 'Leaked'),
        ('opened', 'Opened at PSI'),
    ]
    RV_RESULTS = [
        ('opened_ok', 'Opened OK'),
        ('did_not_open', 'Did Not Open'),
        ('leaked', 'Leaked'),
    ]
    OVERALL = [
        ('pass', 'Pass'),
        ('fail', 'Fail'),
    ]

    job = models.ForeignKey(Job, on_delete=models.SET_NULL, null=True, blank=True, related_name='test_results')
    customer = models.CharField(max_length=200)
    address = models.CharField(max_length=300)

    device_type = models.CharField(max_length=10)
    device_size = models.CharField(max_length=10)
    manufacturer = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    serial = models.CharField(max_length=100)
    install_year = models.IntegerField(null=True, blank=True)

    test_date = models.DateField()
    test_time = models.TimeField()

    cv1_result = models.CharField(max_length=20, choices=CV_RESULTS, blank=True)
    cv1_psi = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    cv2_result = models.CharField(max_length=20, choices=CV_RESULTS, blank=True)
    cv2_psi = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    rv_result = models.CharField(max_length=20, choices=RV_RESULTS, blank=True)
    rv_psi = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)
    line_psi = models.DecimalField(max_digits=6, decimal_places=1, null=True, blank=True)

    overall_result = models.CharField(max_length=10, choices=OVERALL)
    notes = models.TextField(blank=True)
    technician_initials = models.CharField(max_length=4)
    submitted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='test_submissions'
    )

    submitted_at = models.DateTimeField(auto_now_add=True)
    utility_submitted = models.BooleanField(default=False)
    utility_submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.customer} — {self.test_date} — {self.overall_result.upper()}"