from django.apps import AppConfig


class CockfightmanagerConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cockfightManager'

    def ready(self):
        import cockfightManager.signals
