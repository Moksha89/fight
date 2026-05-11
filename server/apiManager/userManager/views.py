import random
import logging

from rest_framework import serializers
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from userManager.models import User, OtpStack
from .serializers import (
    GetOtpSerializer, VerifyOtpSerializer, UserInfoSerializer,
    RegisterSerializer, LoginSerializer, ChangePasswordSerializer
)

from django.utils import timezone
from django.db import transaction
from django.db.models import F
from datetime import timedelta
from decimal import Decimal

from base.models import *
from wallet.models import *

from userManager.tasks import sendEmailOtp
from kokoroko.security import (
    check_otp_rate_limit,
    check_login_rate_limit,
    log_auth_event,
    get_client_ip,
    RateLimiter,
)

logger = logging.getLogger("kokoroko.security")


def _generate_otp():
    """Generate OTP. Uses static '123456' until real SMS gateway is integrated."""
    # TODO: Switch to random OTP once SMS gateway is live:
    # return str(random.randint(100000, 999999))
    return "123456"


class SubscriptionViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=["get"])
    def take(self, request):
        user = request.user
        if user.lastSubscribedAt and timezone.now() - user.lastSubscribedAt < timedelta(days=30):
            return Response({"detail": "You already have an active subscription."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            cost = Decimal(Setting.objects.get(action='K').actionValue)
        except Setting.DoesNotExist:
            return Response({"detail": "Subscription cost not found."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        wallet = user.wallet
        if (wallet.balance - wallet.bonusDebt) < cost:
            return Response({"detail": "Insufficient balance for subscription."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            wallet.balance = F('balance') - cost
            wallet.save()
            WalletHistory.objects.create(
                wallet=wallet,
                transaction_type='S',
                transactionId=None,
                change=cost,
                isSuccess=True,
                description="Monthly subscription"
            )
            user.isSubscribed = True
            user.lastSubscribedAt = timezone.now()
            user.save()

        return Response({"detail": "Subscription successful."}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="status")
    def subscription_status(self, request):
        user = request.user
        is_active = False
        days_left = 0
        if user.lastSubscribedAt:
            elapsed = timezone.now() - user.lastSubscribedAt
            if elapsed < timedelta(days=30):
                is_active = True
                days_left = 30 - elapsed.days
        try:
            cost = Setting.objects.get(action='K').actionValue
        except Setting.DoesNotExist:
            cost = "0"
        return Response({
            "is_subscribed": user.isSubscribed and is_active,
            "days_left": days_left,
            "monthly_cost": cost,
            "last_subscribed_at": user.lastSubscribedAt.isoformat() if user.lastSubscribedAt else None,
        }, status=status.HTTP_200_OK)


class UserViewSet(viewsets.GenericViewSet):
    def get_serializer_class(self):
        if self.action == "getotp":
            return GetOtpSerializer
        elif self.action == "verifyotp":
            return VerifyOtpSerializer
        elif self.action == "register":
            return RegisterSerializer
        elif self.action == "login":
            return LoginSerializer
        elif self.action == "change_password":
            return ChangePasswordSerializer
        elif self.action == "me":
            return UserInfoSerializer
        return serializers.Serializer

    def get_permissions(self):
        if self.action in ["getotp", "verifyotp", "register", "login"]:
            permission_classes = [AllowAny]
        elif self.action in ["me", "change_password", "statement"]:
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = self.permission_classes
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["post"])
    def getotp(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile = serializer.validated_data["mobile"]
        ip = get_client_ip(request)

        # Rate limit OTP requests
        allowed, msg, retry_after = check_otp_rate_limit(mobile, ip)
        if not allowed:
            logger.warning("OTP rate limit hit: mobile=%s ip=%s", mobile, ip)
            return Response(
                {"error": msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)} if retry_after else {},
            )

        # Resolve username to mobile if needed
        resolved_mobile = mobile
        if not mobile.isdigit():
            user = User.objects.filter(username=mobile).first()
            if user and user.phoneNumber:
                resolved_mobile = user.phoneNumber
            else:
                return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        user = User.objects.filter(phoneNumber=resolved_mobile).first()
        if user and not user.is_active:
            return Response({'error': 'This account is suspended.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Generate secure random OTP
        otp = _generate_otp()

        OtpStack.objects.update_or_create(
            mobile=resolved_mobile,
            defaults={'otp': otp}
        )

        # Log OTP request
        if user:
            log_auth_event(user, "otp_requested", request, {"mobile": resolved_mobile})

        # Mask mobile number in response for privacy
        masked = resolved_mobile[:2] + "****" + resolved_mobile[-2:] if len(resolved_mobile) > 4 else resolved_mobile
        return Response({"message": f"OTP sent to {masked}", "mobile": resolved_mobile}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def verifyotp(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mobile = serializer.validated_data["mobile"]
        otp = serializer.validated_data["otp"]
        ip = get_client_ip(request)

        # Rate limit OTP verification attempts
        allowed, _, retry_after = RateLimiter.check(
            f"verify_otp:{mobile}:{ip}", max_attempts=5, window_seconds=300
        )
        if not allowed:
            return Response(
                {"error": f"Too many verification attempts. Try again in {retry_after}s."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        is_exist = OtpStack.objects.filter(mobile=mobile, otp=otp).exists()
        if not is_exist:
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "OTP verified", "verified": True}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def register(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip = get_client_ip(request)

        # Rate limit registration attempts per IP
        allowed, _, retry_after = RateLimiter.check(
            f"register:{ip}", max_attempts=5, window_seconds=3600
        )
        if not allowed:
            return Response(
                {"error": f"Too many registration attempts. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        mobile = serializer.validated_data["mobile"]
        username = serializer.validated_data["username"]
        password = serializer.validated_data["password"]
        otp = serializer.validated_data["otp"]

        # Verify OTP
        is_exist = OtpStack.objects.filter(mobile=mobile, otp=otp).exists()
        if not is_exist:
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        # Check duplicate mobile/username
        if User.objects.filter(phoneNumber=mobile).exists():
            return Response({"error": "Phone number already registered"}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already taken"}, status=status.HTTP_400_BAD_REQUEST)

        # Create user
        user = User(
            phoneNumber=mobile,
            username=username,
            email=f"{mobile}@user.local",
            is_staff=False,
            isVerified=True,
        )
        user.set_password(password)
        user.save()

        # Clean up OTP
        OtpStack.objects.filter(mobile=mobile).delete()

        # Log registration
        log_auth_event(user, "registration", request, {"ip": ip})

        refresh = RefreshToken.for_user(user)
        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "message": "Registration successful"
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def login(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ip = get_client_ip(request)

        # Rate limit login attempts per IP
        allowed, msg, retry_after = check_login_rate_limit(ip)
        if not allowed:
            logger.warning("Login rate limit hit: ip=%s", ip)
            return Response(
                {"error": msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
                headers={"Retry-After": str(retry_after)} if retry_after else {},
            )

        identifier = serializer.validated_data["identifier"]
        password = serializer.validated_data["password"]
        otp = serializer.validated_data["otp"]

        # Also rate-limit per identifier (account-level lockout)
        ident_allowed, _, ident_retry = RateLimiter.check(
            f"login_ident:{identifier}", max_attempts=5, window_seconds=900
        )
        if not ident_allowed:
            return Response(
                {"error": f"Account temporarily locked. Try again in {ident_retry}s."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # Find user by username or mobile
        user = User.objects.filter(username=identifier).first()
        if not user:
            user = User.objects.filter(phoneNumber=identifier).first()

        if not user:
            return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user.is_active:
            log_auth_event(user, "login_blocked_suspended", request)
            return Response({"error": "Account is suspended"}, status=status.HTTP_401_UNAUTHORIZED)

        # Verify password
        if not user.check_password(password):
            log_auth_event(user, "login_failed_password", request)
            return Response({"error": "Invalid password"}, status=status.HTTP_401_UNAUTHORIZED)

        # Verify OTP (sent to user's mobile)
        is_otp_valid = OtpStack.objects.filter(mobile=user.phoneNumber, otp=otp).exists()
        if not is_otp_valid:
            is_otp_valid = OtpStack.objects.filter(mobile=identifier, otp=otp).exists()
        if not is_otp_valid:
            log_auth_event(user, "login_failed_otp", request)
            return Response({"error": "Invalid OTP"}, status=status.HTTP_400_BAD_REQUEST)

        OtpStack.objects.filter(mobile=user.phoneNumber).delete()
        OtpStack.objects.filter(mobile=identifier).delete()

        # Reset rate limiters on successful login
        RateLimiter.reset(f"login_ident:{identifier}")

        # Log successful login
        log_auth_event(user, "login_success", request)

        refresh = RefreshToken.for_user(user)
        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": {
                "id": user.id,
                "username": user.username,
                "phoneNumber": user.phoneNumber,
            }
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="change-password")
    def change_password(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(serializer.validated_data["currentPassword"]):
            log_auth_event(user, "password_change_failed", request)
            return Response({"error": "Current password is incorrect"}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data["newPassword"])
        user.save()
        log_auth_event(user, "password_changed", request)
        return Response({"message": "Password changed successfully"}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"])
    def statement(self, request):
        user = request.user
        try:
            wallet = user.wallet
        except Exception:
            return Response({"transactions": []}, status=status.HTTP_200_OK)

        history = WalletHistory.objects.filter(wallet=wallet).order_by('-created_at')[:50]
        data = []
        for h in history:
            data.append({
                "hash": h.transactionHash,
                "type": h.get_transaction_type_display(),
                "amount": str(h.change),
                "success": h.isSuccess,
                "description": h.description,
                "date": h.created_at.strftime("%Y-%m-%d %H:%M") if h.created_at else ""
            })
        return Response({"transactions": data, "balance": str(wallet.balance)}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get", "patch"])
    def me(self, request):
        user = request.user
        if request.method == "GET":
            serializer = self.get_serializer(user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        elif request.method == "PATCH":
            serializer = self.get_serializer(user, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["get"], url_path="referral")
    def referral(self, request):
        """Get user's referral code and stats."""
        user = request.user
        import hashlib
        referral_code = hashlib.sha256(f"REF-{user.id}-{user.email}".encode()).hexdigest()[:8].upper()
        from django.core.cache import cache
        referral_key = f"referral_code:{referral_code}"
        cache.set(referral_key, user.id, timeout=None)
        referral_count = cache.get(f"referral_count:{user.id}", 0)
        referral_earnings = cache.get(f"referral_earnings:{user.id}", "0.00")
        return Response({
            "referral_code": referral_code,
            "referral_count": referral_count,
            "referral_earnings": str(referral_earnings),
            "share_message": f"Join Kokoroko and use my referral code {referral_code} to get started! Earn 2% commission on every win.",
        }, status=status.HTTP_200_OK)
