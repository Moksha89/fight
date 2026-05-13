from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now

from .models import Zone, CockfightMatch


@receiver(post_save, sender=Zone)
def create_default_cockfight_match(sender, instance, created, **kwargs):
    if created:
        CockfightMatch.objects.create(
            zone=instance,
            title=now().strftime("Match %Y-%m-%d %H:%M:%S"),
            isLive=False,
            liveDate=None
        )
