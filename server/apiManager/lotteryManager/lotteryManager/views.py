from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.db.models import Prefetch, Sum
from lotteryManager.models import *
from .serializers import *
from wallet.models import *
from django.utils import timezone



class GiftPoolViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = GiftPoolSerializer
    pagination_class = None
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        now = timezone.now()
        return GiftPool.objects.filter(
            closingDate__gt=now
        ).prefetch_related(
            Prefetch('giftpoolgifts_set', queryset=GiftPoolGifts.objects.order_by('rank'))
        ).all()

    def get_serializer_context(self):
        context = super().get_serializer_context()
        user = self.request.user
        wallet = None
        if user.is_authenticated:
            try:
                wallet = user.wallet
            except Wallet.DoesNotExist:
                pass
        context['wallet'] = wallet
        return context



class PricePoolRangeViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = PricePoolRangeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return PricePoolRange.objects.prefetch_related(
            Prefetch(
                'pricepool_set',
                queryset=PricePool.objects.annotate(
                    totalGiftsAmount=Sum('pricepoolgifts__amount')
                ).prefetch_related(
                    Prefetch('pricepoolgifts_set', queryset=PricePoolGifts.objects.order_by('rank'))
                )
            )
        ).order_by('price')