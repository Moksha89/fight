from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('wallet', '0004_depositrequest_status_paymentbankaccount_min_deposit_and_more'),
    ]

    operations = [
        # PaymentQR enhancements
        migrations.AddField(
            model_name='paymentqr',
            name='daily_limit',
            field=models.DecimalField(
                max_digits=12, decimal_places=2, default=0,
                help_text='Max amount that can be credited via this QR in 24hrs. 0 = unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='paymentqr',
            name='daily_credited',
            field=models.DecimalField(max_digits=12, decimal_places=2, default=0),
        ),
        migrations.AddField(
            model_name='paymentqr',
            name='last_reset_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='paymentqr',
            name='auto_disable_on_limit',
            field=models.BooleanField(
                default=True,
                help_text='Auto-disable when daily limit reached; auto-reenable after 24hrs'
            ),
        ),
        migrations.AddField(
            model_name='paymentqr',
            name='rotation_priority',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Lower number = shown first. Used for auto-rotation.'
            ),
        ),
        migrations.AddField(
            model_name='paymentqr',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),

        # PaymentBankAccount enhancements
        migrations.AddField(
            model_name='paymentbankaccount',
            name='account_holder_name',
            field=models.CharField(max_length=100, default=''),
        ),
        migrations.AddField(
            model_name='paymentbankaccount',
            name='account_type',
            field=models.CharField(
                max_length=1,
                choices=[('S', 'Savings'), ('C', 'Current')],
                default='S'
            ),
        ),
        migrations.AddField(
            model_name='paymentbankaccount',
            name='daily_limit',
            field=models.DecimalField(
                max_digits=12, decimal_places=2, default=0,
                help_text='Max amount that can be credited via this account in 24hrs. 0 = unlimited.'
            ),
        ),
        migrations.AddField(
            model_name='paymentbankaccount',
            name='daily_credited',
            field=models.DecimalField(max_digits=12, decimal_places=2, default=0),
        ),
        migrations.AddField(
            model_name='paymentbankaccount',
            name='last_reset_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
        ),
        migrations.AddField(
            model_name='paymentbankaccount',
            name='auto_disable_on_limit',
            field=models.BooleanField(
                default=True,
                help_text='Auto-disable when daily limit reached; auto-reenable after 24hrs'
            ),
        ),
        migrations.AddField(
            model_name='paymentbankaccount',
            name='rotation_priority',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Lower number = shown first.'
            ),
        ),
        migrations.AddField(
            model_name='paymentbankaccount',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),

        # WithdrawalRequest enhancements - add screenshot & created_at
        migrations.AddField(
            model_name='withdrawalrequest',
            name='admin_screenshot',
            field=models.ImageField(upload_to='withdrawal_proofs/', null=True, blank=True),
        ),
        migrations.AddField(
            model_name='withdrawalrequest',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),

        # DepositRequest - add created_at
        migrations.AddField(
            model_name='depositrequest',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),

        # Update verbose names for merged view
        migrations.AlterModelOptions(
            name='paymentqr',
            options={'verbose_name': 'UPI / QR Code', 'verbose_name_plural': '1. Payment Methods - UPI/QR', 'ordering': ['rotation_priority', 'id']},
        ),
        migrations.AlterModelOptions(
            name='paymentbankaccount',
            options={'verbose_name': 'Bank Account', 'verbose_name_plural': '1b. Payment Methods - Bank', 'ordering': ['rotation_priority', 'id']},
        ),
    ]
