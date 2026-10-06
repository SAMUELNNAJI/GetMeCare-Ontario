"""
Migration: add last_hourly_rate_reminder_sent to CaregiverProfile.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Account', '0022_add_employer_moderation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='caregiverprofile',
            name='last_hourly_rate_reminder_sent',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='Last time a "set your hourly rate" reminder email was sent',
            ),
        ),
    ]
