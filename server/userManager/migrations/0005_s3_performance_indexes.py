"""Add performance indexes to OtpStack."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("userManager", "0004_passwordresettoken"),
    ]

    operations = [
        # OtpStack: mobile + otp (OTP verification lookup)
        migrations.AddIndex(
            model_name="otpstack",
            index=models.Index(
                fields=["mobile", "otp"],
                name="otp_mobile_otp_idx",
            ),
        ),
        # OtpStack: created_at (expired OTP cleanup)
        migrations.AddIndex(
            model_name="otpstack",
            index=models.Index(
                fields=["created_at"],
                name="otp_created_at_idx",
            ),
        ),
    ]
