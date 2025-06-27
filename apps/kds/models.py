from django.db import models
from django.utils.translation import gettext_lazy as _
from django.db.models import JSONField
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.base.models import BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel
from apps.branches.models import Branch
from apps.sales.models import Order, OrderItem


class KDSStation(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Represents a kitchen display station."""
    branch = models.ForeignKey(Branch,on_delete=models.CASCADE,related_name='kds_stations',verbose_name=_('branch'))
    station_type = models.CharField(_('station type'),max_length=50,choices=[
            ('hot_kitchen', _('Hot Kitchen')),
            ('cold_kitchen', _('Cold Kitchen')),
            ('prep', _('Prep Station')),
            ('beverage', _('Beverage Station'))
        ],
        default='hot_kitchen',
        help_text=_('Type of kitchen station')
    )
    is_active = models.BooleanField(_('is active'),default=True,help_text=_('Whether this station is currently active'))
    metadata = JSONField(_('additional metadata'),default=dict,blank=True,help_text=_('Additional station-specific data in JSON format'))

    class Meta:
        verbose_name = _('kds station')
        verbose_name_plural = _('kds stations')
        ordering = ('branch', 'name')
        unique_together = (('branch', 'name'),)
        indexes = [
            models.Index(fields=['branch', 'is_active']),
            models.Index(fields=['branch', 'station_type'])
        ]

    def __str__(self):
        return f"{self.name} ({self.get_station_type_display()}) at {self.branch.name}"

    @property
    def active_orders(self):
        """Get active orders for this station."""
        return Order.objects.filter(
            branch=self.branch,
            status__in=['confirmed', 'processing', 'ready'],
            items__kds_item__station=self
        ).distinct()


class KDSItem(BaseNameDescriptionModel, TimestampedModel, SoftDeleteModel):
    """Represents an item on the kitchen display system."""
    station = models.ForeignKey(KDSStation,on_delete=models.CASCADE,related_name='kds_items',verbose_name=_('station'))
    order_item = models.OneToOneField(OrderItem,on_delete=models.CASCADE,related_name='kds_item',verbose_name=_('order item'))
    status = models.CharField(_('status'),max_length=20,choices=[
            ('pending', _('Pending')),
            ('in_progress', _('In Progress')),
            ('completed', _('Completed')),
            ('cancelled', _('Cancelled'))
        ],
        default='pending',
        help_text=_('Current status of the kitchen item')
    )
    kitchen_notes = models.TextField(_('kitchen notes'),blank=True,help_text=_('Notes from kitchen staff about this item'))
    completed_at = models.DateTimeField(_('completed at'),null=True,blank=True,help_text=_('When the item was completed'))
    metadata = JSONField(_('additional metadata'),default=dict,blank=True,help_text=_('Additional item-specific data in JSON format'))

    class Meta:
        verbose_name = _('kds item')
        verbose_name_plural = _('kds items')
        ordering = ('-created_at', 'status')
        indexes = [
            models.Index(fields=['station', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['completed_at'])
        ]

    def __str__(self):
        return f"{self.order_item.product.name} at {self.station.name}"

    @property
    def is_pending(self):
        """Check if item is pending."""
        return self.status == 'pending'

    @property
    def is_in_progress(self):
        """Check if item is in progress."""
        return self.status == 'in_progress'

    @property
    def is_completed(self):
        """Check if item is completed."""
        return self.status == 'completed'

    @property
    def is_cancelled(self):
        """Check if item is cancelled."""
        return self.status == 'cancelled'

    def mark_in_progress(self):
        """Mark item as in progress."""
        self.status = 'in_progress'
        self.save()

    def mark_completed(self):
        """Mark item as completed."""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()

    def mark_cancelled(self):
        """Mark item as cancelled."""
        self.status = 'cancelled'
        self.save()


@receiver(post_save, sender=OrderItem)
def create_kds_item(sender, instance, created, **kwargs):
    """Create KDS item when order item is created."""
    if created:
        # Determine station type based on product or menu_item
        station_type = None
        if instance.product:
            station_type = instance.product.get_kds_station_type()
        elif instance.menu_item and hasattr(instance.menu_item, 'get_kds_station_type'):
            station_type = instance.menu_item.get_kds_station_type()
        # Only proceed if station_type is found
        if station_type:
            station = KDSStation.objects.filter(
                branch=instance.order.branch,
                station_type=station_type
            ).first()
            if station:
                KDSItem.objects.create(
                    station=station,
                    order_item=instance
                )
