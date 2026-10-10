from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('AdminApp', '0004_update_service_descriptions'),
    ]

    operations = [
        migrations.CreateModel(
            name='SiteSettings',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False)),
                ('activation_fee_enabled', models.BooleanField(
                    default=True,
                    help_text=(
                        'When ON: new employers must pay the $39.99 activation fee. '
                        'When OFF: all employers get instant free access.'
                    ),
                )),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Site Settings',
                'verbose_name_plural': 'Site Settings',
            },
        ),
    ]
