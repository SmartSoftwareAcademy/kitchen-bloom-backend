from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.db.models import Count

from .models import TableCategory, Table, TableReservation


class TableReservationInline(admin.TabularInline):
    """Inline admin for table reservations."""
    model = TableReservation
    extra = 0
    readonly_fields = ['status', 'customer', 'reservation_time', 'expected_arrival_time']
    fields = ['status', 'customer', 'reservation_time', 'expected_arrival_time', 'expected_guest_count']
    ordering = ['-expected_arrival_time']

@admin.register(Table)
class TableAdmin(admin.ModelAdmin):
    """Admin interface for Table model."""
    list_display = (
        'number',
        'branch',
        'category',
        'capacity',
        'status',
        'get_current_reservation',
        'created_at'
    )
    list_filter = (
        'branch',
        'category',
        'status',
        'created_at'
    )
    search_fields = (
        'number',
        'branch__name',
        'category__name'
    )
    list_editable = ('status',)
    readonly_fields = ('created_at', 'updated_at')
    inlines = [TableReservationInline]
    actions = ['mark_as_available', 'mark_as_occupied', 'mark_as_maintenance']

    def get_current_reservation(self, obj):
        """Get the current reservation for the table."""
        return obj.reservations.filter(
            status__in=['confirmed', 'arrived']
        ).first()
    get_current_reservation.short_description = _('Current Reservation')

    def mark_as_available(self, request, queryset):
        """Mark selected tables as available."""
        updated = queryset.update(status='available')
        self.message_user(
            request,
            f'{updated} table(s) were marked as available.'
        )
    mark_as_available.short_description = _('Mark selected tables as available')

    def mark_as_occupied(self, request, queryset):
        """Mark selected tables as occupied."""
        updated = queryset.update(status='occupied')
        self.message_user(
            request,
            f'{updated} table(s) were marked as occupied.'
        )
    mark_as_occupied.short_description = _('Mark selected tables as occupied')

    def mark_as_maintenance(self, request, queryset):
        """Mark selected tables as maintenance."""
        updated = queryset.update(status='maintenance')
        self.message_user(
            request,
            f'{updated} table(s) were marked as maintenance.'
        )
    mark_as_maintenance.short_description = _('Mark selected tables as maintenance')

@admin.register(TableCategory)
class TableCategoryAdmin(admin.ModelAdmin):
    """Admin interface for TableCategory model."""
    list_display = (
        'name',
        'branch',
        'capacity',
        'color',
        'is_default',
        'table_count',
        'created_at'
    )
    list_filter = (
        'branch',
        'is_default',
        'created_at'
    )
    search_fields = (
        'name',
        'branch__name'
    )
    readonly_fields = ('created_at', 'updated_at')
    actions = ['mark_as_default']

    def get_queryset(self, request):
        """Add table count annotation to queryset."""
        return super().get_queryset(request).annotate(
            table_count=Count('tables')
        )

    def table_count(self, obj):
        """Get number of tables in this category."""
        return obj.table_count
    table_count.short_description = _('Number of Tables')
    table_count.admin_order_field = 'table_count'

    def mark_as_default(self, request, queryset):
        """Mark selected category as default."""
        if queryset.count() != 1:
            self.message_user(
                request,
                _('Please select exactly one category to mark as default.'),
                level='error'
            )
            return

        category = queryset.first()
        category.is_default = True
        category.save()
        self.message_user(
            request,
            f'Table category {category.name} was marked as default.'
        )
    mark_as_default.short_description = _('Mark as default category')

@admin.register(TableReservation)
class TableReservationAdmin(admin.ModelAdmin):
    """Admin interface for TableReservation model."""
    list_display = (
        'table',
        'customer',
        'expected_arrival_time',
        'status',
        'created_at'
    )
    list_filter = (
        'table__branch',
        'status',
        'expected_arrival_time',
        'created_at'
    )
    search_fields = (
        'table__number',
        'customer__name',
        'customer__email'
    )
    list_editable = ('status',)
    readonly_fields = ('created_at', 'updated_at')
    actions = [
        'mark_as_pending',
        'mark_as_confirmed',
        'mark_as_arrived',
        'mark_as_cancelled',
        'mark_as_no_show'
    ]

    def mark_as_pending(self, request, queryset):
        """Mark selected reservations as pending."""
        updated = queryset.update(status='pending')
        self.message_user(
            request,
            f'{updated} reservation(s) were marked as pending.'
        )
    mark_as_pending.short_description = _('Mark selected reservations as pending')

    def mark_as_confirmed(self, request, queryset):
        """Mark selected reservations as confirmed."""
        updated = queryset.update(status='confirmed')
        self.message_user(
            request,
            f'{updated} reservation(s) were marked as confirmed.'
        )
    mark_as_confirmed.short_description = _('Mark selected reservations as confirmed')

    def mark_as_arrived(self, request, queryset):
        """Mark selected reservations as arrived."""
        updated = queryset.update(status='arrived')
        self.message_user(
            request,
            f'{updated} reservation(s) were marked as arrived.'
        )
    mark_as_arrived.short_description = _('Mark selected reservations as arrived')

    def mark_as_cancelled(self, request, queryset):
        """Mark selected reservations as cancelled."""
        updated = queryset.update(status='cancelled')
        self.message_user(
            request,
            f'{updated} reservation(s) were marked as cancelled.'
        )
    mark_as_cancelled.short_description = _('Mark selected reservations as cancelled')

    def mark_as_no_show(self, request, queryset):
        """Mark selected reservations as no-show."""
        updated = queryset.update(status='no_show')
        self.message_user(
            request,
            f'{updated} reservation(s) were marked as no-show.'
        )
    mark_as_no_show.short_description = _('Mark selected reservations as no-show')


# Register models with admin site

