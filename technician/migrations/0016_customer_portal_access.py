from django.db import migrations, models
import django.db.models.deletion


def set_demo_portal_passwords(apps, schema_editor):
    Customer = apps.get_model('technician', 'Customer')
    Customer.objects.filter(demo=True).update(portal_password='test123')


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0012_alter_user_first_name_max_length'),
        ('technician', '0015_rename_customer_tables'),
    ]

    operations = [
        migrations.AddField(
            model_name='customer',
            name='portal_password',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='customer',
            name='linked_user',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='customer_account',
                to='auth.user',
            ),
        ),
        migrations.RunPython(set_demo_portal_passwords, migrations.RunPython.noop),
    ]
