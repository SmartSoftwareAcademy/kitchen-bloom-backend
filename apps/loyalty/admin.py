from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum, Count

from .models import (
    LoyaltyProgram,
    LoyaltyTier,
    LoyaltyTransaction,
    LoyaltyReward,
    LoyaltyRedemption
)


class LoyaltyTierInline(admin.TabularInline):
    model = LoyaltyTier
    extra = 1
    fields = (
        'name',
        'minimum_points',
        'discount_percentage',
        'special_benefits'
    )
    readonly_fields = ('get_customer_count',)

    def get_customer_count(self, obj):
        return obj.get_customer_count()
    get_customer_count.short_description = _('Customer Count')
    get_customer_count.admin_order_field = 'customer_count'


class LoyaltyProgramAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'program_type',
        'status',
        'points_per_dollar',
        'minimum_points_for_reward',
        'points_expiry_days',
        'branch'
    )
    list_filter = (
        'program_type',
        'status',
        'branch'
    )
    search_fields = (
        'name',
        'description'
    )
    inlines = [LoyaltyTierInline]
    readonly_fields = ('total_members', 'total_points_earned', 'total_points_redeemed')

    def total_members(self, obj):
        return obj.members.count()
    total_members.short_description = _('Total Members')

    def total_points_earned(self, obj):
        return LoyaltyTransaction.objects.filter(
            program=obj,
            transaction_type=LoyaltyTransaction.TransactionType.EARN
        ).aggregate(Sum('points'))['points__sum'] or 0
    total_points_earned.short_description = _('Total Points Earned')

    def total_points_redeemed(self, obj):
        return LoyaltyTransaction.objects.filter(
            program=obj,
            transaction_type=LoyaltyTransaction.TransactionType.REDEEM
        ).aggregate(Sum('points'))['points__sum'] or 0
    total_points_redeemed.short_description = _('Total Points Redeemed')


class LoyaltyRewardInline(admin.TabularInline):
    model = LoyaltyReward
    extra = 1
    fields = (
        'name',
        'points_required',
        'value',
        'stock_quantity',
        'is_active'
    )
    readonly_fields = ('get_redemptions_count',)

    def get_redemptions_count(self, obj):
        return obj.redemptions.count()
    get_redemptions_count.short_description = _('Redemptions')


class LoyaltyTierAdmin(admin.ModelAdmin):
    list_display = (
        'program',
        'name',
        'minimum_points',
        'discount_percentage',
        'get_customer_count'
    )
    list_filter = (
        'program',
        'minimum_points'
    )
    search_fields = (
        'name',
        'program__name'
    )
    readonly_fields = ('get_customer_count',)

    def get_customer_count(self, obj):
        return obj.get_customer_count()
    get_customer_count.short_description = _('Customer Count')
    get_customer_count.admin_order_field = 'customer_count'


class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'customer',
        'program',
        'transaction_type',
        'points',
        'reference_order',
        'created_at'
    )
    list_filter = (
        'transaction_type',
        'program',
        'created_at'
    )
    search_fields = (
        'customer__name',
        'program__name',
        'notes'
    )
    readonly_fields = ('get_order_amount',)

    def get_order_amount(self, obj):
        return obj.reference_order.total_amount if obj.reference_order else None
    get_order_amount.short_description = _('Order Amount')


class LoyaltyRewardAdmin(admin.ModelAdmin):
    list_display = (
        'program',
        'name',
        'points_required',
        'value',
        'stock_quantity',
        'is_active',
        'get_redemptions_count'
    )
    list_filter = (
        'program',
        'is_active'
    )
    search_fields = (
        'name',
        'program__name'
    )
    readonly_fields = ('get_redemptions_count',)

    def get_redemptions_count(self, obj):
        return obj.redemptions.count()
    get_redemptions_count.short_description = _('Redemptions')


class LoyaltyRedemptionAdmin(admin.ModelAdmin):
    list_display = (
        'customer',
        'reward',
        'transaction',
        'order',
        'created_at'
    )
    list_filter = (
        'reward',
        'created_at'
    )
    search_fields = (
        'customer__name',
        'reward__name'
    )
    readonly_fields = ('get_order_amount',)

    def get_order_amount(self, obj):
        return obj.order.total_amount if obj.order else None
    get_order_amount.short_description = _('Order Amount')


admin.site.register(LoyaltyProgram, LoyaltyProgramAdmin)
admin.site.register(LoyaltyTier, LoyaltyTierAdmin)
admin.site.register(LoyaltyTransaction, LoyaltyTransactionAdmin)
admin.site.register(LoyaltyReward, LoyaltyRewardAdmin)
admin.site.register(LoyaltyRedemption, LoyaltyRedemptionAdmin)
