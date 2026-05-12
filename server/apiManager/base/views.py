# views.py
from rest_framework import viewsets, permissions, status
from django.utils.decorators import method_decorator

from django.views.decorators.cache import cache_page
from django_ratelimit.decorators import ratelimit
from base.models import *
from wallet.models import *
from .serializers import *

from userManager.tasks import *

from rest_framework.response import Response
from django.db import transaction


# @method_decorator(ratelimit(key="ip", rate="90/h", method="GET", block=True), name="list")
class SettingViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Setting.objects.all()
    serializer_class = SettingSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs).data

        response.append({
            "id": 0,
            "action": "#",
            "action_display": "Is Manual streaming available",
            "actionValue": "Y" if settings.IS_CF_MANUAL_STREAM__ENABLE else "N"
        })

        return Response(response)


# @method_decorator(ratelimit(key="ip", rate="90/h", method="GET", block=True), name="list")
# @method_decorator(cache_page(60 * 120), name="list")
class StatusViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Status.objects.filter(isActive=True)
    serializer_class = StatusSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


@method_decorator(ratelimit(key="ip", rate="90/h", method="GET", block=True), name="list")
# @method_decorator(cache_page(60 * 120), name="list")
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Product.objects.filter(isActive=True)
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

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


class ProductOrderViewSet(viewsets.ModelViewSet):
    serializer_class = ProductOrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProductOrder.objects.filter(user=self.request.user)

    def create(self, request, *args, **kwargs):
        user = request.user
        product_id = request.data.get('product')

        try:
            product = Product.objects.get(pk=product_id, isActive=True)
        except Product.DoesNotExist:
            return Response({"error": "Invalid product."}, status=status.HTTP_400_BAD_REQUEST)

        wallet = user.wallet

        if (wallet.balance - wallet.bonusDebt) < product.minWalletBalance:
            return Response({"error": "You are not eligible to purchase the product."}, status=status.HTTP_400_BAD_REQUEST)

        if (wallet.balance - wallet.bonusDebt) < product.price:
            return Response({"error": "Insufficient wallet balance."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Deduct from wallet
            wallet.balance = F('balance') - product.price
            wallet.save()

            # Create WalletHistory
            WalletHistory.objects.create(
                wallet=wallet,
                transaction_type='P',
                change=product.price,
                isSuccess=False,
                description=f"Purchase request for {product.title}"
            )

            # Create order
            order = ProductOrder.objects.create(
                user=user,
                product=product,
                deducted_price=product.price,
                deliveryTo=request.data.get('deliveryTo'),
                deliveryPhoneNumber=request.data.get('deliveryPhoneNumber'),
                deliveryAddress=request.data.get('deliveryAddress')
            )

            serializer = self.get_serializer(order)
            return Response(serializer.data, status=status.HTTP_201_CREATED)


# @method_decorator(ratelimit(key="ip", rate="90/h", method="GET", block=True), name="list")
class BannerViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Banner.objects.all()
    serializer_class = BannerSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


# @method_decorator(ratelimit(key="ip", rate="90/h", method="GET", block=True), name="list")
class HighlightViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Highlight.objects.all()
    serializer_class = HighlightSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None


@method_decorator(ratelimit(key='ip', rate='100/h', method='GET', block=True), name='list')
@method_decorator(cache_page(60 * 120), name='list')
class LearningVideoViewSet(viewsets.ReadOnlyModelViewSet):
    pagination_class = None
    queryset = LearningVideo.objects.all()
    serializer_class = LearningVideoSerializer
