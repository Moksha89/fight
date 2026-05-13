from django.conf import settings
from django.core.files.storage import FileSystemStorage

AZURE_ACCOUNT_NAME = getattr(settings, "AZURE_ACCOUNT_NAME", None)

if AZURE_ACCOUNT_NAME:
    from storages.backends.azure_storage import AzureStorage

    class AzurePublicStorage(AzureStorage):
        account_name = AZURE_ACCOUNT_NAME
        account_key = getattr(settings, "AZURE_ACCOUNT_KEY", None)
        azure_container = getattr(settings, "AZURE_CONTAINER", "public-container")
        expiration_secs = None
else:
    class AzurePublicStorage(FileSystemStorage):
        def __init__(self, *args, **kwargs):
            kwargs.setdefault("location", str(settings.MEDIA_ROOT))
            kwargs.setdefault("base_url", settings.MEDIA_URL)
            super().__init__(*args, **kwargs)
