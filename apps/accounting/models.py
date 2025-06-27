import datetime
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.contrib.auth import get_user_model

from apps.base.models import TimestampedModel, SoftDeleteModel
from apps.crm.models import Customer

User = get_user_model()

class RevenueAccount(TimestampedModel, SoftDeleteModel):
    """
    Tracks different revenue accounts for accounting purposes.
    """
    ACCOUNT_TYPES = [
        ('sales', _('Sales')),
        ('service', _('Service')),
        ('interest', _('Interest Income')),
        ('other', _('Other Income')),
    ]
    
    name = models.CharField(_('account name'), max_length=100, help_text=_('Name of the revenue account'))
    code = models.CharField(_('account code'), max_length=20, unique=True, help_text=_('Unique code for the account'))
    account_type = models.CharField(_('account type'), max_length=20, choices=ACCOUNT_TYPES, default='sales', help_text=_('Type of revenue account'))
    description = models.TextField(_('description'), blank=True, help_text=_('Detailed description of the account'))
    is_active = models.BooleanField(_('is active'), default=True, help_text=_('Whether this account is active'))
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='subaccounts', verbose_name=_('parent account'), help_text=_('Parent account (for hierarchical accounts)'))
    
    class Meta:
        verbose_name = _('revenue account')
        verbose_name_plural = _('revenue accounts')
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'parent'],
                name='unique_revenue_account_name_per_parent'
            )
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    def clean(self):
        """Validate the revenue account data."""
        if self.parent and self.parent.parent:
            raise ValidationError(_('Accounts can only be two levels deep'))
    
    def save(self, *args, **kwargs):
        """Save the revenue account with validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_full_path(self):
        """Return full account path including parent accounts."""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name
    
    def get_total_revenue(self, start_date=None, end_date=None):
        """Get total revenue for this account and its subaccounts."""
        # Get all subaccount IDs including self
        account_ids = [self.id] + list(self.subaccounts.values_list('id', flat=True))
        
        # Get revenues for this account and its subaccounts
        qs = Revenue.objects.filter(account_id__in=account_ids)
        
        if start_date:
            qs = qs.filter(revenue_date__gte=start_date)
        if end_date:
            qs = qs.filter(revenue_date__lte=end_date)
            
        return qs.aggregate(total=Sum('amount'))['total'] or 0

class RevenueCategory(TimestampedModel, SoftDeleteModel):
    """
    Categories for different types of revenue.
    """
    name = models.CharField(_('name'), max_length=100, help_text=_('Name of the revenue category'))
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='subcategories', verbose_name=_('parent'), help_text=_('Parent category (if this is a subcategory)'))
    description = models.TextField(_('description'), blank=True, help_text=_('Detailed description of the category'))
    is_active = models.BooleanField(_('is active'), default=True, help_text=_('Whether this category is active'))
    default_account = models.ForeignKey(RevenueAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='default_categories', verbose_name=_('default account'), help_text=_('Default revenue account for this category'))

    class Meta:
        verbose_name = _('revenue category')
        verbose_name_plural = _('revenue categories')
        ordering = ['name']

    def __str__(self):
        """Return the category name."""
        return self.name

    def clean(self):
        """Validate the category data."""
        if self.parent and self.parent.parent:
            raise ValidationError(_('Categories can only be two levels deep'))

    def save(self, *args, **kwargs):
        """Save the category with validation."""
        self.full_clean()
        super().save(*args, **kwargs)

    def get_total_revenue(self, start_date=None, end_date=None):
        """Get total revenue for this category and its subcategories."""
        qs = self.revenues.filter(category=self)
        if start_date:
            qs = qs.filter(revenue_date__gte=start_date)
        if end_date:
            qs = qs.filter(revenue_date__lte=end_date)
        return qs.aggregate(total=Sum('amount'))['total'] or 0

class Revenue(TimestampedModel, SoftDeleteModel):
    """
    Tracks business revenues including sales, subscriptions, and other income.
    """
    REVENUE_TYPES = [
        ('sales', _('Sales')),
        ('subscriptions', _('Subscriptions')),
        ('other', _('Other')),
    ]
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('submitted', _('Submitted for Approval')),
        ('approved', _('Approved')),
        ('paid', _('Paid')),
        ('rejected', _('Rejected')),
        ('cancelled', _('Cancelled')),
    ]
    PAYMENT_METHODS = [
        ('cash', _('Cash')),
        ('cheque', _('Cheque')),
        ('bank_transfer', _('Bank Transfer')),
        ('mpesa', _('M-Pesa')),
        ('card', _('Card')),
        ('paypal', _('PayPal')),
        ('online_payment', _('Online Payment')),
        ('loyalty_points', _('Loyalty Points')),
        ('gift_card', _('Gift Card')),
        ('other', _('Other')),
    ]
    # Basic information
    revenue_number = models.CharField(_('revenue number'), max_length=20, unique=True, db_index=True, help_text=_('Auto-generated revenue number'), default=None, editable=False)
    revenue_date = models.DateField(_('revenue date'), default=timezone.now)
    amount = models.DecimalField(_('amount'), max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)], help_text=_('Total amount of the revenue'))
    currency = models.CharField(_('currency'), max_length=3, default='KES', help_text=_('Currency code (e.g., KES, USD)'))
    description = models.TextField(_('description'), help_text=_('Detailed description of the revenue'))
    # Revenue type
    revenue_type = models.CharField(_('revenue type'), max_length=20, choices=REVENUE_TYPES, default='sales', help_text=_('Type of revenue'))
    # Categorization
    category = models.ForeignKey('RevenueCategory', on_delete=models.PROTECT, related_name='revenues', verbose_name=_('category'), help_text=_('Revenue category'))
    # Relationships
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT, related_name='revenues', verbose_name=_('branch'), help_text=_('Branch where revenue was generated'))
    customer = models.ForeignKey('crm.Customer', on_delete=models.SET_NULL, null=True, blank=True, related_name='revenues', verbose_name=_('customer'), help_text=_('Customer associated with this revenue (if applicable)'))
    # Attachments
    receipt = models.FileField(_('receipt'), upload_to='revenues/receipts/%Y/%m/%d/', null=True, blank=True, help_text=_('Revenue receipt or proof of payment'))
    # Additional information
    notes = models.TextField(_('notes'), blank=True, help_text=_('Additional notes about the revenue'))
    # Audit fields
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_revenues', verbose_name=_('created by'), help_text=_('User who created this revenue'))
    last_modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='modified_revenues', verbose_name=_('last modified by'), help_text=_('User who last modified this revenue'))
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='draft', help_text=_('Status of the revenue'))
    payment_date = models.DateField(_('payment date'), null=True, blank=True, help_text=_('Date when the revenue was paid'))
    payment_method = models.CharField(_('payment method'), max_length=20, choices=PAYMENT_METHODS, default='cash', help_text=_('How was this revenue paid?'))
    payment_reference = models.CharField(_('payment reference'), max_length=100, blank=True, help_text=_('Transaction ID, check number, or other reference'))

    class Meta:
        verbose_name = _('revenue')
        verbose_name_plural = _('revenues')
        ordering = ['-revenue_date', '-created_at']
        indexes = [
            models.Index(fields=['revenue_date']),
            models.Index(fields=['category']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.revenue_number} - {self.amount} {self.currency}"

    def clean(self):
        """Validate the revenue data."""
        if self.amount <= 0:
            raise ValidationError(_('Amount must be greater than zero'))
        
        if self.revenue_date > timezone.now().date():
            raise ValidationError(_('Revenue date cannot be in the future'))

    def save(self, *args, **kwargs):
        """Save the revenue with validation and auto-generated number."""
        self.created_at=datetime.datetime.now()
        self.updated_at=datetime.datetime.now()
        if not self.revenue_number:
            self.revenue_number = self._generate_revenue_number()
        self.full_clean()
        super().save(*args, **kwargs)

    def _generate_revenue_number(self):
        """Generate a unique revenue number."""
        prefix = 'REV-'
        date_str = timezone.now().strftime('%Y%m%d')
        
        # Get the last revenue number for today
        last_rev = Revenue.objects.filter(
            revenue_number__startswith=f'{prefix}{date_str}'
        ).order_by('-revenue_number').first()
        
        if last_rev:
            try:
                # Extract the sequence number and increment
                seq = int(last_rev.revenue_number.split('-')[-1]) + 1
                return f'{prefix}{date_str}-{seq:04d}'
            except (IndexError, ValueError):
                # Fallback if there's an issue with the format
                pass
        
        # First revenue of the day
        return f'{prefix}{date_str}-0001'

    def mark_as_paid(self, payment_date=None, payment_method=None, payment_reference=None):
        """Mark the revenue as paid."""
        if self.status != 'paid':
            self.status = 'paid'
            self.payment_date = payment_date or timezone.now().date()
            if payment_method:
                self.payment_method = payment_method
            if payment_reference:
                self.payment_reference = payment_reference
            self.save(update_fields=['status', 'payment_date', 'payment_method', 'payment_reference', 'updated_at'])

    def is_paid(self):
        """Check if the revenue is marked as paid."""
        return self.status == 'paid'

class ExpenseAccount(TimestampedModel, SoftDeleteModel):
    """
    Tracks different expense accounts for accounting purposes.
    """
    ACCOUNT_TYPES=(
        ('sales', _('Sales')),
        ('operating', _('Operating Expenses')),
        ('non_operating', _('Non-Operating Expenses')),
        ('other', _('Other Expenses')),
    )
    name = models.CharField(_('account name'), max_length=100, help_text=_('Name of the expense account'))
    code = models.CharField(_('account code'), max_length=20, unique=True, help_text=_('Unique code for the account'))
    account_type = models.CharField(_('account type'), max_length=20, choices=ACCOUNT_TYPES, default='sales', help_text=_('Type of expense account'))
    description = models.TextField(_('description'), blank=True, help_text=_('Detailed description of the account'))
    is_active = models.BooleanField(_('is active'), default=True, help_text=_('Whether this account is active'))
    parent = models.ForeignKey('self', on_delete=models.PROTECT, null=True, blank=True, related_name='subaccounts', verbose_name=_('parent account'), help_text=_('Parent account (for hierarchical accounts)'))
    
    class Meta:
        verbose_name = _('expense account')
        verbose_name_plural = _('expense accounts')
        ordering = ['code']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'parent'],
                name='unique_expense_account_name_per_parent'
            )
        ]
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate the expense account data."""
        if self.parent and self.parent.parent:
            raise ValidationError(_('Accounts can only be two levels deep'))
    
    def save(self, *args, **kwargs):
        """Save the expense account with validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def get_full_path(self):
        """Return full account path including parent accounts."""
        if self.parent:
            return f"{self.parent.get_full_path()} > {self.name}"
        return self.name
    
    def get_total_expense(self, start_date=None, end_date=None):
        """Get total expense for this account and its subaccounts."""
        # Get all subaccount IDs including self
        account_ids = [self.id] + list(self.subaccounts.values_list('id', flat=True))
        
        # Get expenses for this account and its subaccounts
        qs = Expense.objects.filter(account_id__in=account_ids)
        
        if start_date:
            qs = qs.filter(expense_date__gte=start_date)
        if end_date:
            qs = qs.filter(expense_date__lte=end_date)
            
        return qs.aggregate(total=Sum('amount'))['total'] or 0

class ExpenseCategory(TimestampedModel, SoftDeleteModel):
    """
    Categories for organizing expenses (e.g., Rent, Salaries, Utilities).
    """
    name = models.CharField(_('name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subcategories', verbose_name=_('parent category'))
    is_active = models.BooleanField(_('is active'), default=True)
    default_account = models.ForeignKey(ExpenseAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='default_categories', verbose_name=_('default account'), help_text=_('Default expense account for this category'))
    
    class Meta:
        verbose_name = _('expense category')
        verbose_name_plural = _('expense categories')
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'parent'],
                name='unique_category_name_per_parent'
            )
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def full_path(self):
        """Return full category path including parent categories."""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name

class Expense(TimestampedModel, SoftDeleteModel):
    """
    Tracks business expenses including operational costs, payroll, and other expenditures.
    """
    PAYMENT_METHODS = [
        ('cash', _('Cash')),
        ('bank_transfer', _('Bank Transfer')),
        ('check', _('Check')),
        ('card', _('Card')),
        ('mpesa', _('M-Pesa')),
        ('paypal', _('PayPal')),
        ('online_payment', _('Online Payment')),
        ('loyalty_points', _('Loyalty Points')),
        ('gift_card', _('Gift Card')),
        ('mobile_money', _('Mobile Money')),
        ('other', _('Other')),
    ]
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('submitted', _('Submitted for Approval')),
        ('approved', _('Approved')),
        ('paid', _('Paid')),
        ('rejected', _('Rejected')),
        ('cancelled', _('Cancelled')),
    ]
    EXPENSE_TYPES = [
        ('operational', _('Operational')),
        ('payroll', _('Payroll')),
        ('inventory', _('Inventory')),
        ('marketing', _('Marketing')),
        ('utilities', _('Utilities')),
        ('rent', _('Rent')),
        ('maintenance', _('Maintenance')),
        ('travel', _('Travel')),
        ('other', _('Other')),
    ]
    # Basic information
    expense_number = models.CharField(_('expense number'), max_length=20, unique=True, db_index=True, help_text=_('Auto-generated expense number'), default=None, editable=False)
    expense_date = models.DateField(_('expense date'), default=timezone.now)
    amount = models.DecimalField(_('amount'), max_digits=14, decimal_places=2, validators=[MinValueValidator(0.01)], help_text=_('Total amount of the expense'))
    currency = models.CharField(_('currency'), max_length=3, default='KES', help_text=_('Currency code (e.g., KES, USD)'))
    description = models.TextField(_('description'), help_text=_('Detailed description of the expense'))
    # Payment method
    payment_method = models.CharField(_('payment method'), max_length=20, choices=PAYMENT_METHODS, default='cash', help_text=_('How was this expense paid?'))
    payment_reference = models.CharField(_('payment reference'), max_length=100, blank=True, help_text=_('Transaction ID, check number, or other reference'))
    payment_date = models.DateField(_('payment date'), null=True, blank=True, help_text=_('When the payment was made'))
    # Status and approval workflow
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='draft', help_text=_('Current status of the expense'))
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_expenses', verbose_name=_('approved by'), help_text=_('Who approved this expense'))
    approved_at = models.DateTimeField(_('approved at'), null=True, blank=True, help_text=_('When the expense was approved'))
    # Categorization
    category = models.ForeignKey(ExpenseCategory, on_delete=models.PROTECT, related_name='expenses', verbose_name=_('category'), help_text=_('Expense category'))
    # Expense type
    expense_type = models.CharField(_('expense type'), max_length=20, choices=EXPENSE_TYPES, default='operational', help_text=_('Type of expense'))
    # Relationships
    branch = models.ForeignKey('branches.Branch', on_delete=models.PROTECT, related_name='expenses', verbose_name=_('branch'), help_text=_('Branch where expense was incurred'))
    employee = models.ForeignKey('employees.Employee', on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses', verbose_name=_('employee'), help_text=_('Employee associated with this expense (if applicable)'))
    # Attachments
    receipt = models.FileField(_('receipt'), upload_to='expenses/receipts/%Y/%m/%d/', null=True, blank=True, help_text=_('Expense receipt or proof of payment'))
    # Additional information
    notes = models.TextField(_('notes'), blank=True, help_text=_('Additional notes about the expense'))
    # Audit fields
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='created_expenses', verbose_name=_('created by'), help_text=_('User who created this expense'))
    last_modified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='modified_expenses', verbose_name=_('last modified by'), help_text=_('User who last modified this expense'))

    class Meta:
        verbose_name = _('expense')
        verbose_name_plural = _('expenses')
        ordering = ['-expense_date', '-created_at']
        indexes = [
            models.Index(fields=['expense_date']),
            models.Index(fields=['category']),
            models.Index(fields=['currency']),
        ]

    def __str__(self):
        return f"{self.expense_number} - {self.amount} {self.currency} ({self.expense_date})"
    
    def clean(self):
        """Validate the expense data."""
        if self.status == 'approved' and not self.approved_by:
            raise ValidationError('Approved expenses must have an approver')
        
        if self.status == 'paid' and not self.payment_date:
            raise ValidationError('Paid expenses must have a payment date')
        
        if self.status in ['paid', 'approved'] and not self.payment_method:
            raise ValidationError('Paid or approved expenses must have a payment method')
        
        if self.status == 'rejected' and not self.notes:
            raise ValidationError('Rejected expenses must have a rejection reason')
    
    def save(self, *args, **kwargs):
        """Save the expense with validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    def submit_for_approval(self, submitted_by=None):
        """Submit the expense for approval."""
        if self.status != 'draft':
            raise ValidationError('Only draft expenses can be submitted')
            
        self.status = 'submitted'
        self.created_by = submitted_by
        self.save()
        return True
    
    def approve(self, approved_by=None):
        """Approve the expense."""
        if self.status != 'submitted':
            raise ValidationError('Only submitted expenses can be approved')
            
        self.status = 'approved'
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        self.save()
        return True
    
    def reject(self, reason, rejected_by=None):
        """Reject the expense."""
        if self.status not in ['submitted', 'draft']:
            raise ValidationError('Only submitted or draft expenses can be rejected')
            
        self.status = 'rejected'
        self.notes = reason
        self.approved_by = rejected_by
        self.approved_at = timezone.now()
        self.save()
        return True
    
    def mark_as_paid(self, payment_date=None, payment_method=None, payment_reference=None):
        """Mark the expense as paid."""
        if self.status != 'approved':
            raise ValidationError('Only approved expenses can be marked as paid')
            
        self.status = 'paid'
        self.payment_date = payment_date or timezone.now()
        self.payment_method = payment_method
        self.payment_reference = payment_reference
        self.save()
        return True
    
    def cancel(self, reason, cancelled_by=None):
        """Cancel the expense."""
        if self.status == 'paid':
            raise ValidationError('Paid expenses cannot be cancelled')
            
        self.status = 'cancelled'
        self.notes = reason
        self.approved_by = cancelled_by
        self.approved_at = timezone.now()
        self.save()
        return True
    
    @property
    def is_paid(self):
        """Check if the expense is paid."""
        return self.status == 'paid'
    
    @property
    def is_approved(self):
        """Check if the expense is approved."""
        return self.status == 'approved'
    
    @property
    def is_rejected(self):
        """Check if the expense is rejected."""
        return self.status == 'rejected'
    
    @property
    def is_cancelled(self):
        """Check if the expense is cancelled."""
        return self.status == 'cancelled'
    
    @property
    def is_draft(self):
        """Check if the expense is a draft."""
        return self.status == 'draft'
    
    @property
    def is_submitted(self):
        """Check if the expense is submitted for approval."""
        return self.status == 'submitted'
    
    @classmethod
    def get_total_expenses(cls, branch=None, category=None, start_date=None, end_date=None):
        """Calculate total expenses for a given period and filters."""
        qs = cls.objects.all()
        
        if branch:
            qs = qs.filter(branch=branch)
        if category:
            qs = qs.filter(category=category)
        if start_date:
            qs = qs.filter(expense_date__gte=start_date)
        if end_date:
            qs = qs.filter(expense_date__lte=end_date)
            
        return qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

class GiftCard(TimestampedModel, SoftDeleteModel):
    """
    Represents a gift card that can be purchased and redeemed for goods/services.
    """
    CURRENCY_CHOICES = [
        ('KES', 'Kenyan Shilling (KES)'),
        ('USD', 'US Dollar (USD)'),
    ]

    STATUS_CHOICES = [
        ('active', _('Active')),
        ('redeemed', _('Redeemed')),
        ('expired', _('Expired')),
        ('voided', _('Voided')),
    ]

    # Identification
    code = models.CharField(_('gift card code'),max_length=20,unique=True,db_index=True,help_text=_('Unique code for the gift card'))
    # Value information
    initial_value = models.DecimalField(_('initial value'),max_digits=14,decimal_places=2,validators=[MinValueValidator(0.01)],help_text=_('Original value of the gift card'))
    current_balance = models.DecimalField(_('current balance'),max_digits=14,decimal_places=2,validators=[MinValueValidator(0)],help_text=_('Current available balance'))
    currency = models.CharField(_('currency'),max_length=3,choices=CURRENCY_CHOICES,default='KES',help_text=_('Currency of the gift card value'))
    # Status and dates
    status = models.CharField(_('status'),max_length=20,choices=STATUS_CHOICES,default='active',db_index=True,help_text=_('Current status of the gift card'))
    issue_date = models.DateTimeField(_('issue date'),default=timezone.now,help_text=_('When the gift card was issued'))
    expiry_date = models.DateTimeField(_('expiry date'),null=True,blank=True,help_text=_('When the gift card expires (optional)'))
    # Relationships
    issued_to = models.ForeignKey(Customer,on_delete=models.PROTECT,related_name='gift_cards',verbose_name=_('issued to'),help_text=_('Customer who received the gift card'))
    issued_by = models.ForeignKey('accounts.User',on_delete=models.SET_NULL,null=True,blank=True,related_name='issued_gift_cards',verbose_name=_('issued by'),help_text=_('Staff member who issued the gift card'))
    # Metadata
    notes = models.TextField(_('notes'),blank=True,help_text=_('Any additional notes about this gift card'))
    
    class Meta:
        verbose_name = _('gift card')
        verbose_name_plural = _('gift cards')
        ordering = ['-issue_date', 'code']
        indexes = [
            models.Index(fields=['code'], name='giftcard_code_idx'),
            models.Index(fields=['status'], name='giftcard_status_idx'),
            models.Index(fields=['expiry_date'], name='giftcard_expiry_idx'),
        ]
    
    def __str__(self):
        return f"Gift Card {self.code} ({self.currency} {self.current_balance})"
    
    def clean(self):
        """Validate the gift card data."""
        if self.expiry_date and self.expiry_date < timezone.now():
            self.status = 'expired'
        
        if self.current_balance > self.initial_value:
            raise ValidationError({
                'current_balance': _('Current balance cannot exceed initial value')
            })
    
    def save(self, *args, **kwargs):
        """Save the gift card with validation."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_active(self):
        """Check if the gift card is active and not expired."""
        if self.status != 'active':
            return False
        if self.expiry_date and self.expiry_date < timezone.now():
            self.status = 'expired'
            self.save()
            return False
        return True
    
    def redeem(self, amount, order=None, redeemed_by=None):
        """
        Redeem an amount from the gift card.
        
        Args:
            amount: Decimal - amount to redeem
            order: Optional[Order] - related order
            redeemed_by: Optional[User] - who is redeeming the gift card
            
        Returns:
            bool: True if redemption was successful, False otherwise
        """
        if not self.is_active:
            return False
            
        amount = abs(amount)  # Ensure positive amount
        
        if amount > self.current_balance:
            return False
            
        self.current_balance -= amount
        
        # If balance reaches zero, mark as redeemed
        if self.current_balance <= 0:
            self.status = 'redeemed'
            self.current_balance = 0
        
        # Create redemption record
        GiftCardRedemption.objects.create(gift_card=self,amount=amount,order=order,redeemed_by=redeemed_by,balance_after=self.current_balance)
        
        self.save()
        return True
    
    def void(self, voided_by=None):
        """Void the gift card and make it unusable."""
        if self.status == 'active':
            self.status = 'voided'
            self.save()
            
            # Record the void action
            GiftCardRedemption.objects.create(gift_card=self,amount=self.current_balance,redemption_type='void',redeemed_by=voided_by,balance_after=0,notes='Gift card voided')
            return True
        return False

class GiftCardRedemption(TimestampedModel, SoftDeleteModel):
    """Tracks gift card redemptions and balance changes."""
    REDEMPTION_TYPES = [
        ('purchase', _('Purchase')),
        ('redemption', _('Redemption')),
        ('void', _('Void')),
        ('refund', _('Refund')),
    ]
    
    gift_card = models.ForeignKey(GiftCard,on_delete=models.CASCADE,related_name='redemptions',verbose_name=_('gift card'))
    amount = models.DecimalField(_('amount'),max_digits=12,decimal_places=2,help_text=_('Amount redeemed or refunded'))
    redemption_type = models.CharField(_('redemption type'),max_length=20,choices=REDEMPTION_TYPES,default='redemption',help_text=_('Type of redemption transaction'))
    order = models.ForeignKey('sales.Order',on_delete=models.SET_NULL,null=True,blank=True,related_name='gift_card_redemptions',verbose_name=_('order'),help_text=_('Related order (if applicable)'))
    redeemed_by = models.ForeignKey('accounts.User',on_delete=models.SET_NULL,null=True,blank=True,related_name='gift_card_redemptions',verbose_name=_('redeemed by'),help_text=_('User who processed the redemption'))
    balance_after = models.DecimalField(_('balance after'),max_digits=12,decimal_places=2,help_text=_('Gift card balance after this transaction'))
    notes = models.TextField(_('notes'),blank=True,help_text=_('Additional notes about this redemption'))
    
    class Meta:
        verbose_name = _('gift card redemption')
        verbose_name_plural = _('gift card redemptions')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_redemption_type_display()} - {self.amount} on {self.created_at}"
    
    def save(self, *args, **kwargs):
        """Ensure balance_after is set correctly."""
        if not self.balance_after and self.gift_card_id:
            # Calculate balance after this transaction
            previous_balance = self.gift_card.current_balance
            if self.redemption_type in ['purchase', 'refund']:
                self.balance_after = previous_balance + self.amount
            else:  # redemption, void
                self.balance_after = previous_balance - self.amount
        super().save(*args, **kwargs)
