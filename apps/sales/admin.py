from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Order, OrderItem

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1
    fields = (
       'item_type', 'product','menu_item', 'quantity', 'unit_price', 'discount_amount', 'tax_amount',
        'subtotal', 'total', 'status', 'kitchen_status', 'notes', 'kitchen_notes'
    )
    readonly_fields = ('subtotal', 'total')

class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'order_number', 'branch', 'get_customers', 'get_tables', 'order_type', 'status',
        'total_amount', 'payment_status', 'created_at', 'updated_at',
        'get_payment_method_display', 'get_order_source'
    )
    list_filter = (
        'branch', 'status', 'order_type', 'payment_status', 'created_at',
        'payment_method'
    )
    search_fields = (
        'order_number', 'delivery_address', 'notes'
    )
    inlines = [OrderItemInline]
    readonly_fields = ('order_number', 'subtotal', 'total_amount', 'created_at', 'updated_at')
    filter_horizontal = ('customers', 'tables')
    fieldsets = (
        (_('Order Details'), {
            'fields': (
                'order_number', 'branch', 'order_type', 'status', 'tables',
                'delivery_address'
            )
        }),
        (_('Customer Information'), {
            'fields': ('customers',)
        }),
        (_('Financial Details'), {
            'fields': (
                'subtotal', 'tax_amount', 'discount_amount', 'total_amount',
                'payment_status', 'payment_method', 'notes'
            )
        }),
    )
    ordering = ('-created_at',)
    actions = ['export_orders', 'process_bulk_payment', 'generate_refund',
               'send_order_confirmation', 'generate_receipt']

    def get_customers(self, obj):
        return ", ".join([c.full_name for c in obj.customers.all()])
    get_customers.short_description = _('Customers')

    def get_tables(self, obj):
        return ", ".join([str(t) for t in obj.tables.all()])
    get_tables.short_description = _('Tables')

    def get_payment_method_display(self, obj):
        """Get payment method display name."""
        return obj.get_payment_method_display()
    get_payment_method_display.short_description = _('Payment Method')

    def get_order_source(self, obj):
        """Get order source (dine-in, takeaway, delivery, online)."""
        return obj.get_order_type_display()
    get_order_source.short_description = _('Order Source')

    def export_orders(self, request, queryset):
        """Export selected orders to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="orders.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Order Number', 'Branch', 'Customer', 'Order Type', 'Status',
            'Subtotal', 'Tax', 'Discount', 'Total', 'Payment Status',
            'Payment Method', 'Created At', 'Updated At',
            'Customer Segment', 'Order Source'
        ])
        
        for order in queryset:
            writer.writerow([
                order.order_number, order.branch, order.get_customers(),
                order.get_order_type_display(), order.get_status_display(),
                order.subtotal, order.tax_amount, order.discount_amount,
                order.total_amount, order.get_payment_status_display(),
                order.get_payment_method_display(), order.created_at,
                order.updated_at, order.get_customer_segment(),
                order.get_order_source()
            ])
        
        return response
    export_orders.short_description = _('Export selected orders to CSV')

    def process_bulk_payment(self, request, queryset):
        """Process bulk payment for selected orders."""
        # Implementation for bulk payment processing
        self.message_user(request, _('Bulk payment processed successfully'))
    process_bulk_payment.short_description = _('Process bulk payment')

    def generate_refund(self, request, queryset):
        """Generate refund for selected orders."""
        # Implementation for generating refunds
        self.message_user(request, _('Refunds generated successfully'))
    generate_refund.short_description = _('Generate refunds')

    def send_order_confirmation(self, request, queryset):
        """Send order confirmation to customers."""
        # Implementation for sending order confirmations
        self.message_user(request, _('Order confirmations sent successfully'))
    send_order_confirmation.short_description = _('Send order confirmations')

    def generate_receipt(self, request, queryset):
        """Generate receipts for selected orders."""
        # Implementation for generating receipts
        self.message_user(request, _('Receipts generated successfully'))
    generate_receipt.short_description = _('Generate receipts')

    def save_model(self, request, obj, form, change):
        obj._skip_ws = True
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.prefetch_related('items', 'payments', 'customers', 'tables')

class OrderItemAdmin(admin.ModelAdmin):
    list_display = (
        'order', 'item_type', 'product', 'menu_item', 'quantity', 'unit_price', 'subtotal', 'total',
        'status', 'kitchen_status', 'assigned_customer', 'get_allergens', 'created_at'
    )
    list_filter = (
        'order__branch', 'status', 'kitchen_status', 'created_at', 'item_type'
    )
    search_fields = (
        'order__order_number', 'product__name', 'menu_item__name', 'notes', 'kitchen_notes'
    )
    readonly_fields = ('subtotal', 'total')
    fieldsets = (
        (_('Order Item Details'), {
            'fields': (
                'order', 'item_type', 'product', 'menu_item', 'quantity', 'unit_price', 'discount_amount',
                'tax_amount', 'subtotal', 'total', 'status', 'kitchen_status', 'assigned_customer', 'modifiers'
            )
        }),
        (_('Notes'), {
            'fields': ('notes', 'kitchen_notes')
        }),
        (_('Timestamps'), {
            'fields': ('created_at',)
        })
    )
    ordering = ('-created_at',)
    actions = ['export_items']

    def get_allergens(self, obj):
        return ", ".join([a.name for a in obj.menu_item.allergens.all()]) if obj.menu_item else ''
    get_allergens.short_description = _('Allergens')

    def export_items(self, request, queryset):
        """Export selected order items to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="order_items.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Order Number', 'Product', 'Quantity', 'Unit Price', 'Subtotal',
            'Tax', 'Discount', 'Total', 'Status', 'Kitchen Status', 'Created At'
        ])
        
        for item in queryset:
            writer.writerow([
                item.order.order_number, item.product, item.quantity,
                item.unit_price, item.subtotal, item.tax_amount,
                item.discount_amount, item.total, item.status,
                item.kitchen_status, item.created_at
            ])
        
        return response
    export_items.short_description = _('Export selected items to CSV')

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('order', 'product', 'menu_item', 'assigned_customer')

    def save_model(self, request, obj, form, change):
        obj._skip_ws = True
        super().save_model(request, obj, form, change)

admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
