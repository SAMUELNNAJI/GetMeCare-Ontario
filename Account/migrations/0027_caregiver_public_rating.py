import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('Account', '0026_first_job_nudge_fields')]

    operations = [
        migrations.CreateModel(
            name='CaregiverReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.PositiveSmallIntegerField()),
                ('comment', models.TextField(blank=True, max_length=1000)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('caregiver', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='received_caregiver_reviews', to=settings.AUTH_USER_MODEL)),
                ('employer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submitted_caregiver_reviews', to=settings.AUTH_USER_MODEL)),
                ('shift', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='review', to='Account.shift')),
            ],
            options={'ordering': ['-created_at']},
        ),
    ]
