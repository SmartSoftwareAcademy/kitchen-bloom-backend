from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.core.validators import RegexValidator

from apps.base.models import BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel


class Company(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """
    Represents a company that can have multiple branches.
    """
    legal_name = models.CharField(_('legal name'), max_length=255)
    tax_id = models.CharField(
        _('tax ID'), 
        max_length=50, 
        blank=True,
        null=True,
        help_text=_("Company's tax identification number")
    )
    registration_number = models.CharField(
        _('registration number'), 
        max_length=50, 
        blank=True,
        null=True
    )
    logo = models.ImageField(
        _('logo'), 
        upload_to='company/logos/', 
        blank=True, 
        null=True
    )
    primary_contact_email = models.EmailField(_('primary contact email'))
    primary_contact_phone = models.CharField(
        _('primary contact phone'), 
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ]
    )
    website = models.URLField(_('website'), blank=True)
    address = models.TextField(_('address'))
    city = models.CharField(_('city'), max_length=100)
    state = models.CharField(_('state/province'), max_length=100)
    postal_code = models.CharField(_('postal code'), max_length=20)
    country = models.CharField(_('country'), max_length=100, default='Kenya')
    is_active = models.BooleanField(_('is active'), default=True)
    currency = models.CharField(
        _('default currency'), 
        max_length=3, 
        default='KES',
        help_text=_('ISO 4217 currency code (e.g., KES, USD, EUR)')
    )
    timezone = models.CharField(
        _('timezone'), 
        max_length=50, 
        default='Africa/Nairobi',
        help_text=_('Timezone in format Area/Location')
    )
    
    class Meta:
        verbose_name = _('business')
        verbose_name_plural = _('businesses')
        ordering = ('name',)
    
    def __str__(self):
        return self.legal_name

class Branch(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """
    Represents a physical branch/location of a company.
    """
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name='branches',
        verbose_name=_('company')
    )
    code = models.CharField(
        _('branch code'), 
        max_length=10,
        help_text=_('Short code for the branch (e.g., NBO, MSA)')
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_branches',
        verbose_name=_('branch manager')
    )
    address = models.TextField(_('address'))
    city = models.CharField(_('city'), max_length=100)
    state = models.CharField(_('state/province'), max_length=100, blank=True)
    postal_code = models.CharField(_('postal code'), max_length=20, blank=True)
    country = models.CharField(_('country'), max_length=100, default='Kenya')
    phone = models.CharField(
        _('phone number'), 
        max_length=20,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
            )
        ]
    )
    email = models.EmailField(_('email address'), blank=True)
    is_active = models.BooleanField(_('is active'), default=True)
    is_default = models.BooleanField(
        _('is default branch'),
        default=False,
        help_text=_('Set as the default branch for the company')
    )
    opening_hours = models.JSONField(
        _('opening hours'),
        default=dict,
        blank=True,
        help_text=_('Store opening hours in JSON format')
    )
    location = models.JSONField(
        _('geolocation'),
        null=True,
        blank=True,
        help_text=_('Latitude and longitude for mapping')
    )
    metadata = models.JSONField(
        _('additional metadata'),
        default=dict,
        blank=True,
        help_text=_('Additional branch-specific data in JSON format')
    )

    class Meta:
        verbose_name = _('branch')
        verbose_name_plural = _('branches')
        ordering = ('company', 'name')
        unique_together = (('company', 'code'), ('company', 'name'))
    
    def __str__(self):
        return f"{self.name} ({self.company.name})"
    
    def save(self, *args, **kwargs):
        # Ensure only one default branch per company
        if self.is_default:
            Branch.objects.filter(company=self.company, is_default=True).exclude(pk=self.pk).update(is_default=False)
        elif not Branch.objects.filter(company=self.company, is_default=True).exclude(pk=self.pk).exists():
            self.is_default = True
        super().save(*args, **kwargs)
