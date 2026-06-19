"""Add performance indexes to WalletHistory, DepositRequest, WithdrawalRequest."""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("wallet", "0007_wallet_balance_constraints"),
    ]

    operations = [
        # WalletHistory: wallet + created_at DESC (for history listing with sort)
        migrations.AddIndex(
            model_name="wallethistory",
            index=models.Index(
                fields=["wallet", "-created_at"],
                name="wallet_wh_wallet_created_idx",
            ),
        ),
        # WalletHistory: transaction_type + isSuccess + created_at DESC (admin summaries)
        migrations.AddIndex(
            model_name="wallethistory",
            index=models.Index(
                fields=["transaction_type", "isSuccess", "-created_at"],
                name="wallet_wh_type_success_idx",
            ),
        ),
        # WalletHistory: created_at DESC (recent transactions)
        migrations.AddIndex(
            model_name="wallethistory",
            index=models.Index(
                fields=["-created_at"],
                name="wallet_wh_created_desc_idx",
            ),
        ),
        # DepositRequest: utr_id (duplicate UTR check)
        migrations.AddIndex(
            model_name="depositrequest",
            index=models.Index(
                fields=["utr_id"],
                name="wallet_dr_utr_id_idx",
            ),
        ),
        # DepositRequest: status + created_at DESC (admin pending list)
        migrations.AddIndex(
            model_name="depositrequest",
            index=models.Index(
                fields=["status", "-created_at"],
                name="wallet_dr_status_created_idx",
            ),
        ),
        # WithdrawalRequest: status + created_at DESC (admin pending list)
        migrations.AddIndex(
            model_name="withdrawalrequest",
            index=models.Index(
                fields=["status", "-created_at"],
                name="wallet_wr_status_created_idx",
            ),
        ),
    ]
