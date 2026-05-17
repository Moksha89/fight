import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import DicePlayMatch
from .utils import broadcast_dice_match_update


@receiver(post_save, sender=DicePlayMatch)
def on_dice_play_match_saved(sender, instance, **kwargs):
    """Broadcast match list update so clients get latest isBettingEnabled, isLive, etc."""
    try:
        broadcast_dice_match_update()
    except Exception:
        logging.exception("Failed to broadcast dice match update after save")
