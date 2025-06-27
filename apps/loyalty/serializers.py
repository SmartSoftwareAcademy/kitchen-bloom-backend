from rest_framework import serializers
from django.utils import timezone
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

from .models import LoyaltyProgram,LoyaltyTier,LoyaltyTransaction,LoyaltyReward,LoyaltyRedemption


class LoyaltyTierSerializer(serializers.ModelSerializer):
    """Serializer for LoyaltyTier model."""
    customer_count = serializers.SerializerMethodField()
    
    class Meta:
        model = LoyaltyTier
        fields = [
            'id',
            'program',
            'name',
            'minimum_points',
            'discount_percentage',
            'special_benefits',
            'customer_count'
        ]
    
    def get_customer_count(self, obj):
        return obj.get_customer_count()


class LoyaltyTransactionSerializer(serializers.ModelSerializer):
    """Serializer for LoyaltyTransaction model."""
    order_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = LoyaltyTransaction
        fields = [
            'id',
            'customer',
            'program',
            'transaction_type',
            'points',
            'reference_order',
            'notes',
            'created_at',
            'order_amount'
        ]
    
    def get_order_amount(self, obj):
        return obj.reference_order.total_amount if obj.reference_order else None


class LoyaltyRewardSerializer(serializers.ModelSerializer):
    """Serializer for LoyaltyReward model."""
    redemptions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = LoyaltyReward
        fields = [
            'id',
            'program',
            'name',
            'description',
            'points_required',
            'value',
            'stock_quantity',
            'is_active',
            'redemptions_count'
        ]
    
    def get_redemptions_count(self, obj):
        return obj.redemptions.count()


class LoyaltyRedemptionSerializer(serializers.ModelSerializer):
    """Serializer for LoyaltyRedemption model."""
    order_amount = serializers.SerializerMethodField()
    
    class Meta:
        model = LoyaltyRedemption
        fields = [
            'id',
            'customer',
            'reward',
            'transaction',
            'order',
            'notes',
            'created_at',
            'order_amount'
        ]
    
    def get_order_amount(self, obj):
        return obj.order.total_amount if obj.order else None


class LoyaltyProgramSerializer(serializers.ModelSerializer):
    """Serializer for LoyaltyProgram model."""
    total_members = serializers.SerializerMethodField()
    total_points_earned = serializers.SerializerMethodField()
    total_points_redeemed = serializers.SerializerMethodField()
    tiers = LoyaltyTierSerializer(many=True, read_only=True)
    rewards = LoyaltyRewardSerializer(many=True, read_only=True)
    
    class Meta:
        model = LoyaltyProgram
        fields = [
            'id',
            'name',
            'program_type',
            'status',
            'points_per_dollar',
            'minimum_points_for_reward',
            'points_expiry_days',
            'branch',
            'description',
            'total_members',
            'total_points_earned',
            'total_points_redeemed',
            'tiers',
            'rewards'
        ]
    
    def get_total_members(self, obj):
        return obj.members.count()
    
    def get_total_points_earned(self, obj):
        return LoyaltyTransaction.objects.filter(
            program=obj,
            transaction_type=LoyaltyTransaction.TransactionType.EARN
        ).aggregate(Sum('points'))['points__sum'] or 0
    
    def get_total_points_redeemed(self, obj):
        return LoyaltyTransaction.objects.filter(
            program=obj,
            transaction_type=LoyaltyTransaction.TransactionType.REDEEM
        ).aggregate(Sum('points'))['points__sum'] or 0
