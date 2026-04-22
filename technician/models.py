from django.db import models


class TestResult(models.Model):
    DEVICE_TYPES = [
        ('RPZ', 'RPZ — Reduced Pressure Zone'),
        ('DCVA', 'DCVA — Double Check Valve'),
        ('PVB', 'PVB — Pressure Vacuum Breaker'),
        ('SVB', 'SVB — Spill-Resistant Vacuum Breaker'),
        ('RPDA', 'RPDA — Reduced Pressure Detector'),
    ]
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

    # Job reference (matches hardcoded SAMPLE_JOBS id for POC)
    job_id = models.IntegerField()
    customer = models.CharField(max_length=200)
    address = models.CharField(max_length=300)

    # Device identity
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPES)
    device_size = models.CharField(max_length=10)
    manufacturer = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    serial = models.CharField(max_length=100)
    install_year = models.IntegerField(null=True, blank=True)

    # Test readings
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

    submitted_at = models.DateTimeField(auto_now_add=True)

    # Future: utility API submission tracking
    utility_submitted = models.BooleanField(default=False)
    utility_submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.customer} — {self.test_date} — {self.overall_result.upper()}"
