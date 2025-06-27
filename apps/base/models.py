from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.apps import apps
from django.contrib.postgres.fields import JSONField
from apps.reporting.models import ReportType

# Don't import User model here to avoid circular imports
# Use string references or get_user_model() in methods when needed

class SoftDeleteModel(models.Model):
    """
    An abstract base class model that provides soft delete functionality.
    """
    deleted_at = models.DateTimeField(_('deleted at'), null=True, blank=True)
    deleted_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_%(class)ss', verbose_name=_('deleted by'))

    class Meta:
        abstract = True

class TimestampedModel(models.Model):
    """
    An abstract base class model that provides self-updating
    `created_at` and `updated_at` fields.
    """
    created_at = models.DateTimeField(_('created at'), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_('updated at'), auto_now=True, db_index=True)

    class Meta:
        abstract = True
        ordering = ['-created_at']
        app_label = 'base'

    def __str__(self):
        return f"{self.__class__.__name__} {self.id}"

class UserMixin(models.Model):
    """
    A mixin that adds created_by and updated_by fields to models.
    """
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='created_%(class)ss',
        verbose_name=_('created by'),
        null=True,  # Allow null for the first user
        blank=True  # Allow blank in forms
    )
    updated_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_%(class)ss',
        verbose_name=_('updated by')
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """
        Override save to set created_by and updated_by fields.
        For the first user, created_by can be None.
        """
        from django.contrib.auth import get_user_model
        
        is_first_user = not get_user_model().objects.exists()
        
        if not self.pk:  # New instance
            user = getattr(self, '_current_user', None)
            if user and not user.is_anonymous:
                self.created_by = user
            # If it's the first user and no created_by is set, allow it
            elif not is_first_user and not self.created_by_id:
                # For non-first users, created_by is required
                raise ValueError("created_by is required for non-first users")
        else:  # Updating existing instance
            user = getattr(self, '_current_user', None)
            if user and not user.is_anonymous:
                self.updated_by = user
                
        super().save(*args, **kwargs)

class StatusModel(models.Model):
    """
    An abstract base class model that provides status field.
    """
    STATUS_CHOICES = [
        ('draft', _('Draft')),
        ('active', _('Active')),
        ('inactive', _('Inactive')),
        ('archived', _('Archived')),
    ]
    
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='draft',
        db_index=True
    )

    class Meta:
        abstract = True

class NameDescriptionModel(models.Model):
    """
    An abstract base class model that provides name and description fields.
    """
    name = models.CharField(_('name'), max_length=255, db_index=True)
    description = models.TextField(_('description'), blank=True, null=True)

    class Meta:
        abstract = True
        ordering = ['name']

    def __str__(self):
        return self.name

class BaseNameDescriptionModel(TimestampedModel, NameDescriptionModel):
    """
    A base model that includes all common fields: timestamps, soft delete, name, and description.
    """
    class Meta:
        abstract = True
        ordering = ['name']
        verbose_name = _('base named model')
        verbose_name_plural = _('base named models')

#set up email config settings and use when sending mails in business logic
class EmailConfig(models.Model):
    PROVIDER_CHOICES = [
        ('smtp', 'SMTP'),
        ('sendgrid', 'SendGrid'),
    ]
    provider = models.CharField(max_length=255,default='smtp',unique=True)
    email_host = models.CharField(max_length=255)
    email_port = models.IntegerField()
    email_host_user = models.CharField(max_length=255)
    email_host_password = models.CharField(max_length=255,default='fskwauczrnscjikr')
    email_use_tls = models.BooleanField(default=True)
    email_use_ssl = models.BooleanField(default=False)
    fail_silently = models.BooleanField(default=True)
    email_from = models.CharField(max_length=255,default='codevertexitsolutions@gmail.com')
    email_from_name = models.CharField(max_length=255,default='CodeVertex')
    email_subject = models.CharField(max_length=255,default='CodeVertex')
    email_body = models.TextField(default='CodeVertex')
    
    class Meta:
        verbose_name = _('email config')
        verbose_name_plural = _('email configs')

class SMSSettings(models.Model):
    PROVIDER_CHOICES = [
        ('twilio', 'Twilio'),
        ('africastalking', 'Africa\'s Talking'),
    ]
    
    provider = models.CharField(
        max_length=20,
        choices=PROVIDER_CHOICES,
        default='twilio'
    )
    is_active = models.BooleanField(default=True)
    
    # Twilio credentials
    twilio_account_sid = models.CharField(max_length=100, blank=True,default='')
    twilio_auth_token = models.CharField(max_length=100, blank=True,default='')
    twilio_phone_number = models.CharField(max_length=20, blank=True,default='')
    
    # Africa's Talking credentials
    africastalking_username = models.CharField(max_length=100, blank=True,default='')
    africastalking_api_key = models.CharField(max_length=100, blank=True,default='')
    africastalking_sender_id = models.CharField(max_length=15, blank=True,default='')
    
    def __str__(self):
        return self.provider

    class Meta:
        verbose_name_plural = "SMS Settings"

class Address(TimestampedModel):
    """
    Global Address model that can be used by any model that needs address information.
    Uses a generic relation to link to any model.
    """
    # Address types
    HOME = 'home'
    WORK = 'work'
    BILLING = 'billing'
    SHIPPING = 'shipping'
    OTHER = 'other'
    
    ADDRESS_TYPE_CHOICES = [
        (HOME, _('Home')),
        (WORK, _('Work')),
        (BILLING, _('Billing')),
        (SHIPPING, _('Shipping')),
        (OTHER, _('Other')),
    ]
    
    # Content type fields for generic relation
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.CASCADE,
        related_name='%(app_label)s_%(class)s_addresses',
        null=True,
        blank=True
    )
    object_id = models.UUIDField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Address fields
    address_type = models.CharField(_('address type'),max_length=20,choices=ADDRESS_TYPE_CHOICES,default=HOME)
    address_line1 = models.CharField(_('address line 1'), max_length=255)
    address_line2 = models.CharField(_('address line 2'), max_length=255, blank=True, null=True)
    city = models.CharField(_('city'), max_length=100)
    state = models.CharField(_('state/province/region'), max_length=100)
    postal_code = models.CharField(_('postal code'),max_length=20,validators=[RegexValidator(regex='^[0-9a-zA-Z\-\s]*$',message=_("Enter a valid postal code (letters, numbers, spaces, and hyphens only)"),),])
    country = models.CharField(_('country'), max_length=100, default='Kenya')
    is_primary = models.BooleanField(_('is primary'), default=False)
    notes = models.TextField(_('notes'), blank=True, null=True)
    
    # Geo fields (optional, can be populated by geocoding)
    latitude = models.DecimalField(_('latitude'),max_digits=10,decimal_places=8,null=True,blank=True)
    longitude = models.DecimalField(_('longitude'),max_digits=11,decimal_places=8,null=True,blank=True)
    
    class Meta:
        verbose_name = _('address')
        verbose_name_plural = _('addresses')
        ordering = ['-is_primary', 'address_type', 'city', 'address_line1']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['is_primary']),
            models.Index(fields=['city']),
            models.Index(fields=['country']),
        ]
    
    def __str__(self):
        return f"{self.get_address_type_display()}: {self.address_line1}, {self.city}, {self.country}"
    
    def clean(self):
        """Ensure only one primary address per content type and object."""
        if self.is_primary and self.content_type and self.object_id:
            # Check if there's another primary address for this object
            existing_primary = Address.objects.filter(
                content_type=self.content_type,
                object_id=self.object_id,
                is_primary=True
            ).exclude(pk=self.pk).exists()
            
            if existing_primary:
                raise ValidationError({
                    'is_primary': _('This object already has a primary address.')
                })
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    def get_full_address(self):
        """Return the full formatted address as a string."""
        parts = [
            self.address_line1,
            self.address_line2,
            self.city,
            self.state,
            self.postal_code,
            self.country,
        ]
        return ', '.join(filter(None, parts))

# System Settings Models
class TaxSettings(TimestampedModel, UserMixin):
    """
    Tax configuration settings.
    """
    enabled = models.BooleanField(_('enabled'), default=False)
    use_for_pos = models.BooleanField(_('use for POS'), default=False)
    default_rate = models.DecimalField(_('default rate'), max_digits=5, decimal_places=2, default=0)
    tax_name = models.CharField(_('tax name'), max_length=50, default='VAT')
    tax_description = models.TextField(_('tax description'), blank=True)
    
    # Tax Calculation
    tax_inclusive = models.BooleanField(_('tax inclusive'), default=False)
    round_tax = models.BooleanField(_('round tax'), default=True)
    
    # Multiple Tax Rates
    allow_multiple_rates = models.BooleanField(_('allow multiple rates'), default=False)
    
    class Meta:
        verbose_name = _('tax settings')
        verbose_name_plural = _('tax settings')
    
    def __str__(self):
        return f"Tax Settings - {self.tax_name} ({self.default_rate}%)"
    
    @classmethod
    def get_settings(cls):
        """Get or create tax settings."""
        settings, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'enabled': False,
                'use_for_pos': False,
                'default_rate': 0,
                'tax_name': 'VAT'
            }
        )
        return settings


class POSSettings(TimestampedModel, UserMixin):
    """
    Point of Sale configuration settings.
    """
    # Customer Settings
    require_customer = models.BooleanField(_('require customer'), default=False)
    allow_anonymous_orders = models.BooleanField(_('allow anonymous orders'), default=True)
    
    # Order Settings
    allow_hold_orders = models.BooleanField(_('allow hold orders'), default=True)
    allow_discounts = models.BooleanField(_('allow discounts'), default=True)
    allow_void = models.BooleanField(_('allow void'), default=True)
    allow_refunds = models.BooleanField(_('allow refunds'), default=True)
    
    # Discount Settings
    max_discount_percent = models.DecimalField(_('max discount percent'), max_digits=5, decimal_places=2, default=20)
    require_discount_reason = models.BooleanField(_('require discount reason'), default=False)
    
    # Payment Settings
    default_payment_method = models.CharField(_('default payment method'), max_length=20, default='cash')
    allow_split_payments = models.BooleanField(_('allow split payments'), default=True)
    require_payment_confirmation = models.BooleanField(_('require payment confirmation'), default=False)
    
    # Receipt Settings
    auto_print_receipt = models.BooleanField(_('auto print receipt'), default=False)
    show_tax_breakdown = models.BooleanField(_('show tax breakdown'), default=True)
    show_qr_code = models.BooleanField(_('show QR code'), default=False)
    
    # Kitchen Display
    enable_kds = models.BooleanField(_('enable kitchen display'), default=True)
    auto_assign_orders = models.BooleanField(_('auto assign orders'), default=False)
    
    class Meta:
        verbose_name = _('POS settings')
        verbose_name_plural = _('POS settings')
    
    def __str__(self):
        return "POS Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create POS settings."""
        settings, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'allow_hold_orders': True,
                'allow_discounts': True,
                'allow_void': True,
                'max_discount_percent': 20,
                'default_payment_method': 'cash',
                'allow_split_payments': True,
                'show_tax_breakdown': True,
                'enable_kds': True
            }
        )
        return settings


class ReceiptSettings(TimestampedModel, UserMixin):
    """
    Receipt configuration settings.
    """
    header_text = models.TextField(_('header text'), blank=True)
    footer_text = models.TextField(_('footer text'), blank=True)
    show_logo = models.BooleanField(_('show logo'), default=True)
    show_tax_breakdown = models.BooleanField(_('show tax breakdown'), default=True)
    show_qr_code = models.BooleanField(_('show QR code'), default=False)
    show_barcode = models.BooleanField(_('show barcode'), default=False)
    
    # Receipt Format
    paper_width = models.IntegerField(_('paper width (mm)'), default=80)
    font_size = models.CharField(_('font size'), max_length=10, default='normal')
    alignment = models.CharField(_('alignment'), max_length=10, default='left')
    
    # Receipt Content
    show_order_number = models.BooleanField(_('show order number'), default=True)
    show_date_time = models.BooleanField(_('show date time'), default=True)
    show_cashier = models.BooleanField(_('show cashier'), default=True)
    show_customer = models.BooleanField(_('show customer'), default=True)
    show_payment_method = models.BooleanField(_('show payment method'), default=True)
    
    # Additional Information
    show_terms = models.BooleanField(_('show terms'), default=False)
    terms_text = models.TextField(_('terms text'), blank=True)
    show_return_policy = models.BooleanField(_('show return policy'), default=False)
    return_policy_text = models.TextField(_('return policy text'), blank=True)
    
    class Meta:
        verbose_name = _('receipt settings')
        verbose_name_plural = _('receipt settings')
    
    def __str__(self):
        return "Receipt Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create receipt settings."""
        settings, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'show_logo': True,
                'show_tax_breakdown': True,
                'paper_width': 80,
                'font_size': 'normal',
                'alignment': 'left',
                'show_order_number': True,
                'show_date_time': True,
                'show_cashier': True,
                'show_customer': True,
                'show_payment_method': True
            }
        )
        return settings


class NotificationSettings(TimestampedModel, UserMixin):
    """
    Notification configuration settings.
    """
    # Email Notifications
    email_notifications = models.BooleanField(_('email notifications'), default=True)
    alert_email = models.EmailField(_('alert email'), blank=True)
    
    # SMS Notifications
    sms_notifications = models.BooleanField(_('SMS notifications'), default=False)
    alert_phone = models.CharField(_('alert phone'), max_length=20, blank=True)
    
    # Push Notifications
    push_notifications = models.BooleanField(_('push notifications'), default=True)
    
    # Notification Types
    low_stock_alerts = models.BooleanField(_('low stock alerts'), default=True)
    low_stock_threshold = models.IntegerField(_('low stock threshold'), default=10)
    
    order_notifications = models.BooleanField(_('order notifications'), default=True)
    payment_notifications = models.BooleanField(_('payment notifications'), default=True)
    refund_notifications = models.BooleanField(_('refund notifications'), default=True)
    
    # System Notifications
    system_maintenance = models.BooleanField(_('system maintenance'), default=True)
    security_alerts = models.BooleanField(_('security alerts'), default=True)
    backup_notifications = models.BooleanField(_('backup notifications'), default=True)
    
    class Meta:
        verbose_name = _('notification settings')
        verbose_name_plural = _('notification settings')
    
    def __str__(self):
        return "Notification Settings"
    
    @classmethod
    def get_settings(cls):
        """Get or create notification settings."""
        settings, created = cls.objects.get_or_create(
            id=1,
            defaults={
                'email_notifications': True,
                'push_notifications': True,
                'low_stock_alerts': True,
                'low_stock_threshold': 10,
                'order_notifications': True,
                'payment_notifications': True,
                'system_maintenance': True,
                'security_alerts': True,
                'backup_notifications': True
            }
        )
        return settings


class PaymentGatewaySettings(TimestampedModel, UserMixin):
    """
    Payment gateway configuration settings.
    """
    GATEWAY_CHOICES = [
        ('mpesa', 'M-Pesa'),
        ('card', 'Card Payment'),
        ('paypal', 'PayPal'),
        ('stripe', 'Stripe'),
        ('razorpay', 'Razorpay'),
        ('flutterwave', 'Flutterwave'),
        ('paystack', 'Paystack'),
        ('square', 'Square'),
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
    ]
    
    gateway_name = models.CharField(_('gateway name'), max_length=50, choices=GATEWAY_CHOICES)
    is_active = models.BooleanField(_('is active'), default=False)
    is_default = models.BooleanField(_('is default'), default=False)
    
    # Gateway Configuration
    api_key = models.CharField(_('API key'), max_length=255, blank=True)
    secret_key = models.CharField(_('secret key'), max_length=255, blank=True)
    webhook_url = models.URLField(_('webhook URL'), blank=True)
    
    # M-Pesa Specific
    mpesa_consumer_key = models.CharField(_('M-Pesa consumer key'), max_length=255, blank=True)
    mpesa_consumer_secret = models.CharField(_('M-Pesa consumer secret'), max_length=255, blank=True)
    mpesa_passkey = models.CharField(_('M-Pesa passkey'), max_length=255, blank=True)
    mpesa_shortcode = models.CharField(_('M-Pesa shortcode'), max_length=10, blank=True)
    mpesa_environment = models.CharField(_('M-Pesa environment'), max_length=10, default='sandbox', choices=[
        ('sandbox', 'Sandbox'),
        ('live', 'Live')
    ])
    
    # Card Payment Specific
    card_processor = models.CharField(_('card processor'), max_length=50, blank=True, choices=[
        ('stripe', 'Stripe'),
        ('square', 'Square'),
        ('razorpay', 'Razorpay'),
        ('flutterwave', 'Flutterwave'),
        ('paystack', 'Paystack'),
    ])
    
    # PayPal Specific
    paypal_client_id = models.CharField(_('PayPal client ID'), max_length=255, blank=True)
    paypal_secret = models.CharField(_('PayPal secret'), max_length=255, blank=True)
    paypal_environment = models.CharField(_('PayPal environment'), max_length=10, default='sandbox', choices=[
        ('sandbox', 'Sandbox'),
        ('live', 'Live')
    ])
    
    # Stripe Specific
    stripe_publishable_key = models.CharField(_('Stripe publishable key'), max_length=255, blank=True)
    stripe_secret_key = models.CharField(_('Stripe secret key'), max_length=255, blank=True)
    stripe_webhook_secret = models.CharField(_('Stripe webhook secret'), max_length=255, blank=True)
    
    # General Settings
    transaction_fee_percent = models.DecimalField(_('transaction fee percent'), max_digits=5, decimal_places=2, default=0)
    transaction_fee_fixed = models.DecimalField(_('transaction fee fixed'), max_digits=10, decimal_places=2, default=0)
    minimum_amount = models.DecimalField(_('minimum amount'), max_digits=10, decimal_places=2, default=0)
    maximum_amount = models.DecimalField(_('maximum amount'), max_digits=10, decimal_places=2, default=1000000)
    
    # Display Settings
    display_name = models.CharField(_('display name'), max_length=100, blank=True)
    description = models.TextField(_('description'), blank=True)
    icon = models.CharField(_('icon'), max_length=50, blank=True)
    
    class Meta:
        verbose_name = _('payment gateway settings')
        verbose_name_plural = _('payment gateway settings')
        unique_together = ['gateway_name']
    
    def __str__(self):
        return f"{self.get_gateway_name_display()} - {'Active' if self.is_active else 'Inactive'}"
    
    def save(self, *args, **kwargs):
        # Ensure only one default gateway
        if self.is_default:
            PaymentGatewaySettings.objects.filter(is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active_gateways(cls):
        """Get all active payment gateways."""
        return cls.objects.filter(is_active=True).order_by('-is_default', 'gateway_name')
    
    @classmethod
    def get_default_gateway(cls):
        """Get the default payment gateway."""
        return cls.objects.filter(is_active=True, is_default=True).first()

class SystemModuleSettings(models.Model):
    """Singleton model to store which modules, models, and fields are enabled/disabled."""
    singleton_enforcer = models.BooleanField(default=True, editable=False, unique=True,null=True)
    modules_config = models.JSONField(_('modules config'), default=dict, blank=True,null=True)
    reporting_enabled_reports = models.JSONField(_('enabled reports'), default=dict, blank=True,null=True)

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    @classmethod
    def discover_structure(cls):
        """Auto-discover all apps, models, and fields, and their required/optional status."""
        structure = {}
        for app_config in apps.get_app_configs():
            if not app_config.models_module:
                continue
            app_label = app_config.label
            structure[app_label] = {"enabled": True, "models": {}}
            for model in app_config.get_models():
                model_name = model.__name__
                structure[app_label]["models"][model_name] = {"enabled": True, "fields": {}}
                for field in model._meta.get_fields():
                    # Only include regular fields (not reverse relations, etc.)
                    if not hasattr(field, 'blank') or not hasattr(field, 'null'):
                        continue
                    # Required if blank=False and null=False
                    is_required = not field.blank and not field.null
                    structure[app_label]["models"][model_name]["fields"][field.name] = {
                        "enabled": True,
                        "required": is_required
                    }
        return structure

    @classmethod
    def getDefaultModules(cls):
        """
        Return a structure with all modules, models, and fields relevant to the POS page (sales, inventory, crm, tables) fully enabled.
        This is based on the backend models and fields, with all fields enabled and required as per model definition.
        """
        # Use discover_structure to get all models/fields, then filter for relevant apps
        structure = cls.discover_structure()
        relevant_apps = ['sales', 'inventory', 'crm', 'tables','payroll','kds','employees']
        default_modules = {}
        for app in relevant_apps:
            if app in structure:
                default_modules[app] = {"enabled": True, "models": {}}
                for model, model_data in structure[app]["models"].items():
                    default_modules[app]["models"][model] = {"enabled": True, "fields": {}}
                    for field, field_data in model_data["fields"].items():
                        default_modules[app]["models"][model]["fields"][field] = {
                            "enabled": True,
                            "required": field_data["required"]
                        }
        return default_modules

    def get_full_structure(self):
        """Return the merged structure of discovered modules and current config, with required/optional info."""
        discovered = self.discover_structure()
        config = self.modules_config or {}
        # Merge config into discovered, prioritizing config for enabled/disabled
        for app, app_data in discovered.items():
            if app in config:
                app_data["enabled"] = config[app].get("enabled", True)
                for model, model_data in app_data["models"].items():
                    if model in config[app].get("models", {}):
                        model_data["enabled"] = config[app]["models"][model].get("enabled", True)
                        for field, field_data in model_data["fields"].items():
                            if field in config[app]["models"][model].get("fields", {}):
                                field_data["enabled"] = config[app]["models"][model]["fields"][field].get("enabled", True)
        return discovered

    @staticmethod
    def get_all_report_types():
        return {rt[0]: rt[1] for rt in ReportType.choices}

    def get_enabled_reports(self):
        all_reports = self.get_all_report_types()
        config = self.reporting_enabled_reports or {}
        # Default: all enabled
        return {k: config.get(k, True) for k in all_reports.keys()}
