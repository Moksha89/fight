# celery.py

from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from django.conf import settings

import logging

logger = logging.getLogger(__name__)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "kokoroko.settings")

app = Celery("kokoroko")
app.conf.enable_utc = False

app.conf.update(timezone="Asia/Kolkata")

app.config_from_object(settings, namespace="CELERY")

app.autodiscover_tasks()

app.conf.broker_connection_retry_on_startup = True

# Beat schedule file: /tmp on Linux/Docker (writable by non-root); Windows has no /tmp, use TEMP or cwd
if os.environ.get("CELERY_BEAT_SCHEDULE_FILE"):
    _beat_schedule_path = os.environ["CELERY_BEAT_SCHEDULE_FILE"]
elif os.name == "nt":  # Windows (local dev)
    _beat_schedule_path = os.path.join(os.environ.get("TEMP", os.getcwd()), "celerybeat-schedule")
else:
    _beat_schedule_path = "/tmp/celerybeat-schedule"
app.conf.beat_schedule_filename = _beat_schedule_path


@app.task(bind=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
