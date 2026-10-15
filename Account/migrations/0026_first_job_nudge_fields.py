from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Account', '0025_add_fee_exempt_to_employerprofile'),
    ]

    operations = [
        migrations.AddField(
            model_name='employerprofile',
            name='last_first_job_reminder_sent',
            field=models.DateTimeField(
                blank=True,
                help_text='Last time a "post your first job" reminder email was sent',
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='employerprofile',
            name='last_first_job_modal_shown',
            field=models.DateTimeField(
                blank=True,
                help_text='Last time the "create job post" popup was shown (weekly throttle)',
                null=True,
            ),
        ),
    ]
