from rest_framework import serializers
from wallet.models import *


class WalletHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = WalletHistory
        fields = ['id', 'transaction_type', 'change', 'isSuccess', 'description', 'created_at']


class WalletSerializer(serializers.ModelSerializer):
    exposure = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    available_balance = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Wallet
        fields = ['balance', 'bonusDebt', 'exposure', 'available_balance', 'updated_at']


class PaymentQRSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentQR
        fields = ['id', 'upi_id', 'display_name', 'qr_image', 'min_deposit', 'max_deposit']


class PaymentBankAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentBankAccount
        fields = ['id', 'account_holder_name', 'bank_name', 'account_number', 'ifsc_code',
                  'account_type', 'min_deposit', 'max_deposit']


class DepositRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = DepositRequest
        fields = [
            'customer', 'status', 'deposit_type', 'utr_id', 'deposit_amount',
            'infoNote', 'updated_at', 'created_at', 'screenShort'
        ]
        read_only_fields = ['customer', 'status', 'updated_at', 'created_at']


class WithdrawalRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = WithdrawalRequest
        fields = [
            'customer', 'status', 'withdrawal_type', 'withdrawal_amount', 'upi_id', 'account_number',
            'ifsc_code', 'account_holder_name', 'infoNote', 'updated_at', 'created_at'
        ]
        read_only_fields = ['customer', 'status', 'updated_at', 'created_at']

    def validate(self, attrs):
        withdrawal_type = attrs.get('withdrawal_type')

        def is_blank(value):
            return value is None or str(value).strip() == ""

        if withdrawal_type == 'U':
            if is_blank(attrs.get('upi_id')):
                raise serializers.ValidationError({
                    "upi_id": "UPI ID is required when withdrawal type is UPI."
                })
        elif withdrawal_type == 'B':
            missing_fields = {}
            if is_blank(attrs.get('account_number')):
                missing_fields["account_number"] = "Account number is required when withdrawal type is Bank Account."
            if is_blank(attrs.get('ifsc_code')):
                missing_fields["ifsc_code"] = "IFSC code is required when withdrawal type is Bank Account."
            if is_blank(attrs.get('account_holder_name')):
                missing_fields["account_holder_name"] = "Account holder name is required when withdrawal type is Bank Account."
            if missing_fields:
                raise serializers.ValidationError(missing_fields)
        else:
            raise serializers.ValidationError({
                "withdrawal_type": "Invalid withdrawal type."
            })

        return attrs
