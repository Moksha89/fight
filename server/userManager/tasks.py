from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.utils import timezone
from datetime import timedelta

from userManager.models import User, OtpStack


@shared_task
def expire_subscriptions():

    threshold = timezone.now() - timedelta(days=30)
    expired_users = User.objects.filter(
        isSubscribed=True, lastSubscribedAt__lt=threshold)

    for user in expired_users:
        user.isSubscribed = False
        user.save()


@shared_task
def delete_expired_otps():
    threshold = timezone.now() - timedelta(minutes=10)
    deleted, _ = OtpStack.objects.filter(created_at__lt=threshold).delete()
    return f"Deleted {deleted} expired OTPs"


@shared_task
def sendEmailOtp(email, otp):
    subject = f"{otp} is your email OTP"
    from_email = 'Kokoroko <no-reply@kokoroko.app>'
    recipient_list = [email]

    context = {
        'otp': otp,
        'current_year': now().year,
    }

    try:
        html_content = render_to_string(
            'emailTemplates/emailOtp.html', context)
        text_content = f"Your OTP is: {otp}"

        send_mail(
            subject=subject,
            message=text_content,
            from_email=from_email,
            recipient_list=recipient_list,
            fail_silently=False,
            html_message=html_content
        )
        print("OTP email sent successfully")
    except Exception as e:
        print(f"Error sending OTP email: {e}")
