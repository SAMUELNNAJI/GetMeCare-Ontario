"""
Migration: add account_status, status_reason, status_changed_at to CaregiverProfile.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Account', '0023_add_hourly_rate_reminder_field'),
    ]

    operations = [
        migrations.AddField(
            model_name='caregiverprofile',
            name='account_status',
            field=models.CharField(
                choices=[
                    ('active', 'Active'),
                    ('suspended', 'Suspended'),
                    ('deactivated', 'Deactivated'),
                ],
                default='active',
                help_text='Admin-controlled moderation status',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='caregiverprofile',
            name='status_reason',
            field=models.TextField(
                blank=True,
                help_text='Reason given to caregiver for suspension/deactivation',
            ),
        ),
        migrations.AddField(
            model_name='caregiverprofile',
            name='status_changed_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='When account_status was last changed by admin',
            ),
        ),
    ]
