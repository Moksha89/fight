from celery import shared_task
from django.utils import timezone
from decimal import Decimal


@shared_task
def reset_payment_daily_limits():
    """
    Reset daily_credited for payment methods where 24hrs have passed.
    Auto-reenable disabled accounts if auto_disable_on_limit is True.
    Runs every 5 minutes via Celery Beat.
    """
    from wallet.models import PaymentQR, PaymentBankAccount

    now = timezone.now()
    count = 0

    for model in [PaymentQR, PaymentBankAccount]:
        for pm in model.objects.all():
            if pm.last_reset_at and (now - pm.last_reset_at).total_seconds() >= 86400:
                pm.daily_credited = Decimal('0')
                pm.last_reset_at = now
                if pm.auto_disable_on_limit and not pm.is_active:
                    pm.is_active = True
                pm.save(update_fields=['daily_credited', 'last_reset_at', 'is_active'])
                count += 1

    return f"Reset {count} payment method(s)"
