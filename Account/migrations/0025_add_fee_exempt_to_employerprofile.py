from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Account', '0024_add_caregiver_moderation_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='employerprofile',
            name='fee_exempt',
            field=models.BooleanField(
                default=False,
                help_text='True when employer registered while activation fee was disabled — permanent free access.',
            ),
        ),
    ]
