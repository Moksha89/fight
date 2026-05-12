from rest_framework import serializers
from base.models import *


class SettingSerializer(serializers.ModelSerializer):
    action_display = serializers.CharField(
        source='get_action_display', read_only=True)

    class Meta:
        model = Setting
        fields = ['id', 'action', 'action_display',
                  'actionValue']


class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        fields = ['id', 'category', 'status', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class ProductSerializer(serializers.ModelSerializer):
    isEligible = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            'id', 'title', 'image', 'price', 'strikePrice', 'minWalletBalance', 'isEligible'
        ]

    def get_isEligible(self, obj: Product):
        wallet = self.context.get('wallet')
        if not wallet:
            return False
        mainBalance = wallet.balance - wallet.bonusDebt
        return (mainBalance >= obj.minWalletBalance) and (mainBalance >= obj.price)


class ProductOrderSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(
        source='product.title', read_only=True)
    product_image = serializers.ImageField(
        source='product.image', read_only=True)
    status_display = serializers.CharField(
        source='get_status_display', read_only=True)

    class Meta:
        model = ProductOrder
        fields = ['id', 'product', 'product_title', 'product_image', 'status', 'status_display',
                  'deliveryTo', 'deliveryPhoneNumber', 'deliveryAddress', 'created_at']
        read_only_fields = ['status', 'created_at']


class BannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banner
        fields = ['id', 'placement', 'category', 'banner', 'uploaded_at']
        read_only_fields = ['uploaded_at']


class HighlightSerializer(serializers.ModelSerializer):
    class Meta:
        model = Highlight
        fields = ['id', 'title', 'category',
                  'updated_at', 'thumbnail', 'video']
        read_only_fields = ['updated_at']


class LearningVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = LearningVideo
        fields = ['id', 'title', 'language', 'video', 'thumbnail']

    def to_representation(self, learningVideo):
        representation = super().to_representation(learningVideo)
        representation['language'] = learningVideo.get_language_display()
        return representation
