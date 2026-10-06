# Generated to remove legacy Fincra/Interac gateway — Stripe is now the sole gateway.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('Account', '0020_fincra_cad_models'),
    ]

    operations = [
        migrations.DeleteModel(
            name='FincraCadAccount',
        ),
        migrations.DeleteModel(
            name='FincraCollection',
        ),
        migrations.DeleteModel(
            name='InteracPaymentRequest',
        ),
        migrations.AlterField(
            model_name='employerpayment',
            name='payment_reference',
            field=models.CharField(
                blank=True,
                help_text='Stripe payment reference',
                max_length=200,
            ),
        ),
    ]
