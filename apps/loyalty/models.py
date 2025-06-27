from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.utils.functional import cached_property
from django.db.models import Sum

from apps.base.models import TimestampedModel, SoftDeleteModel
from apps.branches.models import Branch
from apps.crm.models import Customer
from apps.sales.models import Order


class LoyaltyProgram(TimestampedModel, SoftDeleteModel):
    """
    Represents a loyalty program that customers can be enrolled in.
    Each program has its own rules, rewards, and tiers.
    """
    class ProgramType(models.TextChoices):
        POINTS = 'points', _('Points System')
        TIERED = 'tiered', _('Tiered System')
        CASHBACK = 'cashback', _('Cashback System')
        VOUCHER = 'voucher', _('Voucher System')
        
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Active')
        INACTIVE = 'inactive', _('Inactive')
        ARCHIVED = 'archived', _('Archived')
        
    name = models.CharField(_('name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    program_type = models.CharField(_('program type'),max_length=20,choices=ProgramType.choices,default=ProgramType.POINTS)
    status = models.CharField(_('status'),max_length=20,choices=Status.choices,default=Status.ACTIVE)
    points_per_dollar = models.DecimalField(_('points per dollar'),max_digits=5,decimal_places=2,default=1.00,help_text=_('Number of loyalty points earned per dollar spent'))
    minimum_points_for_reward = models.PositiveIntegerField(_('minimum points for reward'),default=1000,help_text=_('Minimum points required to redeem rewards'))
    points_expiry_days = models.PositiveIntegerField(_('points expiry days'),default=365,help_text=_('Number of days after which points expire'))
    branch = models.ForeignKey(Branch,on_delete=models.PROTECT,related_name='loyalty_programs',verbose_name=_('branch'),null=True,blank=True)
    
    class Meta:
        verbose_name = _('loyalty program')
        verbose_name_plural = _('loyalty programs')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['status']),
            models.Index(fields=['branch']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_program_type_display()})"
    
    def calculate_points(self, amount):
        """Calculate loyalty points for a given amount."""
        return amount * self.points_per_dollar
    
    def is_points_valid(self, points):
        """Check if points are valid (not expired)."""
        valid_points = LoyaltyTransaction.objects.filter(
            customer__loyalty_program=self,
            transaction_type=LoyaltyTransaction.TransactionType.EARN,
            created_at__gte=timezone.now() - timezone.timedelta(days=self.points_expiry_days)
        ).aggregate(Sum('points'))['points__sum'] or 0
        
        redeemed_points = LoyaltyTransaction.objects.filter(
            customer__loyalty_program=self,
            transaction_type=LoyaltyTransaction.TransactionType.REDEEM
        ).aggregate(Sum('points'))['points__sum'] or 0
        
        return valid_points - redeemed_points >= points
    
    def process_order_points(self, order: Order):
        """Process loyalty points for a completed order."""
        if not self.is_active:
            return 0
            
        # Calculate points
        points = self.calculate_points(order.total_amount)
        
        # Create transaction
        transaction = LoyaltyTransaction.objects.create(customer=order.customer,program=self,transaction_type=LoyaltyTransaction.TransactionType.EARN,points=points,
            reference_order=order,
            notes=f"Points earned from order {order.order_number}"
        )
        
        # Update customer tier if needed
        self.update_customer_tier(order.customer)
        
        return points
    
    def update_customer_tier(self, customer: Customer):
        """Update customer's loyalty tier based on their points."""
        if not customer:
            return
            
        total_points = LoyaltyTransaction.objects.filter(
            customer=customer,
            program=self,
            transaction_type=LoyaltyTransaction.TransactionType.EARN
        ).aggregate(Sum('points'))['points__sum'] or 0
        
        current_tier = customer.loyalty_tier
        new_tier = None
        
        # Find the highest tier that matches the points
        for tier in self.tiers.all().order_by('-minimum_points'):
            if total_points >= tier.minimum_points:
                new_tier = tier
                break
        
        # Update tier if changed
        if new_tier and new_tier != current_tier:
            customer.loyalty_tier = new_tier
            customer.save()


class LoyaltyTier(TimestampedModel, SoftDeleteModel):
    """
    Represents a tier level within a loyalty program.
    Each tier has its own benefits and requirements.
    """
    program = models.ForeignKey(LoyaltyProgram,on_delete=models.CASCADE,related_name='tiers',verbose_name=_('loyalty program'))
    name = models.CharField(_('name'), max_length=50)
    minimum_points = models.PositiveIntegerField(_('minimum points'),default=0,help_text=_('Minimum points required to reach this tier'))
    discount_percentage = models.DecimalField(_('discount percentage'),max_digits=5,decimal_places=2,default=0,help_text=_('Discount percentage for this tier'))
    special_benefits = models.TextField(_('special benefits'),blank=True,help_text=_('Additional benefits for this tier'))
    
    class Meta:
        verbose_name = _('loyalty tier')
        verbose_name_plural = _('loyalty tiers')
        ordering = ['minimum_points']
        indexes = [
            models.Index(fields=['program']),
            models.Index(fields=['minimum_points']),
        ]
    
    def __str__(self):
        return f"{self.program.name} - {self.name}"
    
    def get_customer_count(self):
        """Get number of customers in this tier."""
        return Customer.objects.filter(loyalty_tier=self).count()


class LoyaltyTransaction(TimestampedModel, SoftDeleteModel):
    """
    Represents a loyalty transaction (earning or redeeming points).
    Each transaction is linked to a customer and a program.
    """
    class TransactionType(models.TextChoices):
        EARN = 'earn', _('Earn Points')
        REDEEM = 'redeem', _('Redeem Points')
        ADJUST = 'adjust', _('Adjust Points')
        
    customer = models.ForeignKey(Customer,on_delete=models.PROTECT,related_name='loyalty_transactions',verbose_name=_('customer'))
    program = models.ForeignKey(LoyaltyProgram,on_delete=models.PROTECT,related_name='transactions',verbose_name=_('loyalty program'))
    transaction_type = models.CharField(_('transaction type'),max_length=20,choices=TransactionType.choices,default=TransactionType.EARN)
    points = models.IntegerField(_('points'),validators=[MinValueValidator(0)],help_text=_('Number of points in this transaction'))
    reference_order = models.ForeignKey(Order,on_delete=models.SET_NULL,related_name='loyalty_transactions',verbose_name=_('reference order'),null=True,blank=True)
    notes = models.TextField(_('notes'), blank=True)
    
    class Meta:
        verbose_name = _('loyalty transaction')
        verbose_name_plural = _('loyalty transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['customer']),
            models.Index(fields=['program']),
            models.Index(fields=['transaction_type']),
        ]
    
    def __str__(self):
        return f"{self.get_transaction_type_display()} {self.points} points for {self.customer}"
    
    def save(self, *args, **kwargs):
        """Update customer's loyalty points after saving."""
        super().save(*args, **kwargs)
        self.customer.refresh_from_db()
        self.customer.save()


class LoyaltyReward(TimestampedModel, SoftDeleteModel):
    """
    Represents a reward that can be redeemed by customers.
    Each reward is linked to a loyalty program and has its own requirements.
    """
    program = models.ForeignKey(LoyaltyProgram,on_delete=models.PROTECT,related_name='rewards',verbose_name=_('loyalty program'))
    name = models.CharField(_('name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    points_required = models.PositiveIntegerField(_('points required'),help_text=_('Number of points required to redeem this reward'))
    value = models.DecimalField(_('value'),max_digits=10,decimal_places=2,help_text=_('Value of the reward in currency'))
    stock_quantity = models.PositiveIntegerField(_('stock quantity'),default=0,help_text=_('Number of this reward available'))
    is_active = models.BooleanField(_('is active'),default=True,help_text=_('Whether this reward is currently available'))
    
    class Meta:
        verbose_name = _('loyalty reward')
        verbose_name_plural = _('loyalty rewards')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['program']),
            models.Index(fields=['points_required']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.points_required} points)"
    
    def is_available(self):
        """Check if reward is available for redemption."""
        return self.is_active and self.stock_quantity > 0
    
    def redeem(self, customer: Customer, transaction: 'LoyaltyTransaction'):
        """Process reward redemption."""
        if not self.is_available():
            raise ValueError(_('This reward is not currently available'))
            
        if not self.program.is_points_valid(self.points_required):
            raise ValueError(_('Insufficient points for this reward'))
            
        # Create redemption record
        LoyaltyRedemption.objects.create(customer=customer,reward=self,transaction=transaction)
        
        # Update stock
        self.stock_quantity -= 1
        self.save()


class LoyaltyRedemption(TimestampedModel, SoftDeleteModel):
    """
    Represents a redeemed loyalty reward.
    Each redemption is linked to a customer, reward, and transaction.
    """
    customer = models.ForeignKey(Customer,on_delete=models.PROTECT,related_name='loyalty_redemptions',verbose_name=_('customer'))
    reward = models.ForeignKey(LoyaltyReward,on_delete=models.PROTECT,related_name='redemptions',verbose_name=_('reward'))
    transaction = models.ForeignKey(LoyaltyTransaction,on_delete=models.PROTECT,related_name='redemptions',verbose_name=_('transaction'))
    order = models.ForeignKey(Order,on_delete=models.PROTECT,related_name='loyalty_redemptions',verbose_name=_('order'),null=True,blank=True)
    notes = models.TextField(_('notes'), blank=True)
    
    class Meta:
        verbose_name = _('loyalty redemption')
        verbose_name_plural = _('loyalty redemptions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['customer']),
            models.Index(fields=['reward']),
            models.Index(fields=['transaction']),
        ]
    
    def __str__(self):
        return f"{self.customer} redeemed {self.reward}"
    
    def get_order_amount(self):
        """Get the order amount if this redemption was part of an order."""
        return self.order.total_amount if self.order else None
