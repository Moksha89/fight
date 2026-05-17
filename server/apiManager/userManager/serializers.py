from rest_framework import serializers
from userManager.models import User


class GetOtpSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=15)


class RegisterSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=15)
    username = serializers.CharField(max_length=50)
    password = serializers.CharField(min_length=6)
    confirmPassword = serializers.CharField(min_length=6)
    otp = serializers.CharField(max_length=6)

    def validate(self, data):
        if data['password'] != data['confirmPassword']:
            raise serializers.ValidationError({"confirmPassword": "Passwords do not match"})
        if User.objects.filter(phoneNumber=data['mobile']).exists():
            raise serializers.ValidationError({"mobile": "Mobile number already registered"})
        if User.objects.filter(username=data['username']).exists():
            raise serializers.ValidationError({"username": "Username already taken"})
        return data


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=50)  # username or mobile
    password = serializers.CharField()
    otp = serializers.CharField(max_length=6)


class ChangePasswordSerializer(serializers.Serializer):
    currentPassword = serializers.CharField()
    newPassword = serializers.CharField(min_length=6)
    confirmPassword = serializers.CharField(min_length=6)

    def validate(self, data):
        if data['newPassword'] != data['confirmPassword']:
            raise serializers.ValidationError({"confirmPassword": "Passwords do not match"})
        return data


class VerifyOtpSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)


class ForgotPasswordRequestOtpSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=15)


class ForgotPasswordVerifyOtpSerializer(serializers.Serializer):
    mobile = serializers.CharField(max_length=15)
    otp = serializers.CharField(max_length=6)


class ForgotPasswordResetSerializer(serializers.Serializer):
    reset_token = serializers.CharField()
    new_password = serializers.CharField(min_length=6)
    confirm_password = serializers.CharField(min_length=6)

    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match"})
        return data


class UserInfoSerializer(serializers.ModelSerializer):
    wallet_balance = serializers.SerializerMethodField()
    exposure = serializers.SerializerMethodField()
    available_balance = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "email", "username", "phoneNumber", "dateOfBirth", "gender", "isSubscribed", "isVerified", "wallet_balance", "exposure", "available_balance"]
        read_only_fields = ["id", "email", "isSubscribed", "isVerified"]

    def get_wallet_balance(self, obj):
        try:
            return float(obj.wallet.balance)
        except Exception:
            return 0.0

    def get_exposure(self, obj):
        try:
            return float(obj.wallet.exposure)
        except Exception:
            return 0.0

    def get_available_balance(self, obj):
        try:
            return float(obj.wallet.available_balance)
        except Exception:
            return 0.0
