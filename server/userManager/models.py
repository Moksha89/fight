from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.conf import settings
import hashlib
import secrets
import time

from django.utils import timezone

from wallet.models import Wallet


class Room(models.Model):
    name = models.CharField(max_length=100, unique=True)
    manager = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="managed_room"
    )

    class Meta:
        verbose_name = "Room"
        verbose_name_plural = "1. Rooms"

    def __str__(self):
        return self.name



# =================================================================
#                         Global Otp Stack                        ||
# =================================================================

class OtpStack(models.Model):
    id = models.CharField(max_length=40, primary_key=True)
    email = models.EmailField(null=True, blank=True)
    mobile = models.CharField(max_length=15, null=True, blank=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.pk:
            timeStr = str(time.time())
            identifier = self.mobile or self.email or 'unknown'
            self.id = f"{identifier[0:10]}{self.otp}" + \
                timeStr[0:8] + timeStr[-6:-1]
        super(OtpStack, self).save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=["email"]),
            models.Index(fields=["mobile"]),
            models.Index(fields=["mobile", "otp"]),
            models.Index(fields=["created_at"]),
        ]


# =================================================================
#                          User & Profiles                       ||
# =================================================================

def getHashCode(email, username):
    data = str(settings.SECRET_KEY) + str(email) + str(username)
    hashed = hashlib.sha256(data.encode()).hexdigest()
    return str(hashed[:2] + hashed[10:12] + hashed[-7:-1])


class User(AbstractUser):
    first_name = None
    last_name = None
    date_joined = None
    id = models.CharField(max_length=10, primary_key=True, editable=False)
    username = models.CharField(max_length=50, null=True)
    email = models.EmailField(unique=True)
    phoneNumber = models.CharField(max_length=15, unique=True, null=True, blank=True)
    dateOfBirth = models.DateField(null=True, blank=True)
    isSubscribed = models.BooleanField(default=False)
    lastSubscribedAt = models.DateTimeField(null=True, blank=True)
    joinedDate = models.DateTimeField(auto_now_add=True)
    room = models.ForeignKey(Room, on_delete=models.PROTECT, null=True, related_name="users")
    GENDER_CHOICES = (
        ("M", "Male"),
        ("F", "Female"),
    )
    gender = models.CharField(
        max_length=1, choices=GENDER_CHOICES, null=True, blank=True
    )

    # set Verify to True if OTP Verification Done
    isVerified = models.BooleanField(default=False)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def save(self, *args, **kwargs):
        if not self.pk:
            self.id = getHashCode(self.email, self.username)
        super(User, self).save(*args, **kwargs)
        

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "2. Users"
        indexes = [
            models.Index(fields=["id"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.username} - {self.phoneNumber}"



class SettlementBox(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="settlement")
    verifiedValue = models.DecimalField(default=0, decimal_places=2, max_digits=12)
    collectedValue = models.DecimalField(default=0, decimal_places=2, max_digits=12)
    isProcessed = models.BooleanField(default=False)
    processedId = models.ForeignKey('SettlementBox', on_delete=models.PROTECT, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Settlement"
        verbose_name_plural = "3. Settlements"
        ordering = ["-updated_at"]

    def __str__(self):
        return f"Settlement for {self.user}"



class SettlementHistory(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('D', 'Deposit'),
        ('W', 'Withdrawal'),
    )
    settlementBox = models.ForeignKey(SettlementBox, on_delete=models.CASCADE, related_name="settlement_histories")
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="customer_transactions", null=True, blank=True)
    transaction_type = models.CharField(max_length=1, choices=TRANSACTION_TYPE_CHOICES)
    utr_id = models.CharField(max_length=100, unique=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Settlement History"
        verbose_name_plural = "4. Settlement Histories"
        ordering = ['-timestamp']


    def __str__(self):
        return f"{self.get_transaction_type_display()} of {self.amount} by {self.settlementBox}"


# =================================================================
#                    Password Reset Token                         ||
# =================================================================

class PasswordResetToken(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="password_reset_tokens",
    )
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=200, blank=True, default="")

    EXPIRY_MINUTES = 15

    class Meta:
        verbose_name = "Password Reset Token"
        verbose_name_plural = "5. Password Reset Tokens"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reset token for {self.user} ({'used' if self.used_at else 'active'})"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_valid(self):
        return not self.is_expired and not self.is_used

    @classmethod
    def create_for_user(cls, user, ip_address=None, user_agent=""):
        raw_token = secrets.token_urlsafe(48)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expires_at = timezone.now() + timezone.timedelta(minutes=cls.EXPIRY_MINUTES)
        obj = cls.objects.create(
            user=user,
            token_hash=token_hash,
            expires_at=expires_at,
            ip_address=ip_address,
            user_agent=user_agent[:200],
        )
        return obj, raw_token

    @classmethod
    def validate_token(cls, raw_token):
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        try:
            obj = cls.objects.select_related("user").get(token_hash=token_hash)
        except cls.DoesNotExist:
            return None, "Invalid reset token."
        if obj.is_used:
            return None, "Reset token has already been used."
        if obj.is_expired:
            return None, "Reset token has expired."
        return obj, None

    def mark_used(self):
        self.used_at = timezone.now()
        self.save(update_fields=["used_at"])
