from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe

from .models import KDSStation, KDSItem
from apps.branches.models import Branch


class KDSItemInline(admin.TabularInline):
    """Inline for KDS items in station admin."""
    model = KDSItem
    extra = 0
    fields = ('order_item', 'status', 'created_at', 'time_since_created')
    readonly_fields = ('order_item', 'created_at', 'time_since_created')
    show_change_link = True

    def time_since_created(self, obj):
        if not obj.created_at:
            return '-' 
        return obj.time_since_created
    time_since_created.short_description = _('Time since created')


@admin.register(KDSStation)
class KDSStationAdmin(admin.ModelAdmin):
    """Admin configuration for KDSStation model."""
    list_display = ('name', 'branch', 'station_type_display', 'is_active', 'items_count', 'created_at')
    list_filter = ('station_type', 'is_active', 'branch')
    search_fields = ('name', 'description', 'branch__name')
    list_editable = ('is_active',)
    list_select_related = ('branch',)
    inlines = [KDSItemInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'branch', 'is_active')
        }),
        (_('Configuration'), {
            'fields': ('station_type', 'metadata')
        }),
    )

    def station_type_display(self, obj):
        return obj.get_station_type_display()
    station_type_display.short_description = _('Station Type')
    station_type_display.admin_order_field = 'station_type'

    def items_count(self, obj):
        return obj.kds_items.count()
    items_count.short_description = _('Items Count')

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('kds_items')


class StatusFilter(admin.SimpleListFilter):
    """Filter for KDSItem status."""
    title = _('status')
    parameter_name = 'status'

    def lookups(self, request, model_admin):
        return KDSItem.STATUS_CHOICES

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(status=self.value())
        return queryset


@admin.register(KDSItem)
class KDSItemAdmin(admin.ModelAdmin):
    """Admin configuration for KDSItem model."""
    list_display = (
        'order_item_link', 'station_link', 'status_display',
        'time_since_created', 'time_in_status', 'completed_at', 'created_at'
    )
    list_filter = (StatusFilter, 'station__branch', 'station')
    search_fields = (
        'order_item__product__name',
        'kitchen_notes',
        'order_item__order__order_number'
    )
    list_select_related = ('station', 'order_item', 'order_item__order')
    readonly_fields = (
        'created_at', 'updated_at', 'completed_at',
        'time_since_created', 'time_in_status', 'order_item_link'
    )
    fieldsets = (
        (None, {
            'fields': ('order_item_link', 'station', 'status', 'kitchen_notes')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at', 'completed_at', 'time_since_created', 'time_in_status'),
            'classes': ('collapse',)
        }),
        (_('Metadata'), {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
    )
    actions = ['mark_in_progress', 'mark_completed', 'mark_cancelled']

    def order_item_link(self, obj):
        if not obj.order_item:
            return '-'
        url = reverse('admin:sales_orderitem_change', args=[obj.order_item.id])
        return format_html('<a href="{}">{}</a>', url, str(obj.order_item))
    order_item_link.short_description = _('Order Item')
    order_item_link.admin_order_field = 'order_item'

    def station_link(self, obj):
        if not obj.station:
            return '-'
        url = reverse('admin:kds_kdsstation_change', args=[obj.station.id])
        return format_html('<a href="{}">{}</a>', url, str(obj.station))
    station_link.short_description = _('Station')
    station_link.admin_order_field = 'station__name'

    def status_display(self, obj):
        return obj.get_status_display()
    status_display.short_description = _('Status')
    status_display.admin_order_field = 'status'

    def time_since_created(self, obj):
        return obj.time_since_created
    time_since_created.short_description = _('Time since created')

    def time_in_status(self, obj):
        return obj.time_in_status
    time_in_status.short_description = _('Time in status')

    def mark_in_progress(self, request, queryset):
        updated = 0
        for item in queryset:
            item.mark_in_progress()
            updated += 1
        self.message_user(request, f"Marked {updated} items as in progress.")
    mark_in_progress.short_description = _("Mark selected items as in progress")

    def mark_completed(self, request, queryset):
        updated = 0
        for item in queryset:
            item.mark_completed()
            updated += 1
        self.message_user(request, f"Marked {updated} items as completed.")
    mark_completed.short_description = _("Mark selected items as completed")

    def mark_cancelled(self, request, queryset):
        updated = 0
        for item in queryset:
            item.mark_cancelled()
            updated += 1
        self.message_user(request, f"Marked {updated} items as cancelled.")
    mark_cancelled.short_description = _("Mark selected items as cancelled")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'station',
            'order_item__product',
            'order_item__order'
        )
