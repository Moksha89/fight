import logging
from decimal import Decimal
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
from kokoroko.error_handler import KokorokoError, ErrorCode, Severity, build_error_response
from kokoroko.security import get_client_ip, log_auth_event, RateLimiter

from .paginations import *

security_logger = logging.getLogger("kokoroko.security")


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
        ip = get_client_ip(self.request)
        utr_id = self.request.data.get('utr_id')
        screenShort = self.request.FILES.get('screenShort')
        deposit_type = self.request.data.get('deposit_type')
        deposit_amount = self.request.data.get('deposit_amount')

        # Rate limit: max 10 deposit requests per hour per IP
        allowed, _, retry_after = RateLimiter.check(
            f"deposit:{ip}", max_attempts=10, window_seconds=3600
        )
        if not allowed:
            raise KokorokoError(
                ErrorCode.WALLET_DEPOSIT_ACTIVE,
                "Too many deposit requests. Try again later.",
                severity=Severity.MEDIUM,
            )

        minDepositValue = float(Setting.objects.filter(
            action='J').first().actionValue)

        if float(deposit_amount) < minDepositValue:
            raise KokorokoError(
                ErrorCode.WALLET_DEPOSIT_MIN_AMOUNT,
                f"Minimum deposit is ₹{int(minDepositValue)}.",
                severity=Severity.LOW,
            )

        if not utr_id:
            raise KokorokoError(
                ErrorCode.VALIDATION_REQUIRED_FIELD,
                "UTR ID is required.",
                severity=Severity.LOW,
            )

        if not str(utr_id).isdigit():
            raise KokorokoError(
                ErrorCode.WALLET_UTR_INVALID,
                severity=Severity.LOW,
            )

        if not deposit_type or not deposit_amount:
            raise ValidationError("Deposit type and amount are required.")

        if DepositRequest.objects.filter(customer=user).exists():
            raise KokorokoError(
                ErrorCode.WALLET_DEPOSIT_ACTIVE,
                "You already have an active deposit request.",
                severity=Severity.LOW,
            )

        if DepositRequest.objects.filter(utr_id=utr_id).exclude(customer=None).exclude(customer=user).exists():
            raise KokorokoError(
                ErrorCode.WALLET_UTR_DUPLICATE,
                severity=Severity.MEDIUM,
            )

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

    # Withdrawal security limits
    MIN_WITHDRAWAL = Decimal('100')
    MAX_WITHDRAWAL = Decimal('500000')
    MAX_DAILY_WITHDRAWAL_COUNT = 5

    def perform_create(self, serializer):
        user = self.request.user
        ip = get_client_ip(self.request)
        withdrawal_amount = serializer.validated_data.get('withdrawal_amount')
        speed_type = serializer.validated_data.get('speed_type', 'N')

        # Rate limit: max 5 withdrawal requests per hour per IP
        allowed, _, retry_after = RateLimiter.check(
            f"withdrawal:{ip}", max_attempts=5, window_seconds=3600
        )
        if not allowed:
            raise KokorokoError(
                ErrorCode.WALLET_WITHDRAWAL_ACTIVE,
                f"Too many withdrawal requests. Try again later.",
                severity=Severity.MEDIUM,
            )

        if withdrawal_amount <= 0:
            raise KokorokoError(
                ErrorCode.BET_INVALID_AMOUNT,
                "Withdrawal amount must be greater than ₹0.",
                severity=Severity.LOW,
            )

        if withdrawal_amount < self.MIN_WITHDRAWAL:
            raise KokorokoError(
                ErrorCode.BET_INVALID_AMOUNT,
                f"Minimum withdrawal is ₹{self.MIN_WITHDRAWAL}.",
                severity=Severity.LOW,
            )

        if withdrawal_amount > self.MAX_WITHDRAWAL:
            raise KokorokoError(
                ErrorCode.BET_INVALID_AMOUNT,
                f"Maximum withdrawal is ₹{self.MAX_WITHDRAWAL}.",
                severity=Severity.LOW,
            )

        if WithdrawalRequest.objects.filter(customer=user).exists():
            raise KokorokoError(
                ErrorCode.WALLET_WITHDRAWAL_ACTIVE,
                "You already have an active withdrawal request.",
                severity=Severity.LOW,
            )

        wallet = getattr(user, 'wallet', None)
        if not wallet:
            raise KokorokoError(
                ErrorCode.WALLET_NOT_FOUND,
                http_status=status.HTTP_404_NOT_FOUND,
                severity=Severity.HIGH,
            )

        available = wallet.balance - wallet.bonusDebt
        if available < withdrawal_amount:
            raise KokorokoError(
                ErrorCode.WALLET_INSUFFICIENT_BALANCE,
                severity=Severity.MEDIUM,
            )

        # Calculate fee for Express withdrawals
        fee_amount = Decimal('0.00')
        if speed_type == 'E':
            fee_amount = (withdrawal_amount * Decimal('2.5') / Decimal('100')).quantize(Decimal('0.01'))
        payout_amount = withdrawal_amount - fee_amount

        # Log withdrawal attempt
        security_logger.info(
            "Withdrawal request: user=%s amount=%s speed=%s ip=%s",
            user.id, withdrawal_amount, speed_type, ip,
        )

        with transaction.atomic():
            wallet.balance = F('balance') - withdrawal_amount
            wallet.save()

            serializer.save(
                customer=user,
                fee_amount=fee_amount,
                payout_amount=payout_amount,
            )

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
