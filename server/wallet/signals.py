from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Wallet
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


@receiver(post_save, sender=Wallet)
def wallet_updated(sender, instance, **kwargs):
    instance.refresh_from_db()
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{instance.user.id}_wallet",
        {
            "type": "send_wallet_update",
            "balance": str(instance.balance),
            "bonusDebt": str(instance.bonusDebt),
            "updated_at": instance.updated_at.isoformat(),
        }
    )
