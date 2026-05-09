from django.db import migrations, models
from decimal import Decimal


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0005_payment_methods_upgrade'),
    ]

    operations = [
        migrations.AddField(
            model_name='withdrawalrequest',
            name='speed_type',
            field=models.CharField(
                max_length=1,
                choices=[('N', 'Normal'), ('E', 'Express')],
                default='N',
                help_text='Normal: up to 6hrs, Express: up to 30mins (2.5% fee)',
            ),
        ),
        migrations.AddField(
            model_name='withdrawalrequest',
            name='fee_amount',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, default=0,
                help_text='Fee deducted for Express withdrawal (2.5%)',
            ),
        ),
        migrations.AddField(
            model_name='withdrawalrequest',
            name='payout_amount',
            field=models.DecimalField(
                max_digits=10, decimal_places=2, default=0,
                help_text='Amount user receives after fee deduction',
            ),
        ),
    ]
