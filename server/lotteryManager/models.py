from django.db import models
from django.conf import settings
from utility.storageClasses import AzurePublicStorage
from django.core.validators import FileExtensionValidator



class GiftPool(models.Model):
    name = models.CharField(max_length=100)
    image = models.FileField(storage=AzurePublicStorage(), upload_to='giftPool/')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    minWalletBalance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    liveDate = models.DateTimeField()
    closingDate = models.DateTimeField()
    isLocked = models.BooleanField(default=False)
    lastUpdated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Gift Pool"
        verbose_name_plural = "2. Gift Pools"
        ordering = ['-liveDate']


class GiftPoolGifts(models.Model):
    giftPool = models.ForeignKey(GiftPool, on_delete=models.CASCADE)
    rank = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=100)
    lastUpdated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.giftPool.name} - Rank {self.rank}: {self.title}"

    class Meta:
        verbose_name = "Gift Pool Gift"
        verbose_name_plural = "Gift Pool Gifts"
        ordering = ['rank']
        unique_together = ('giftPool', 'rank')



class GiftPoolWinner(models.Model):
    giftPool = models.ForeignKey(GiftPool, on_delete=models.CASCADE)
    rank = models.PositiveSmallIntegerField()
    email = models.EmailField()
    lastUpdated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.email} (Rank {self.rank}) - {self.giftPool.name}"

    class Meta:
        verbose_name = "Gift Pool Winner"
        verbose_name_plural = "Gift Pool Winners"
        ordering = ['rank']
        unique_together = ('giftPool', 'rank')


class PricePoolStream(models.Model):
    roomSize = models.PositiveSmallIntegerField()
    winningNumbers = models.CharField(max_length=50)
    video = models.FileField(storage=AzurePublicStorage(), upload_to='pricePoolStream/', validators=[FileExtensionValidator(allowed_extensions=['mp4'])])
    lastUpdated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Stream #{self.roomSize} - {self.winningNumbers}"

    class Meta:
        verbose_name = "Price Pool Stream"
        verbose_name_plural = "1. Lottery Streams"
        ordering = ['roomSize', 'winningNumbers']



class PricePoolRange(models.Model):
    price = models.PositiveSmallIntegerField()
    lastUpdated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.price)

    class Meta:
        verbose_name = "Price Pool Range"
        verbose_name_plural = "3. Price Pool Ranges"
        ordering = ['price']


class PricePool(models.Model):
    range = models.ForeignKey(PricePoolRange, on_delete=models.PROTECT)
    ticketCount = models.PositiveSmallIntegerField()
    timeIntervalMin = models.PositiveSmallIntegerField()
    isLocked = models.BooleanField(default=False)
    isClosed = models.BooleanField(default=False)
    lastUpdated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"PricePool {self.ticketCount} Sitting"

    class Meta:
        verbose_name = "Price Pool"
        verbose_name_plural = "4. Price Pools"



class PricePoolGifts(models.Model):
    pricePool = models.ForeignKey(PricePool, on_delete=models.CASCADE)
    rank = models.PositiveSmallIntegerField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    lastUpdated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.pricePool} - Rank {self.rank}: ₹{self.amount}"

    class Meta:
        verbose_name = "Price Pool Gift"
        verbose_name_plural = "Price Pool Gifts"
        ordering = ['rank']
        unique_together = ('pricePool', 'rank')
