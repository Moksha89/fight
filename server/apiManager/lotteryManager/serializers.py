from rest_framework import serializers
from lotteryManager.models import *
from django.utils import timezone


class GiftPoolGiftsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GiftPoolGifts
        fields = ['rank', 'title', 'lastUpdated']



class GiftPoolSerializer(serializers.ModelSerializer):
    gifts = GiftPoolGiftsSerializer(source='giftpoolgifts_set', many=True, read_only=True)
    isEligible = serializers.SerializerMethodField()
    isLive = serializers.SerializerMethodField()

    class Meta:
        model = GiftPool
        fields = ['id', 'name', 'image', 'amount', 'minWalletBalance',
                  'liveDate', 'isEligible', 'closingDate', 'isLocked', 'isLive', 'lastUpdated', 'gifts']

    def get_isEligible(self, obj: GiftPool):
        wallet = self.context.get('wallet')
        if not wallet:
            return False
        balance = wallet.balance
        return (balance >= obj.minWalletBalance) and (balance >= obj.amount)


    def get_isLive(self, obj: GiftPool):
        now = timezone.now()
        if obj.liveDate > now:
            return False
        return True
    


class PricePoolGiftsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PricePoolGifts
        fields = ['rank', 'amount', 'lastUpdated']



class PricePoolSerializer(serializers.ModelSerializer):
    gifts = PricePoolGiftsSerializer(source='pricepoolgifts_set', many=True, read_only=True)
    totalGiftsAmount = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )

    class Meta:
        model = PricePool
        fields = ['id', 'ticketCount', 'timeIntervalMin',
                  'isLocked', 'isClosed', 'lastUpdated', 'totalGiftsAmount', 'gifts']
        


class PricePoolRangeSerializer(serializers.ModelSerializer):
    pools = PricePoolSerializer(source='pricepool_set', many=True, read_only=True)

    class Meta:
        model = PricePoolRange
        fields = ['id', 'price', 'lastUpdated', 'pools']
