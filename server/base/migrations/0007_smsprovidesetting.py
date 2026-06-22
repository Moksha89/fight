from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('base', '0006_add_china_auto_enable_setting'),
    ]

    operations = [
        migrations.CreateModel(
            name='SmsProviderSetting',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('provider', models.CharField(choices=[('none', 'None / Disabled'), ('msg91', 'MSG91'), ('twilio', 'Twilio')], default='none', help_text='Active SMS provider for OTP delivery.', max_length=10)),
                ('is_enabled', models.BooleanField(default=False, help_text='Master switch — if off, no SMS is sent regardless of provider.')),
                ('default_country_code', models.CharField(default='91', help_text='Default country code for mobile numbers (e.g. 91 for India).', max_length=5)),
                ('msg91_auth_key_enc', models.TextField(blank=True, default='', verbose_name='MSG91 Auth Key (encrypted)')),
                ('msg91_template_id', models.CharField(blank=True, default='', max_length=200, verbose_name='MSG91 Template ID')),
                ('msg91_sender_id', models.CharField(blank=True, default='', max_length=20, verbose_name='MSG91 Sender ID / Header')),
                ('msg91_route', models.CharField(blank=True, default='', max_length=10, verbose_name='MSG91 Route')),
                ('msg91_entity_id', models.CharField(blank=True, default='', max_length=100, verbose_name='MSG91 DLT Entity ID')),
                ('msg91_base_url', models.URLField(blank=True, default='https://control.msg91.com/api/v5/otp', verbose_name='MSG91 API Base URL')),
                ('twilio_account_sid_enc', models.TextField(blank=True, default='', verbose_name='Twilio Account SID (encrypted)')),
                ('twilio_auth_token_enc', models.TextField(blank=True, default='', verbose_name='Twilio Auth Token (encrypted)')),
                ('twilio_from_number', models.CharField(blank=True, default='', max_length=20, verbose_name='Twilio From Number')),
                ('twilio_messaging_service_sid', models.CharField(blank=True, default='', max_length=100, verbose_name='Twilio Messaging Service SID')),
                ('otp_message_template', models.CharField(blank=True, default='Your KOKOROKO OTP is {otp}. It is valid for 5 minutes. Do not share it with anyone.', help_text='OTP message template. Use {otp} as placeholder.', max_length=500)),
                ('last_test_status', models.CharField(blank=True, choices=[('', 'Never tested'), ('success', 'Success'), ('failed', 'Failed')], default='', max_length=20)),
                ('last_test_error', models.TextField(blank=True, default='')),
                ('last_test_at', models.DateTimeField(blank=True, null=True)),
                ('last_test_mobile', models.CharField(blank=True, default='', max_length=20)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('updated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'SMS Provider Setting',
                'verbose_name_plural': 'SMS Provider Settings',
            },
        ),
    ]
