from django.apps import AppConfig


class WalletConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'wallet'
    icon_name = 'account_balance_wallet'

    def ready(self):
        import wallet.signals
