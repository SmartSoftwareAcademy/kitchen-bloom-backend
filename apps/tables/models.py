import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.db.models import JSONField
from django.utils import timezone
from apps.base.models import BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel
from apps.branches.models import Branch
from apps.employees.models import Employee
from apps.crm.models import Customer

class FloorPlan(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Represents a floor plan for a restaurant branch."""
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='floor_plans', 
                             verbose_name=_('branch'))
    is_active = models.BooleanField(_('is active'), default=True,
                                  help_text=_('Whether this floor plan is currently active'))
    width = models.PositiveIntegerField(_('width'), default=1000,
                                      help_text=_('Width of the floor plan in pixels'))
    height = models.PositiveIntegerField(_('height'), default=800,
                                       help_text=_('Height of the floor plan in pixels'))
    background_image = models.ImageField(_('background image'), upload_to='floor_plans/',
                                       null=True, blank=True,
                                       help_text=_('Background image for the floor plan'))
    metadata = JSONField(_('additional metadata'), default=dict, blank=True,
                        help_text=_('Additional floor plan data in JSON format'))

    class Meta:
        verbose_name = _('floor plan')
        verbose_name_plural = _('floor plans')
        ordering = ('branch', 'name')
        unique_together = (('branch', 'name'),)
        indexes = [
            models.Index(fields=['branch', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.branch.name})"

    def save(self, *args, **kwargs):
        """Ensure only one active floor plan per branch."""
        if self.is_active:
            FloorPlan.objects.filter(branch=self.branch, is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class TableCategory(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Category for organizing tables."""
    branch = models.ForeignKey(Branch,on_delete=models.CASCADE,related_name='table_categories',verbose_name=_('branch'))
    capacity = models.PositiveIntegerField(_('default capacity'),default=4,help_text=_('Default capacity for tables in this category'))
    color = models.CharField(_('color'),max_length=7,default='#000000',help_text=_('Color for table category visualization'))
    is_default = models.BooleanField(_('is default category'),default=False,help_text=_('Set as default category for new tables'))
    metadata = JSONField(_('additional metadata'),default=dict,blank=True,help_text=_('Additional category-specific data in JSON format'))

    class Meta:
        verbose_name = _('table category')
        verbose_name_plural = _('table categories')
        ordering = ('branch', 'name')
        unique_together = (('branch', 'name'),)
        indexes = [
            models.Index(fields=['branch', 'is_default']),
            models.Index(fields=['branch', 'name'])
        ]

    def __str__(self):
        return f"{self.name} ({self.branch.name})"

    def save(self, *args, **kwargs):
        """Ensure only one default category per branch."""
        if self.is_default:
            TableCategory.objects.filter(branch=self.branch,is_default=True).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)

class Table(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Represents a physical table in a branch."""
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='tables', verbose_name=_('branch'))
    floor_plan = models.ForeignKey(FloorPlan, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name='tables', verbose_name=_('floor plan'))
    category = models.ForeignKey(TableCategory, on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='tables', verbose_name=_('category'))
    number = models.CharField(_('table number'), max_length=10, 
                             help_text=_('Unique identifier for the table'))
    capacity = models.PositiveIntegerField(_('capacity'), default=4, validators=[MinValueValidator(1)], 
                                          help_text=_('Maximum number of guests that can sit at this table'))
    location = models.JSONField(_('location coordinates'), null=True, blank=True,
                               help_text=_('Table position coordinates for floor plan (x, y, rotation)'))
    size = models.JSONField(_('table size'), null=True, blank=True,
                           help_text=_('Table dimensions (width, height) in pixels'))
    shape = models.CharField(_('table shape'), max_length=20, default='rectangle',
                            choices=[
                                ('rectangle', _('Rectangle')),
                                ('circle', _('Circle')),
                                ('square', _('Square')),
                                ('oval', _('Oval'))
                            ],
                            help_text=_('Shape of the table for floor plan display'))
    status = models.CharField(_('status'), max_length=20,
                             choices=[
                                 ('available', _('Available')),
                                 ('occupied', _('Occupied')),
                                 ('reserved', _('Reserved')),
                                 ('maintenance', _('Maintenance')),
                                 ('cleaning', _('Cleaning'))
                             ],
                             default='available',
                             help_text=_('Current status of the table'))
    waiter = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='assigned_tables', verbose_name=_('waiter'))
    is_combined = models.BooleanField(_('is combined table'), default=False,
                                     help_text=_('Whether this is a combined table'))
    combined_tables = models.ManyToManyField('self', blank=True, symmetrical=False,
                                           related_name='combined_into',
                                           help_text=_('Tables that are combined into this table'))
    metadata = JSONField(_('additional metadata'), default=dict, blank=True,
                        help_text=_('Additional table-specific data in JSON format'))
    last_status_change = models.DateTimeField(_('last status change'), auto_now_add=True)

    class Meta:
        verbose_name = _('table')
        verbose_name_plural = _('tables')
        ordering = ('branch', 'number')
        unique_together = (('branch', 'number'),)
        indexes = [
            models.Index(fields=['branch', 'status']),
            models.Index(fields=['branch', 'category']),
            models.Index(fields=['branch', 'number'])
        ]

    def __str__(self):
        return f"{self.number} ({self.branch.name})"

    def save(self, *args, **kwargs):
        """Set default capacity from category if not specified."""
        if not self.capacity and self.category:
            self.capacity = self.category.capacity
        super().save(*args, **kwargs)

    @property
    def is_available(self):
        """Check if table is available."""
        return self.status == 'available'

    @property
    def is_occupied(self):
        """Check if table is occupied."""
        return self.status == 'occupied'

    @property
    def is_reserved(self):
        """Check if table is reserved."""
        return self.status == 'reserved'

    @property
    def is_in_maintenance(self):
        """Check if table is in maintenance."""
        return self.status == 'maintenance'

class TableReservation(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Represents a table reservation."""
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('confirmed', _('Confirmed')),
        ('seated', _('Seated')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
        ('no_show', _('No Show')),
    ]
    
    reservation_number = models.CharField(_('reservation number'), max_length=50, unique=True, 
                                         default=uuid.uuid4, editable=False)
    table = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='reservations', 
                             verbose_name=_('table'))
    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, 
                                related_name='table_reservations', verbose_name=_('customer'))
    reservation_time = models.DateTimeField(_('reservation time'), auto_now_add=True,
                                           help_text=_('Time when the table was reserved'))
    expected_arrival_time = models.DateTimeField(_('expected arrival time'),
                                               help_text=_('Expected time of customer arrival'))
    actual_arrival_time = models.DateTimeField(_('actual arrival time'), null=True, blank=True,
                                              help_text=_('Actual time of arrival'))
    departure_time = models.DateTimeField(_('departure time'), null=True, blank=True,
                                         help_text=_('Time when the customer left'))
    status = models.CharField(_('status'), max_length=20, 
                             choices=STATUS_CHOICES,
                             default='pending',
                             help_text=_('Current status of the reservation'))
    covers = models.PositiveIntegerField(_('number of covers'), default=1,
                                        validators=[MinValueValidator(1)],
                                        help_text=_('Number of guests expected'))
    notes = models.TextField(_('notes'), blank=True,
                           help_text=_('Additional notes about the reservation'))
    source = models.CharField(_('reservation source'), max_length=50, 
                             default='in_house',
                             choices=[
                                 ('in_house', _('In-House')),
                                 ('website', _('Website')),
                                 ('phone', _('Phone')),
                                 ('mobile_app', _('Mobile App')),
                                 ('walk_in', _('Walk-In')),
                                 ('other', _('Other'))
                             ],
                             help_text=_('Source of the reservation'))
    metadata = JSONField(_('additional metadata'), default=dict, blank=True,
                        help_text=_('Additional reservation data in JSON format'))

    class Meta:
        verbose_name = _('table reservation')
        verbose_name_plural = _('table reservations')
        ordering = ('-expected_arrival_time', 'table__number')
        indexes = [
            models.Index(fields=['table', 'status']),
            models.Index(fields=['expected_arrival_time']),
            models.Index(fields=['status'])
        ]

    def __str__(self):
        return f"{self.table.number} - {self.expected_arrival_time}"

    @property
    def is_pending(self):
        """Check if reservation is pending."""
        return self.status == 'pending'

    @property
    def is_confirmed(self):
        """Check if reservation is confirmed."""
        return self.status == 'confirmed'

    @property
    def is_arrived(self):
        """Check if reservation has arrived."""
        return self.status == 'arrived'

    @property
    def is_cancelled(self):
        """Check if reservation is cancelled."""
        return self.status == 'cancelled'

    @property
    def is_no_show(self):
        """Check if reservation is a no-show."""
        return self.status == 'no_show'

    def save(self, *args, **kwargs):
        """Update table status based on reservation status."""
        super().save(*args, **kwargs)
        if self.status == 'confirmed':
            self.table.status = 'reserved'
            self.table.save()
        elif self.status in ['cancelled', 'no_show']:
            self.table.status = 'available'
            self.table.save()
