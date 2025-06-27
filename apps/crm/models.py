from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.utils.functional import cached_property
from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.utils.crypto import get_random_string

from apps.base.models import BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel
from apps.branches.models import Branch

# Using string reference to avoid circular import
# LoyaltyProgram is referenced as "loyalty.LoyaltyProgram" in the model field

User = get_user_model()

class CustomerTag(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """
    Tags for categorizing and filtering customers.
    Can be used for segmentation, marketing, and reporting.
    """
    COLOR_CHOICES = [
        ('#FF0000', 'Red'),
        ('#00FF00', 'Green'),
        ('#0000FF', 'Blue'),
        ('#FFFF00', 'Yellow'),
        ('#FF00FF', 'Magenta'),
        ('#00FFFF', 'Cyan'),
        ('#FFA500', 'Orange'),
        ('#800080', 'Purple'),
        ('#008000', 'Dark Green'),
        ('#000080', 'Navy'),
    ]
    
    color = models.CharField(_('color'),max_length=7,choices=COLOR_CHOICES,default='#000000',help_text=_('Tag color for visual distinction'))
    is_active = models.BooleanField(_('is active'),default=True,help_text=_('Whether this tag is active and can be used'))
    
    class Meta:
        verbose_name = _('customer tag')
        verbose_name_plural = _('customer tags')
        ordering = ['name']
        
    def __str__(self):
        return self.name
    
    @property
    def customer_count(self):
        """Return the number of customers with this tag."""
        return self.customers.count()


class Customer(TimestampedModel, SoftDeleteModel):
    """
    Extended customer profile that links to the base User model.
    Contains all customer-specific data and relationships.
    
    Key features:
    - Multi-channel communication preferences
    - Loyalty program integration
    - Gift card management
    - Segmentation and tagging
    - Campaign tracking
    - Communication logging
    """
    class CustomerType(models.TextChoices):
        INDIVIDUAL = 'individual', _('Individual')
        BUSINESS = 'business', _('Business')
        WHOLESALER = 'wholesaler', _('Wholesaler')
        RETAIL = 'retail', _('Retail Customer')
        VIP = 'vip', _('VIP Customer')
        
    class Gender(models.TextChoices):
        MALE = 'M', _('Male')
        FEMALE = 'F', _('Female')
        OTHER = 'O', _('Other')
        PREFER_NOT_TO_SAY = 'N', _('Prefer not to say')
        
    class CommunicationPreference(models.TextChoices):
        EMAIL = 'email', _('Email')
        SMS = 'sms', _('SMS')
        WHATSAPP = 'whatsapp', _('WhatsApp')
        PHONE = 'phone', _('Phone')
        NONE = 'none', _('None')
        
    class CampaignStatus(models.TextChoices):
        ACTIVE = 'active', _('Active')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
        
    class CommunicationType(models.TextChoices):
        EMAIL = 'email', _('Email')
        SMS = 'sms', _('SMS')
        WHATSAPP = 'whatsapp', _('WhatsApp')
        CALL = 'call', _('Phone Call')
        IN_APP = 'in_app', _('In-App Notification')
        SOCIAL = 'social', _('Social Media')
        OTHER = 'other', _('Other')
        
    class CampaignType(models.TextChoices):
        PROMOTION = 'promotion', _('Promotion')
        NEWSLETTER = 'newsletter', _('Newsletter')
        ANNOUNCEMENT = 'announcement', _('Announcement')
        SURVEY = 'survey', _('Survey')
        OTHER = 'other', _('Other')
    
    # Link to User model (one-to-one relationship)
    user = models.OneToOneField(User,on_delete=models.CASCADE,related_name='customer_profile',verbose_name=_('user account'),null=True,blank=True)
    tags = models.ManyToManyField(CustomerTag,related_name='customers',blank=True,verbose_name=_('tags'))
    loyalty_program = models.ForeignKey('loyalty.LoyaltyProgram', on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    active_gift_cards = models.ManyToManyField("accounting.GiftCard",related_name='active_customers',blank=True,verbose_name=_('active gift cards'))
    birthday = models.DateField(_('birthday'),null=True,blank=True,help_text=_('Customer\'s birthday for special offers'))
    # Basic Information
    customer_code = models.CharField(_('customer code'),max_length=20,unique=True,db_index=True,help_text=_('Unique identifier for the customer'))
    customer_type = models.CharField(_('customer type'),max_length=20,choices=CustomerType.choices,default=CustomerType.INDIVIDUAL)
    gender = models.CharField(_('gender'),max_length=1,choices=Gender.choices,blank=True,null=True)
    date_of_birth = models.DateField(_('date of birth'),null=True,blank=True)
    tax_id = models.CharField(_('tax ID'),max_length=50,blank=True,help_text=_('VAT/GST/TIN number'))
    alternate_phone = models.CharField(_('alternate phone'),max_length=20,blank=True)
    # Address Information
    address_line1 = models.CharField(_('address line 1'),max_length=255,blank=True)
    address_line2 = models.CharField(_('address line 2'),max_length=255,blank=True)
    city = models.CharField(_('city'),max_length=100,blank=True)
    state = models.CharField(_('state/province/region'),max_length=100,blank=True)
    postal_code = models.CharField(_('postal code'),max_length=20,blank=True)
    country = models.CharField(_('country'),max_length=100,default='Kenya')
    # Business Information (for business/wholesale customers)
    company_name = models.CharField(_('company name'),max_length=200,blank=True)
    company_registration = models.CharField(_('company registration'),max_length=100,blank=True,help_text=_('Company registration number'))
    vat_number = models.CharField(_('VAT number'),max_length=50,blank=True)
    website = models.URLField(_('website'),blank=True)
    # Preferences
    preferred_contact_method = models.CharField(_('preferred contact method'),max_length=10,choices=CommunicationPreference.choices,default=CommunicationPreference.EMAIL,blank=True)
    marketing_opt_in = models.BooleanField(_('marketing opt-in'),default=False,help_text=_('Customer has opted in to receive marketing communications'))
    # Internal Notes
    notes = models.TextField(_('internal notes'),blank=True,help_text=_('Internal notes about this customer'))
    allergens = models.ManyToManyField('inventory.Allergy', blank=True, related_name='customers')
    
    class Meta:
        verbose_name = _('customer')
        verbose_name_plural = _('customers')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['customer_code']),
            models.Index(fields=['customer_type']),
            models.Index(fields=['alternate_phone']),
            models.Index(fields=['company_name']),
            models.Index(fields=['loyalty_program']),
            models.Index(fields=['preferred_contact_method']),
            models.Index(fields=['marketing_opt_in']),
        ]
    
    def __str__(self):
        if self.user:
            return f"{self.user.get_full_name()} ({self.customer_code})"
        return f"Guest Customer {self.customer_code}"
    
    @cached_property
    def is_eligible_for_birthday_offer(self):
        """Check if customer is eligible for birthday offer."""
        if not self.birthday:
            return False
        today = timezone.now().date()
        return today.month == self.birthday.month and today.day == self.birthday.day
    
    @cached_property
    def is_eligible_for_anniversary_offer(self):
        """Check if customer is eligible for anniversary offer."""
        if not self.anniversary:
            return False
        today = timezone.now().date()
        return today.month == self.anniversary.month and today.day == self.anniversary.day
    
    def log_communication(self, message, method):
        """Log a communication with the customer."""
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
        self.communication_log += f"\n[{timestamp}] {method.upper()}: {message}"
        self.save()
    
    def add_loyalty_points(self, points):
        """Add loyalty points to customer's account."""
        self.loyalty_points += points
        self.save()
    
    def redeem_loyalty_points(self, points):
        """Redeem loyalty points from customer's account."""
        if points > self.loyalty_points:
            raise ValueError(_('Insufficient loyalty points'))
        self.loyalty_points -= points
        self.save()
    
    def get_campaign_response_rate(self):
        """Calculate campaign response rate."""
        if not hasattr(self, 'campaign_response_count') or not self.campaign_response_count:
            return 0
        if not hasattr(self, 'communication_log'):
            return 0
        total_campaigns = self.communication_log.count('CAMPAIGN:')
        return (self.campaign_response_count / total_campaigns) * 100 if total_campaigns else 0
    
    def get_segment_statistics(self):
        """Get statistics for customer's segment."""
        if not hasattr(self, 'segment') or not self.segment:
            return None
        return Customer.objects.filter(
            segment=self.segment
        ).aggregate(
            average_orders=Count('orders__id'),
            average_spend=Sum('orders__total_amount')
        )
    
    def clean(self):
        """Validate model fields."""
        if not self.user and not (self.alternate_phone):
            raise ValidationError(_('At least one phone number is required for guest customers.'))
    
    def save(self, *args, **kwargs):
        self.clean()
        if not self.customer_code:
            self.customer_code = self._generate_customer_code()
        super().save(*args, **kwargs)
    
    def _generate_customer_code(self):
        """Generate a unique customer code."""
        prefix = 'CUST' if self.customer_type == self.CustomerType.INDIVIDUAL else 'BUSI'
        return f"{prefix}{get_random_string(8, '0123456789').upper()}"

    @cached_property
    def full_name(self):
        """Return the customer's full name."""
        if self.user:
            return self.user.get_full_name()
        return self.company_name or getattr(self.user, 'get_full_name', lambda: '')() or 'Unnamed Customer'
    
    @cached_property
    def primary_contact(self):
        """Return the primary contact information."""
        if self.user and self.user.email:
            return self.user.email
        if self.email:
            return self.email
        return self.phone or self.alternate_phone or _('No contact information')
    
    @cached_property
    def full_address(self):
        """Return the full formatted address."""
        parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state,
            self.postal_code,
            self.country
        ]
        return ', '.join(filter(None, parts)) or _('No address provided')
    
    def get_orders(self, branch=None, status=None):
        """Get orders for this customer, optionally filtered by branch and status."""        
        queryset = self.orders.filter(customer=self)
        
        if branch:
            queryset = queryset.filter(branch=branch)
            
        if status:
            if isinstance(status, str):
                status = [status]
            queryset = queryset.filter(status__in=status)
            
        return queryset.order_by('-created_at')
    
    @cached_property
    def total_orders(self):
        """Return the total number of orders for this customer."""
        return self.get_orders().count()
    
    @cached_property
    def total_spent(self):
        """Return the total amount spent by this customer."""
        result = self.orders.aggregate(
            total=Sum('total_amount')
        )
        return result['total'] or 0
    
    @cached_property
    def average_order_value(self):
        """Return the average order value for this customer."""
        if self.total_orders == 0:
            return 0
        return self.total_spent / self.total_orders
    
    @cached_property
    def last_order_date(self):
        """Return the date of the last order."""
        last_order = self.get_orders().first()
        return last_order.created_at if last_order else None
    
    @cached_property
    def days_since_last_order(self):
        """Return the number of days since the last order."""
        if not self.last_order_date:
            return None
        return (timezone.now().date() - self.last_order_date.date()).days
    
    def get_preferred_branch(self):
        """Return the branch where this customer has placed the most orders."""        
        branch_data = self.get_orders().values('branch').annotate(
            order_count=Count('id')
        ).order_by('-order_count').first()
        
        if branch_data:
            return Branch.objects.get(pk=branch_data['branch'])
        return None

    @property
    def loyalty_tier(self):
        """Return the loyalty tier for this customer."""
        if not self.loyalty_program:
            return None
        return self.loyalty_program.get_tier(self)
