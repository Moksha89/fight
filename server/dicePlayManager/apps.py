from django.apps import AppConfig


class DiceplaymanagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dicePlayManager'

    def ready(self):
        import dicePlayManager.signals  # noqa: F401
