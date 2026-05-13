from django.db import models
from utility.storageClasses import AzurePublicStorage
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
import re
from django.conf import settings


class Setting(models.Model):
    CATEGORY_CHOICES = [
        ('A', 'Is App Under Maintenance?'),
        ('B', 'Is Cock-Fight Under Maintenance?'),
        ('C', 'Is Dice Play Under Maintenance?'),
        ('D', 'Is Cricket Under Maintenance?'),

        ('E', 'Whatsapp Link'),
        ('F', 'Telegram Link'),
        ('G', 'Youtube Link'),
        ('H', 'Facebook Link'),
        ('I', 'Instagram Link'),

        ('J', 'Min Deposit Value'),
        ('K', 'Monthly Subscription Cost'),
        ('L', 'Min Balance To Watch Live'),
        ('M', 'Monthly Free Withdrawal'),
        ('N', 'Additional Withdrawal Commession %'),

        ('O', 'Scrolling Promotion Text'),

        ('P', 'Dice Play Intro Video'),
        ('Q', 'Dice Play Max Bet Allowed'),

        ('R', 'China Cockfight A Upper Ratio'),
        ('S', 'China Cockfight B Upper Ratio'),
        ('T', 'China Cockfight Draw Upper Ratio'),
        ('U', 'China Cockfight A Lower Ratio'),
        ('V', 'China Cockfight B Lower Ratio'),
        ('W', 'China Cockfight Draw Lower Ratio'),
        ('X', 'Auto Match Secret Access Line Key (DON\'T TOUCH)'),
        ('Y', 'Is China Auto Match Enabled?'),
        ('Z', 'Active Theme Configuration'),
    ]

    action = models.CharField(
        max_length=1, choices=CATEGORY_CHOICES, unique=True)
    actionValue = models.CharField(max_length=1000)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["action"]
        verbose_name = "Setting"
        verbose_name_plural = "Settings"

    def __str__(self):
        return self.get_action_display()

    def clean(self):
        value = self.actionValue.strip()
        action = self.action

        # A–D: Boolean Y/N
        if action in ['A', 'B', 'C', 'D', 'Y']:
            if value.upper() not in ['Y', 'N']:
                raise ValidationError(
                    {'actionValue': "This field must be 'Y' or 'N'."})

        # E–I, P: URL
        elif action in ['E', 'F', 'G', 'H', 'I', 'P']:
            validator = URLValidator()
            try:
                validator(value)
            except:
                raise ValidationError({'actionValue': "Enter a valid URL."})

        # Q: Dice Play Max Bet Allowed (non-negative integer; 0 = no limit)
        elif action == 'Q':
            if not value.isdigit():
                raise ValidationError(
                    {'actionValue': "Enter a valid non-negative integer (0 for no limit)."})
            if int(value) < 0:
                raise ValidationError(
                    {'actionValue': "Value must be 0 or greater."})

        # J–M: Integer
        elif action in ['J', 'K', 'L', 'M']:
            if not value.isdigit():
                raise ValidationError(
                    {'actionValue': "Enter a valid integer."})

        # N: Decimal or Integer
        elif action in ['N', 'R', 'S', 'T', 'U', 'V', 'W']:
            try:
                val = float(value)
                if not (0 <= val < 100):
                    raise ValidationError(
                        {'actionValue': "Percentage must be between 0 and less than 100."})
            except ValueError:
                raise ValidationError(
                    {'actionValue': "Enter a number (integer or decimal)."})

        # O: Non-empty text
        elif action == 'O':
            if not value:
                raise ValidationError(
                    {'actionValue': "This field cannot be empty."})


class Status(models.Model):
    CATEGORY_CHOICES = [
        ('F', 'Cockfight'),
        ('D', 'Dice Play'),
        ('C', 'Cricket'),
    ]

    category = models.CharField(max_length=1, choices=CATEGORY_CHOICES)
    status = models.FileField(
        storage=AzurePublicStorage(), upload_to='status/')
    isActive = models.BooleanField(default=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValueError("Editing is not allowed.")
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Status"
        verbose_name_plural = "2. Statuses"

    def __str__(self):
        return "Status"


class Product(models.Model):
    title = models.CharField(max_length=255)
    image = models.FileField(storage=AzurePublicStorage(),
                             upload_to='promotional_products/')
    price = models.DecimalField(max_digits=10, decimal_places=2)
    strikePrice = models.DecimalField(max_digits=10, decimal_places=2)
    minWalletBalance = models.DecimalField(max_digits=10, decimal_places=2)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    isActive = models.BooleanField(default=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Product"
        verbose_name_plural = "5. Giveaway Products"

    def __str__(self):
        return self.title


class ProductOrder(models.Model):
    ORDER_STATUS_CHOICES = (
        ('P', 'Pending'),
        ('A', 'Approved'),
        ('D', 'Delivered'),
        ('R', 'Rejected'),
        ('F', 'Refunded'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_orders")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    status = models.CharField(
        max_length=1, choices=ORDER_STATUS_CHOICES, default='P')
    deliveryTo = models.CharField(max_length=50)
    deliveryPhoneNumber = models.CharField(max_length=10)
    deliveryAddress = models.CharField(max_length=800)
    deducted_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.product.title} by {self.user} ({self.get_status_display()})"

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Product Order"
        verbose_name_plural = "6. Product Orders"


class Banner(models.Model):
    PLACEMENT_CHOICES = [
        ('C', 'Common'),
        ('D', 'Dice Play'),
        ('F', 'Game Card - Cockfight'),
        ('G', 'Game Card - Dice'),
    ]

    placement = models.CharField(max_length=1, choices=PLACEMENT_CHOICES)
    CATEGORY_CHOICES = [
        ('S', 'Cockfight'),
        ('P', 'Promotion'),
        ('D', 'Dice Play'),
        ('W', 'Wallet'),
        ('V', 'Learning Videos'),
    ]

    category = models.CharField(max_length=1, choices=CATEGORY_CHOICES)
    banner = models.FileField(
        storage=AzurePublicStorage(), upload_to='banners/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        if self.category == 'P' and not self.targetProduct:
            raise ValidationError({
                'targetProduct': 'Target product is required when category is Promotion.'
            })

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old = Product.objects.get(pk=self.pk)
                if old.image and old.image != self.image:
                    if old.image.storage.exists(old.image.name):
                        old.image.storage.delete(old.image.name)
            except Product.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Banner"
        verbose_name_plural = "1. Banners"

    def __str__(self):
        return "Banner"


class Highlight(models.Model):
    CATEGORY_CHOICES = [
        ('C', 'Cockfight'),
        ('D', 'Dice Play'),
    ]

    title = models.CharField(max_length=255)
    thumbnail = models.FileField(
        storage=AzurePublicStorage(), upload_to='highlight_thumbnails/')
    video = models.FileField(storage=AzurePublicStorage(),
                             upload_to='highlight_videos/')
    category = models.CharField(max_length=1, choices=CATEGORY_CHOICES)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old = Highlight.objects.get(pk=self.pk)

                if old.thumbnail and old.thumbnail != self.thumbnail:
                    if old.thumbnail.storage.exists(old.thumbnail.name):
                        old.thumbnail.storage.delete(old.thumbnail.name)

                if old.video and old.video != self.video:
                    if old.video.storage.exists(old.video.name):
                        old.video.storage.delete(old.video.name)
            except Highlight.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Highlight"
        verbose_name_plural = "3. Highlights"

    def __str__(self):
        return self.title


class LearningVideo(models.Model):
    LANGUAGE_CHOICES = [
        ('T', 'Telugu'),
        ('H', 'Hindi'),
        ('E', 'English'),
        ('I', 'Tamil'),
        ('M', 'Malayalam'),
    ]
    language = models.CharField(max_length=1, choices=LANGUAGE_CHOICES)
    title = models.CharField(max_length=100)
    thumbnail = models.FileField(
        storage=AzurePublicStorage(), upload_to='learning_thumbnails/')
    video = models.FileField(storage=AzurePublicStorage(),
                             upload_to='learning_videos/')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        language = dict(self.LANGUAGE_CHOICES).get(self.language, '')
        return f'{self.title} - {language}'

    def save(self, *args, **kwargs):
        if self.pk:
            try:
                old = LearningVideo.objects.get(pk=self.pk)

                if old.thumbnail and old.thumbnail != self.thumbnail:
                    if old.thumbnail.storage.exists(old.thumbnail.name):
                        old.thumbnail.storage.delete(old.thumbnail.name)

                if old.video and old.video != self.video:
                    if old.video.storage.exists(old.video.name):
                        old.video.storage.delete(old.video.name)
            except LearningVideo.DoesNotExist:
                pass
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = ("Learning Video")
        verbose_name_plural = ("4. Learning Videos")
