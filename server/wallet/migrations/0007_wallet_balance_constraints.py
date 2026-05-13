"""Add CHECK constraints to prevent negative wallet balance, fundsIn, fundsOut.

MySQL 8.0.16+ enforces CHECK constraints.  Existing data has been verified
to contain no negative values.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wallet", "0006_add_withdrawal_speed_type"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="wallet",
            constraint=models.CheckConstraint(
                check=models.Q(balance__gte=0),
                name="wallet_balance_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="wallet",
            constraint=models.CheckConstraint(
                check=models.Q(fundsIn__gte=0),
                name="wallet_funds_in_non_negative",
            ),
        ),
        migrations.AddConstraint(
            model_name="wallet",
            constraint=models.CheckConstraint(
                check=models.Q(fundsOut__gte=0),
                name="wallet_funds_out_non_negative",
            ),
        ),
    ]
