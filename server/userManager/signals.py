from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from userManager.models import SettlementBox, User
from wallet.models import Wallet

@receiver(post_save, sender=User)
def create_related_records(sender, instance, created, **kwargs):
    if created:
        Wallet.objects.get_or_create(user=instance)

        if instance.is_staff:
            SettlementBox.objects.get_or_create(user=instance, isProcessed=False)
