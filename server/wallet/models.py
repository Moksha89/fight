from django.db import models
import hashlib
import uuid
from django.conf import settings
from utility.storageClasses import AzurePublicStorage
from django.db import models, transaction
from django.utils import timezone

from decimal import Decimal

from django.db.models import F

# ========================= Customer Wallet ======================


class Wallet(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wallet", primary_key=True)
    balance = models.DecimalField(default=0, decimal_places=2, max_digits=12)
    bonusDebt = models.DecimalField(default=0, decimal_places=2, max_digits=12)
    fundsIn = models.DecimalField(default=0, decimal_places=2, max_digits=12)
    fundsOut = models.DecimalField(default=0, decimal_places=2, max_digits=12)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def exposure(self):
        """Total amount in unsettled bets (matchWinStatus=0 or null)."""
        from cockfightManager.models import CockfightMatchBet
        from django.db.models import Sum
        total = CockfightMatchBet.objects.filter(
            customer=self.user, matchWinStatus=0
        ).aggregate(t=Sum('amount'))['t']
        return total or Decimal('0.00')

    @property
    def available_balance(self):
        """Balance minus exposure and bonus debt."""
        return self.balance - self.bonusDebt - self.exposure

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.balance < 0:
            raise ValidationError({"balance": "Wallet balance cannot be negative."})
        if self.fundsIn < 0:
            raise ValidationError({"fundsIn": "Funds-in cannot be negative."})
        if self.fundsOut < 0:
            raise ValidationError({"fundsOut": "Funds-out cannot be negative."})

    def __str__(self):
        return f"Wallet of {self.user}"

    class Meta:
        verbose_name = "Wallet"
        verbose_name_plural = "5. Wallets"
        ordering = ['-balance']
        constraints = [
            models.CheckConstraint(
                check=models.Q(balance__gte=0),
                name="wallet_balance_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(fundsIn__gte=0),
                name="wallet_funds_in_non_negative",
            ),
            models.CheckConstraint(
                check=models.Q(fundsOut__gte=0),
                name="wallet_funds_out_non_negative",
            ),
        ]


# ========================= Customer Wallet History ======================
class WalletHistory(models.Model):
    wallet = models.ForeignKey(
        Wallet, on_delete=models.CASCADE, related_name="history")

    TRANSACTION_TYPE_CHOICES = (
        ('D', 'Deposit'),
        ('W', 'Withdrawal'),
        ('B', 'Bonus'),
        ('L', 'Lottery'),
        ('F', 'Cockfight'),
        ('C', 'Cricket'),
        ('S', 'Subscription'),
        ('I', 'Dice Play'),
    )

    transactionHash = models.CharField(
        max_length=64, unique=True, null=True, blank=True, db_index=True)
    transaction_type = models.CharField(
        max_length=1, choices=TRANSACTION_TYPE_CHOICES)
    transactionId = models.CharField(max_length=50, null=True, blank=True)
    change = models.DecimalField(decimal_places=2, max_digits=12)
    isSuccess = models.BooleanField()
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self._state.adding
        if not self.transactionHash:
            raw = f"{uuid.uuid4().hex}{self.wallet_id}{self.transaction_type}{self.change}"
            self.transactionHash = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()

        with transaction.atomic():
            super().save(*args, **kwargs)

            wallet = self.wallet

            if is_new and self.transaction_type == 'D' and self.isSuccess:

                is_first_deposit = not WalletHistory.objects.filter(
                    wallet=wallet, transaction_type='D', isSuccess=True
                ).exclude(pk=self.pk).exists()

                bonus_settings = BonusRange.objects.filter(
                    min_deposit__lte=self.change
                ).order_by('-min_deposit')

                if not is_first_deposit:
                    bonus_settings = bonus_settings.exclude(
                        only_first_deposit=True)

                # Step 3: Evaluate best bonus
                bonus = None
                max_bonus_value = Decimal('0')

                for setting in bonus_settings:
                    if setting.bonus_type == 'P':
                        calculated_bonus = (self.change * setting.bonus_value /
                                            Decimal('100')).quantize(Decimal('0.01'))
                    else:  # Flat bonus
                        calculated_bonus = setting.bonus_value

                    if calculated_bonus > max_bonus_value:
                        max_bonus_value = calculated_bonus
                        bonus = setting

                if bonus:
                    bonus_amount = (self.change * bonus.bonus_value /
                                    100) if bonus.bonus_type == 'P' else bonus.bonus_value

                    if bonus and bonus_amount > 0:
                        wallet.balance = F('balance') + bonus_amount
                        wallet.bonusDebt = F('bonusDebt') + bonus_amount
                        wallet.save()

                    WalletHistory.objects.create(
                        wallet=wallet,
                        transaction_type='B',
                        change=bonus_amount,
                        isSuccess=True,
                        description=f"Bonus of {bonus_amount} for deposit of {self.change}"
                    )

            elif is_new and self.transaction_type == 'W' and self.isSuccess:
                walletBonus = wallet.bonusDebt
                if wallet.bonusDebt > 0:
                    wallet.balance = F('balance') - walletBonus
                    wallet.bonusDebt = 0
                    wallet.save()

                    WalletHistory.objects.create(
                        wallet=wallet,
                        transaction_type='B',
                        change=walletBonus,
                        isSuccess=False,
                        description=f"Wallet bonus set to 0."
                    )

    def __str__(self):
        return f"WalletHistory for {self.wallet.user}"

    class Meta:
        indexes = [
            models.Index(fields=['wallet']),
            models.Index(fields=['wallet', '-created_at']),
            models.Index(fields=['transaction_type', 'isSuccess', '-created_at']),
            models.Index(fields=['-created_at']),
        ]
        verbose_name = "Wallet History"
        verbose_name_plural = "7. Wallet History"


class PaymentQR(models.Model):
    upi_id = models.CharField(max_length=100)
    display_name = models.CharField(max_length=100)
    qr_image = models.FileField(
        storage=AzurePublicStorage(), upload_to='qr_codes/')
    is_active = models.BooleanField(default=True)
    min_deposit = models.PositiveIntegerField(default=100)
    max_deposit = models.PositiveIntegerField()
    daily_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Max amount credited via this QR in 24hrs. 0 = unlimited.')
    daily_credited = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Amount credited today. Resets automatically after 24hrs.')
    last_reset_at = models.DateTimeField(default=timezone.now)
    auto_disable_on_limit = models.BooleanField(
        default=True,
        help_text='If checked, auto-disables when daily limit reached and re-enables after 24hrs. Uncheck to keep showing even after limit.')
    rotation_priority = models.PositiveIntegerField(
        default=0, help_text='Lower = shown first. Auto-rotation cycles through QRs.')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='payment_qrs')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def check_and_update_limit(self):
        """Check if 24hrs passed since last reset and reset daily_credited."""
        if self.last_reset_at and (timezone.now() - self.last_reset_at).total_seconds() >= 86400:
            self.daily_credited = Decimal('0')
            self.last_reset_at = timezone.now()
            if self.auto_disable_on_limit and not self.is_active:
                self.is_active = True
            self.save(update_fields=['daily_credited', 'last_reset_at', 'is_active'])

    def add_credit(self, amount):
        """Track credited amount and auto-disable if limit reached."""
        self.daily_credited = F('daily_credited') + Decimal(str(amount))
        self.save(update_fields=['daily_credited'])
        self.refresh_from_db()
        if self.daily_limit > 0 and self.daily_credited >= self.daily_limit and self.auto_disable_on_limit:
            self.is_active = False
            self.save(update_fields=['is_active'])

    @property
    def limit_remaining(self):
        if self.daily_limit <= 0:
            return None  # unlimited
        return max(Decimal('0'), self.daily_limit - self.daily_credited)

    def __str__(self):
        return f"{self.display_name} ({self.upi_id})"

    class Meta:
        verbose_name = "UPI / QR Code"
        verbose_name_plural = "1. Payment Methods - UPI/QR"
        ordering = ['rotation_priority', 'id']


class PaymentBankAccount(models.Model):
    ACCOUNT_TYPE_CHOICES = (
        ('S', 'Savings'),
        ('C', 'Current'),
    )
    account_holder_name = models.CharField(max_length=100, default='')
    bank_name = models.CharField(max_length=50)
    account_number = models.CharField(max_length=50)
    ifsc_code = models.CharField(max_length=20)
    account_type = models.CharField(max_length=1, choices=ACCOUNT_TYPE_CHOICES, default='S')
    is_active = models.BooleanField(default=True)
    min_deposit = models.PositiveIntegerField(default=100)
    max_deposit = models.PositiveIntegerField()
    daily_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Max amount credited via this account in 24hrs. 0 = unlimited.')
    daily_credited = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Amount credited today. Resets automatically after 24hrs.')
    last_reset_at = models.DateTimeField(default=timezone.now)
    auto_disable_on_limit = models.BooleanField(
        default=True,
        help_text='If checked, auto-disables when daily limit reached and re-enables after 24hrs. Uncheck to keep showing even after limit.')
    rotation_priority = models.PositiveIntegerField(
        default=0, help_text='Lower = shown first.')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='bank_accounts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def check_and_update_limit(self):
        """Check if 24hrs passed since last reset and reset daily_credited."""
        if self.last_reset_at and (timezone.now() - self.last_reset_at).total_seconds() >= 86400:
            self.daily_credited = Decimal('0')
            self.last_reset_at = timezone.now()
            if self.auto_disable_on_limit and not self.is_active:
                self.is_active = True
            self.save(update_fields=['daily_credited', 'last_reset_at', 'is_active'])

    def add_credit(self, amount):
        """Track credited amount and auto-disable if limit reached."""
        self.daily_credited = F('daily_credited') + Decimal(str(amount))
        self.save(update_fields=['daily_credited'])
        self.refresh_from_db()
        if self.daily_limit > 0 and self.daily_credited >= self.daily_limit and self.auto_disable_on_limit:
            self.is_active = False
            self.save(update_fields=['is_active'])

    @property
    def limit_remaining(self):
        if self.daily_limit <= 0:
            return None  # unlimited
        return max(Decimal('0'), self.daily_limit - self.daily_credited)

    def __str__(self):
        return f"{self.bank_name} - {self.account_holder_name} ({self.account_number[-4:]})"

    class Meta:
        verbose_name = "Bank Account"
        verbose_name_plural = "1b. Payment Methods - Bank"
        ordering = ['rotation_priority', 'id']


class DepositRequest(models.Model):
    DEPOSIT_TYPE_CHOICES = (
        ('Q', 'QR'),
        ('B', 'Bank Account'),
    )
    STATUS_CHOICES = (
        ('P', 'Pending'),
        ('A', 'Accepted'),
        ('R', 'Rejected'),
    )
    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='P', db_index=True)
    screenShort = models.FileField(
        storage=AzurePublicStorage(), upload_to='paymentScreenshorts/', null=True)
    deposit_type = models.CharField(max_length=1, choices=DEPOSIT_TYPE_CHOICES)
    utr_id = models.CharField(max_length=100)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    confirm_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True)
    infoNote = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Deposit Request"
        verbose_name_plural = "3. Deposit Requests"
        indexes = [
            models.Index(fields=['utr_id']),
            models.Index(fields=['status', '-created_at']),
        ]

    def delete(self, *args, **kwargs):
        if self.screenShort:
            try:
                self.screenShort.storage.delete(self.screenShort.name)
            except Exception as e:
                pass
        super().delete(*args, **kwargs)


class WithdrawalRequest(models.Model):
    WITHDRAWAL_TYPE_CHOICES = (
        ('U', 'UPI ID'),
        ('B', 'Bank Account'),
    )
    SPEED_TYPE_CHOICES = (
        ('N', 'Normal'),
        ('E', 'Express'),
    )
    STATUS_CHOICES = (
        ('P', 'Pending'),
        ('A', 'Accepted'),
        ('R', 'Rejected'),
    )
    EXPRESS_FEE_PERCENT = Decimal('2.5')

    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, primary_key=True)
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default='P', db_index=True)
    withdrawal_type = models.CharField(
        max_length=1, choices=WITHDRAWAL_TYPE_CHOICES)
    speed_type = models.CharField(
        max_length=1, choices=SPEED_TYPE_CHOICES, default='N',
        help_text='Normal: up to 6hrs, Express: up to 30mins (2.5% fee)')
    withdrawal_amount = models.DecimalField(max_digits=10, decimal_places=2)
    fee_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Fee deducted for Express withdrawal (2.5%)')
    payout_amount = models.DecimalField(
        max_digits=10, decimal_places=2, default=0,
        help_text='Amount user receives after fee deduction')
    upi_id = models.CharField(max_length=100, blank=True, null=True)
    account_number = models.CharField(max_length=50, blank=True, null=True)
    ifsc_code = models.CharField(max_length=20, blank=True, null=True)
    account_holder_name = models.CharField(
        max_length=100, blank=True, null=True)
    handling_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True,
                                    blank=True, on_delete=models.SET_NULL, related_name="handled_withdrawals")
    utr_id = models.CharField(max_length=100, blank=True, null=True)
    admin_screenshot = models.ImageField(
        upload_to='withdrawal_proofs/', null=True, blank=True,
        help_text='Admin uploads payment proof screenshot')
    infoNote = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def calculate_fee(self):
        if self.speed_type == 'E':
            return (self.withdrawal_amount * self.EXPRESS_FEE_PERCENT / Decimal('100')).quantize(Decimal('0.01'))
        return Decimal('0.00')

    @property
    def processing_time(self):
        return '30 minutes' if self.speed_type == 'E' else '6 hours'

    class Meta:
        verbose_name = "Withdrawal Request"
        verbose_name_plural = "4. Withdrawal Requests"
        indexes = [
            models.Index(fields=['status', '-created_at']),
        ]


class BonusRange(models.Model):
    BONUS_TYPE_CHOICES = [
        ('P', 'Percentage'),  # e.g. 10% of deposit
        ('F', 'Flat'),        # e.g. ₹100 fixed bonus
    ]

    min_deposit = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Minimum deposit to be eligible for a bonus"
    )
    bonus_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Bonus amount (either percentage or flat)"
    )
    bonus_type = models.CharField(
        max_length=1,
        choices=BONUS_TYPE_CHOICES,
        default='P'
    )
    only_first_deposit = models.BooleanField(
        default=False,
        help_text="If true, bonus only applies to first deposit"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bonus Tier"
        verbose_name_plural = "6. Bonus Tiers"
        ordering = ['min_deposit']

    def __str__(self):
        if self.bonus_type == 'P':
            return f"{self.bonus_value}% bonus for deposits >= {self.min_deposit}"
        return f"Flat {self.bonus_value} bonus for deposits >= {self.min_deposit}"
