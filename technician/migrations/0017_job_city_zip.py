from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('technician', '0016_customer_portal_access'),
    ]

    operations = [
        migrations.AddField(
            model_name='job',
            name='city',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.AddField(
            model_name='job',
            name='zip_code',
            field=models.CharField(blank=True, max_length=10),
        ),
    ]
