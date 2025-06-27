from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db.models import Sum
from django.utils import timezone
from django.db.models import Count
from .models import (
    ExpenseCategory, Expense,
    GiftCard, GiftCardRedemption,
    RevenueCategory, RevenueAccount,
    Revenue
)


class ExpenseInline(admin.TabularInline):
    """Inline for expenses in ExpenseCategory admin."""
    model = Expense
    fields = ['expense_number', 'amount', 'currency', 'expense_date', 'status', 'category']
    readonly_fields = ['expense_number', 'amount', 'currency', 'expense_date', 'status', 'category']
    extra = 0
    can_delete = False
    show_change_link = True
    verbose_name = _('expense')
    verbose_name_plural = _('expenses')

@admin.register(ExpenseCategory)
class ExpenseCategoryAdmin(admin.ModelAdmin):
    """Admin configuration for ExpenseCategory."""
    list_display = ['name', 'parent', 'is_active', 'expense_count', 'total_amount']
    list_filter = ('is_active',)
    search_fields = ('name', 'description')
    readonly_fields = ('expense_count', 'total_amount')
    fieldsets = (
        (_('Basic Information'), {'fields': ('name', 'parent', 'is_active', 'description')}),
        (_('Financial Metrics'), {'fields': ('expense_count', 'total_amount')})
    )    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.annotate(
            expense_count=Count('expenses'),
            total_amount=Sum('expenses__amount')
        )

    def expense_count(self, obj):
        return obj.expense_count
    expense_count.short_description = _('Number of Expenses')
    expense_count.admin_order_field = 'expense_count'

    def total_amount(self, obj):
        return obj.total_amount
    total_amount.short_description = _('Total Amount')
    total_amount.admin_order_field = 'total_amount'

@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ('expense_date','category','amount','currency','expense_type','status','created_by')
    list_filter = ('status','expense_type','category','branch','expense_date')
    search_fields = ('expense_number','description','created_by__email','approved_by__email')
    readonly_fields=('expense_number','created_at','updated_at')
    fieldsets = (
        (_('Basic Information'), {'fields': ('expense_date','category','amount','currency','expense_type','description')}),
        (_('Payment Information'), {'fields': ('payment_method','payment_reference','payment_date')}),
        (_('Status and Approval'), {'fields': ('status','approved_by','approved_at')}),
        (_('Audit Information'), {'fields': ('created_by',)})
    )

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = list(self.readonly_fields)
        if obj and obj.status != 'draft':
            readonly_fields.extend(['expense_date','category','amount','currency','expense_type','description','payment_method','payment_reference','payment_date'])
        return readonly_fields

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    actions = ['submit_for_approval', 'approve_selected', 'reject_selected']

    def submit_for_approval(self, request, queryset):
        updated = queryset.filter(status='draft').update(status='submitted',created_by=request.user)
        self.message_user(request, f'Successfully submitted {updated} expenses for approval.')
    submit_for_approval.short_description = _('Submit selected expenses for approval')

    def approve_selected(self, request, queryset):
        updated = queryset.filter(status='submitted').update(status='approved',approved_by=request.user,approved_at=timezone.now())
        self.message_user(request, f'Successfully approved {updated} expenses.')
    approve_selected.short_description = _('Approve selected expenses')

    def reject_selected(self, request, queryset):
        updated = queryset.filter(status='submitted').update(status='rejected',approved_by=request.user,approved_at=timezone.now())
        self.message_user(request, f'Successfully rejected {updated} expenses.')
    reject_selected.short_description = _('Reject selected expenses')

class GiftCardRedemptionInline(admin.TabularInline):
    """Inline admin for GiftCardRedemption."""
    model = GiftCardRedemption
    extra = 0
    fields = (
        'amount', 'redemption_type', 'order', 'notes', 'redeemed_by', 'created_at'
    )
    readonly_fields = ('created_at',)

@admin.register(GiftCard)
class GiftCardAdmin(admin.ModelAdmin):
    """Admin configuration for GiftCard."""
    list_display = (
        'code', 'initial_value', 'current_balance', 'currency',
        'status', 'issue_date', 'expiry_date', 'issued_by'
    )
    list_filter = (
        'status', 'currency', 'issue_date', 'expiry_date',
        'issued_by'
    )
    search_fields = (
        'code', 'notes', 'issued_to__name', 'issued_by__email'
    )
    ordering = ('-issue_date',)
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'code', 'initial_value', 'currency', 'status',
                'issue_date', 'expiry_date', 'issued_to', 'issued_by',
                'notes'
            )
        }),
        (_('Current Status'), {
            'fields': (
                'current_balance', 'last_redeemed_at'
            )
        }),
        (_('Audit Information'), {
            'fields': (
                'created_at', 'updated_at'
            )
        })
    )
    readonly_fields = (
        'code', 'current_balance',
        'created_at', 'updated_at'
    )
    inlines = [GiftCardRedemptionInline]
    actions = ['mark_as_expired', 'mark_as_active']

    def mark_as_expired(self, request, queryset):
        """Mark selected gift cards as expired."""
        updated = queryset.update(
            status='expired',
            notes=_('Marked as expired via admin action')
        )
        self.message_user(
            request,
            f'Successfully marked {updated} gift card(s) as expired.'
        )
    mark_as_expired.short_description = _('Mark selected gift cards as expired')

    def mark_as_active(self, request, queryset):
        """Mark selected gift cards as active."""
        updated = queryset.update(
            status='active',
            notes=_('Marked as active via admin action')
        )
        self.message_user(
            request,
            f'Successfully marked {updated} gift card(s) as active.'
        )
    mark_as_active.short_description = _('Mark selected gift cards as active')

class RevenueCategoryInline(admin.TabularInline):
    """Inline admin for RevenueCategory."""
    model = RevenueCategory
    extra = 0
    fields = ('name', 'parent', 'description', 'default_account', 'is_active')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(RevenueCategory)
class RevenueCategoryAdmin(admin.ModelAdmin):
    """Admin configuration for RevenueCategory."""
    list_display = (
        'name', 'parent', 'default_account', 'is_active', 'created_at'
    )
    list_filter = (
        'is_active', 'created_at', 'default_account'
    )
    search_fields = (
        'name', 'description', 'default_account__name'
    )
    ordering = ('name',)
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'name', 'parent', 'description', 'default_account'
            )
        }),
        (_('Status'), {
            'fields': (
                'is_active',
            )
        }),
        (_('Audit Information'), {
            'fields': (
                'created_at', 'updated_at'
            )
        })
    )
    readonly_fields = ('created_at', 'updated_at')
    inlines = [RevenueCategoryInline]
    actions = ['mark_as_active', 'mark_as_inactive']

    def mark_as_active(self, request, queryset):
        """Mark selected categories as active."""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'Successfully marked {updated} category(s) as active.'
        )
    mark_as_active.short_description = _('Mark selected categories as active')

    def mark_as_inactive(self, request, queryset):
        """Mark selected categories as inactive."""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'Successfully marked {updated} category(s) as inactive.'
        )
    mark_as_inactive.short_description = _('Mark selected categories as inactive')

class RevenueAccountInline(admin.TabularInline):
    """Inline admin for RevenueAccount."""
    model = RevenueAccount
    extra = 0
    fields = (
        'code', 'name', 'account_type', 'description', 'is_active', 'parent'
    )
    readonly_fields = ('created_at', 'updated_at')

@admin.register(RevenueAccount)
class RevenueAccountAdmin(admin.ModelAdmin):
    """Admin configuration for RevenueAccount."""
    list_display = (
        'code', 'name', 'account_type', 'parent', 'is_active', 'created_at'
    )
    list_filter = (
        'is_active', 'created_at', 'account_type', 'parent'
    )
    search_fields = (
        'code', 'name', 'description', 'parent__name'
    )
    ordering = ('code',)
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'code', 'name', 'account_type', 'description', 'parent'
            )
        }),
        (_('Status'), {
            'fields': (
                'is_active',
            )
        }),
        (_('Audit Information'), {
            'fields': (
                'created_at', 'updated_at'
            )
        })
    )
    readonly_fields = ('created_at', 'updated_at')
    inlines = [RevenueAccountInline]
    actions = ['mark_as_active', 'mark_as_inactive']

    def mark_as_active(self, request, queryset):
        """Mark selected accounts as active."""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f'Successfully marked {updated} account(s) as active.'
        )
    mark_as_active.short_description = _('Mark selected accounts as active')

    def mark_as_inactive(self, request, queryset):
        """Mark selected accounts as inactive."""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f'Successfully marked {updated} account(s) as inactive.'
        )
    mark_as_inactive.short_description = _('Mark selected accounts as inactive')

@admin.register(Revenue)
class RevenueAdmin(admin.ModelAdmin):
    """Admin configuration for Revenue."""
    list_display = (
        'revenue_number', 'revenue_date', 'category','branch',
        'amount', 'currency', 'status', 'created_by', 'last_modified_by','created_at'
    )
    list_filter = (
        'status', 'revenue_type', 'category', 'branch', 'created_at'
    )
    search_fields = (
        'revenue_number', 'description', 'payment_reference',
        'created_by__email', 'customer__name', 'category__name'
    )
    ordering = ('-revenue_date',)
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'revenue_number', 'revenue_date', 'category','branch',
                'amount', 'currency', 'revenue_type', 'description'
            )
        }),
        (_('Payment Information'), {
            'fields': (
                'payment_method', 'payment_reference', 'payment_date',
                'receipt'
            )
        }),
        (_('Status'), {
            'fields': (
                'status',
            )
        }),
        (_('Audit Information'), {
            'fields': (
                'created_at', 'last_modified_by','updated_at', 'created_by'
            )
        })
    )
    readonly_fields = (
        'revenue_number', 'created_at', 'updated_at'
    )
    actions = ['mark_as_paid', 'mark_as_unpaid']

    def mark_as_paid(self, request, queryset):
        """Mark selected revenues as paid."""
        updated = queryset.update(
            status='paid',
            payment_date=timezone.now().date()
        )
        self.message_user(
            request,
            f'Successfully marked {updated} revenue(s) as paid.'
        )
    mark_as_paid.short_description = _('Mark selected revenues as paid')

    def mark_as_unpaid(self, request, queryset):
        """Mark selected revenues as unpaid."""
        updated = queryset.update(
            status='unpaid',
            payment_date=None
        )
        self.message_user(
            request,
            f'Successfully marked {updated} revenue(s) as unpaid.'
        )
    mark_as_unpaid.short_description = _('Mark selected revenues as unpaid')


