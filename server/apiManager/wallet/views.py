from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from wallet.models import *
from base.models import *
from userManager.models import *
from django.db import transaction
from .serializers import *
from rest_framework.exceptions import ValidationError, PermissionDenied, MethodNotAllowed

from .paginations import *


class WalletViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [permission() for permission in self.permission_classes]

    def get_queryset(self):
        return Wallet.objects.filter(user=self.request.user)

    @action(detail=False, methods=["get"])
    def info(self, request):
        try:
            wallet = request.user.wallet
        except Wallet.DoesNotExist:
            return Response({"detail": "Wallet not found."}, status=status.HTTP_404_NOT_FOUND)

        wallet_data = WalletSerializer(wallet).data

        history = wallet.history.order_by('-created_at')
        paginator = WalletPagination()
        paginated_history = paginator.paginate_queryset(history, request)
        history_data = WalletHistorySerializer(
            paginated_history, many=True).data

        return paginator.get_paginated_response({
            "wallet": wallet_data,
            "history": history_data
        })

    # Disable all default actions
    def list(self, request): return Response(
        status=status.HTTP_405_METHOD_NOT_ALLOWED)
    def retrieve(self, request, pk=None): return Response(
        status=status.HTTP_405_METHOD_NOT_ALLOWED)


class DepositRequestViewSet(viewsets.ModelViewSet):
    queryset = DepositRequest.objects.all()
    serializer_class = DepositRequestSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['post', 'get', 'delete']

    def list(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "GET", detail="List endpoint is not allowed for this view.")

    def perform_create(self, serializer):
        user = self.request.user
        utr_id = self.request.data.get('utr_id')
        screenShort = self.request.FILES.get('screenShort')
        deposit_type = self.request.data.get('deposit_type')
        deposit_amount = self.request.data.get('deposit_amount')

        minDepositValue = float(Setting.objects.filter(
            action='J').first().actionValue)

        if float(deposit_amount) < minDepositValue:
            raise ValidationError(
                f"Deposit amount should be grater than {minDepositValue}.")

        if not utr_id:
            raise ValidationError("UTR ID is required.")

        if not str(utr_id).isdigit():
            raise ValidationError("UTR ID must contain only numbers.")

        if not deposit_type or not deposit_amount:
            raise ValidationError("Deposit type and amount are required.")

        if DepositRequest.objects.filter(customer=user).exists():
            raise ValidationError(
                "You already have an active deposit request.")

        if DepositRequest.objects.filter(utr_id=utr_id).exclude(customer=None).exclude(customer=user).exists():
            raise ValidationError(
                "This UTR ID is already linked to another user.")

        existing_staff_request = DepositRequest.objects.filter(
            utr_id=utr_id, customer=None).first()

        if existing_staff_request:
            amount = existing_staff_request.deposit_amount
            with transaction.atomic():
                existing_staff_request.delete()

                wallet, _ = Wallet.objects.get_or_create(user=user)
                wallet.balance = F('balance') + amount
                wallet.fundsIn = F('fundsIn') + amount
                wallet.save()

                settlementHistory = SettlementHistory.objects.filter(
                    utr_id=utr_id).first()
                if settlementHistory:
                    settlementHistory.customer = user
                    settlementHistory.save()

                WalletHistory.objects.create(
                    wallet=wallet,
                    transaction_type='D',
                    transactionId=settlementHistory.id if settlementHistory else None,
                    change=amount,
                    isSuccess=True,
                    description=f"Deposit auto-verified by UTR match ({utr_id})"
                )

            return

        serializer.save(
            customer=user,
            screenShort=screenShort,
            utr_id=utr_id,
            deposit_type=deposit_type,
            deposit_amount=deposit_amount
        )

    @action(detail=False, methods=['get'], url_path='payment-options')
    def get_payment_options(self, request):
        amount_str = request.query_params.get('amount')
        if not amount_str:
            return Response({"detail": "Missing 'amount' query parameter."}, status=status.HTTP_403_FORBIDDEN)

        try:
            amount = float(amount_str)
        except ValueError:
            return Response({"detail": "Invalid amount value."}, status=status.HTTP_400_BAD_REQUEST)

        method_type = request.query_params.get('type', 'all')  # 'qr', 'bank', or 'all'

        # Reset daily limits for expired accounts before filtering
        from decimal import Decimal
        from django.utils import timezone
        now = timezone.now()

        response_data = {}

        if method_type in ('qr', 'all'):
            # Check and reset QR limits
            for qr in PaymentQR.objects.all():
                qr.check_and_update_limit()

            qrs = PaymentQR.objects.filter(
                is_active=True, max_deposit__gte=amount, min_deposit__lte=amount
            ).order_by('rotation_priority', 'id')

            # Filter out QRs that have exceeded daily limit
            filtered_qrs = []
            for qr in qrs:
                if qr.daily_limit > 0 and qr.daily_credited >= qr.daily_limit:
                    continue
                filtered_qrs.append(qr)

            response_data['payment_qrs'] = PaymentQRSerializer(filtered_qrs, many=True).data

        if method_type in ('bank', 'all'):
            # Check and reset bank limits
            for bank in PaymentBankAccount.objects.all():
                bank.check_and_update_limit()

            banks = PaymentBankAccount.objects.filter(
                is_active=True, max_deposit__gte=amount, min_deposit__lte=amount
            ).order_by('rotation_priority', 'id')

            filtered_banks = []
            for bank in banks:
                if bank.daily_limit > 0 and bank.daily_credited >= bank.daily_limit:
                    continue
                filtered_banks.append(bank)

            response_data['payment_banks'] = PaymentBankAccountSerializer(filtered_banks, many=True).data

        return Response(response_data)

    @action(detail=False, methods=['get', 'delete'])
    def current(self, request):
        try:
            obj = DepositRequest.objects.get(customer=request.user)
            if request.method == 'DELETE':
                obj.delete()
                return Response({"detail": "Request deleted"}, status=status.HTTP_204_NO_CONTENT)
            return Response(DepositRequestSerializer(obj).data)
        except DepositRequest.DoesNotExist:
            return Response({})


class WithdrawalRequestViewSet(viewsets.ModelViewSet):
    queryset = WithdrawalRequest.objects.all()
    serializer_class = WithdrawalRequestSerializer
    permission_classes = [IsAuthenticated]

    def list(self, request, *args, **kwargs):
        raise MethodNotAllowed(
            "GET", detail="List endpoint is not allowed for this view.")

    def perform_create(self, serializer):
        user = self.request.user
        withdrawal_amount = serializer.validated_data.get('withdrawal_amount')

        if float(withdrawal_amount) <= 0:
            raise ValidationError("Withdrawal amount should be grater than 0.")

        if WithdrawalRequest.objects.filter(customer=user).exists():
            raise PermissionDenied(
                "You already have an existing withdrawal request.")

        wallet = getattr(user, 'wallet', None)
        if not wallet:
            raise PermissionDenied("Wallet does not exist.")

        available = wallet.balance - wallet.bonusDebt
        if available < withdrawal_amount:
            raise PermissionDenied(
                "Insufficient wallet balance for this withdrawal request.")

        with transaction.atomic():
            wallet.balance = F('balance') - withdrawal_amount
            wallet.save()

            serializer.save(customer=user)

    @action(detail=False, methods=['get', 'delete'])
    def current(self, request):
        try:
            obj = WithdrawalRequest.objects.get(customer=request.user)
            if request.method == 'DELETE':
                if obj.handling_by is not None:
                    if request.user != obj.handling_by and request.user == obj.customer:
                        raise PermissionDenied(
                            "You cannot delete a withdrawal request being handled by staff.")
                with transaction.atomic():
                    wallet = obj.customer.wallet
                    wallet.balance = F('balance') + obj.withdrawal_amount
                    wallet.save()

                    obj.delete()

                return Response({"detail": "Withdrawal request deleted and wallet refunded."}, status=status.HTTP_204_NO_CONTENT)
            return Response(WithdrawalRequestSerializer(obj).data)
        except WithdrawalRequest.DoesNotExist:
            return Response([], status=status.HTTP_404_NOT_FOUND)
