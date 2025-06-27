from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html
from .models import Customer, CustomerTag

class CustomerTagInline(admin.TabularInline):
    model = Customer.tags.through
    extra = 1
    verbose_name = _('tag')
    verbose_name_plural = _('tags')

class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'customer_code', 'full_name', 'customer_type', 'company_name',
        'get_total_orders', 'get_total_spent', 'get_days_since_last_order',
        'get_allergens', 'created_at', 'updated_at'
    )
    list_filter = (
        'customer_type', 'created_at', 'updated_at', 'tags',
        'preferred_contact_method', 'marketing_opt_in',
        'loyalty_program', 'allergens'
    )
    search_fields = (
        'customer_code', 'user__first_name', 'user__last_name',
        'company_name', 'alternate_phone', 'tax_id', 'company_registration'
    )
    inlines = [CustomerTagInline]
    readonly_fields = (
        'customer_code', 'full_name', 'created_at', 'updated_at'
    )
    filter_horizontal = ('tags', 'allergens')
    fieldsets = (
        (_('Basic Information'), {
            'fields': (
                'user', 'customer_code', 'customer_type', 'gender',
                'date_of_birth', 'tax_id', 'alternate_phone',
                'preferred_contact_method', 'marketing_opt_in', 'allergens'
            )
        }),
        (_('Address Information'), {
            'fields': (
                'address_line1', 'address_line2', 'city', 'state',
                'postal_code', 'country'
            )
        }),
        (_('Business Information'), {
            'fields': (
                'company_name', 'company_registration', 'vat_number',
                'website'
            )
        }),
        (_('Preferences and Notes'), {
            'fields': ('notes',)
        }),
        (_('Loyalty Program'), {
            'fields': ('loyalty_program',)
        }),
        (_('Tags'), {
            'fields': ('tags',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )
    ordering = ('-created_at',)
    actions = ['export_customers', 'send_mass_email', 'generate_campaign_report']

    def get_total_orders(self, obj):
        """Get total number of orders for the customer."""
        return 0  # TODO: Implement actual order counting
    get_total_orders.short_description = _('Total Orders')
    get_total_orders.admin_order_field = None  # Can't sort by this field

    def get_total_spent(self, obj):
        """Get total amount spent by the customer."""
        return "0.00"  # TODO: Implement actual total spent calculation
    get_total_spent.short_description = _('Total Spent')
    get_total_spent.admin_order_field = None  # Can't sort by this field

    def get_days_since_last_order(self, obj):
        """Get number of days since the last order."""
        return _('No orders')  # TODO: Implement actual calculation
    get_days_since_last_order.short_description = _('Last Order')
    get_days_since_last_order.admin_order_field = None  # Can't sort by this field

    def get_allergens(self, obj):
        return ", ".join([a.name for a in obj.allergens.all()])
    get_allergens.short_description = _('Allergens')

    def get_preferred_branch(self, obj):
        branch = obj.get_preferred_branch()
        if branch:
            return format_html('<a href="{}">{}</a>',
                f"/admin/branches/branch/{branch.pk}/change/",
                branch.name
            )
        return '-'
    get_preferred_branch.short_description = _('Preferred Branch')
    get_preferred_branch.admin_order_field = 'preferred_branch'

    def export_customers(self, request, queryset):
        """Export selected customers to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="customers.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Customer Code', 'Full Name', 'Company Name', 'Customer Type',
            'Alternate Phone', 'Preferred Contact Method', 'Created At'
        ])
        
        for customer in queryset:
            writer.writerow([
                customer.customer_code,
                customer.full_name,
                customer.company_name or '',
                customer.get_customer_type_display(),
                customer.alternate_phone or '',
                customer.get_preferred_contact_method_display(),
                customer.created_at.strftime('%Y-%m-%d %H:%M:%S') if customer.created_at else ''
            ])
        
        return response
    export_customers.short_description = _('Export selected customers to CSV')

class CustomerTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'color', 'description', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
    fieldsets = (
        (_('Tag Information'), {
            'fields': ('name', 'color', 'description')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'modified')
        })
    )
    ordering = ('name',)
    actions = ['export_tags']

    def export_tags(self, request, queryset):
        """Export selected customer tags to CSV."""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="customer_tags.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Tag Name', 'Color', 'Description', 'Created At', 'Modified At'
        ])
        
        for tag in queryset:
            writer.writerow([
                tag.name, tag.color, tag.description, tag.created_at, tag.modified
            ])
        
        return response
    export_tags.short_description = _('Export selected tags to CSV')

admin.site.register(Customer, CustomerAdmin)
admin.site.register(CustomerTag, CustomerTagAdmin)
