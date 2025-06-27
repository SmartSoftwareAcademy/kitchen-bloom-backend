from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.db.models import Count

from .models import Company, Branch


class BranchInline(admin.TabularInline):
    model = Branch
    extra = 0
    fields = ('name', 'code', 'city', 'phone', 'is_active', 'is_default')
    readonly_fields = ('is_default',)
    show_change_link = True


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('name', 'legal_name', 'tax_id', 'city', 'country', 'is_active', 'branch_count', 'created_at')
    list_filter = ('is_active', 'country', 'city')
    search_fields = ('name', 'legal_name', 'tax_id', 'registration_number')
    list_select_related = ()
    readonly_fields = ('created_at', 'updated_at', 'branch_count')
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'legal_name', 'description', 'logo', 'is_active')
        }),
        (_('Registration & Tax'), {
            'fields': ('tax_id', 'registration_number')
        }),
        (_('Contact Information'), {
            'fields': ('primary_contact_email', 'primary_contact_phone', 'website')
        }),
        (_('Address'), {
            'fields': ('address', 'city', 'state', 'postal_code', 'country')
        }),
        (_('Settings'), {
            'fields': ('currency', 'timezone')
        }),
        (_('Metadata'), {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )
    inlines = [BranchInline]
    
    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _branch_count=Count('branches', distinct=True)
        )
    
    def branch_count(self, obj):
        return obj._branch_count
    branch_count.short_description = _('Branches')
    branch_count.admin_order_field = '_branch_count'


class BranchActiveFilter(SimpleListFilter):
    title = _('status')
    parameter_name = 'is_active'
    
    def lookups(self, request, model_admin):
        return (
            ('active', _('Active')),
            ('inactive', _('Inactive')),
        )
    
    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(is_active=True)
        if self.value() == 'inactive':
            return queryset.filter(is_active=False)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'company_link', 'city', 'phone', 'is_active', 'is_default', 'created_at')
    list_filter = (BranchActiveFilter, 'is_default', 'company', 'city', 'country')
    search_fields = ('name', 'code', 'company__name', 'address', 'city', 'phone')
    list_select_related = ('company', 'manager')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('company', 'name', 'code', 'description', 'is_active', 'is_default')
        }),
        (_('Contact Information'), {
            'fields': ('manager', 'phone', 'email')
        }),
        (_('Address'), {
            'fields': ('address', 'city', 'state', 'postal_code', 'country')
        }),
        (_('Additional Information'), {
            'classes': ('collapse',),
            'fields': ('opening_hours', 'location', 'metadata')
        }),
        (_('Metadata'), {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def company_link(self, obj):
        url = reverse('admin:branches_company_change', args=[obj.company.id])
        return format_html('<a href="{}">{}</a>', url, obj.company.name)
    company_link.short_description = _('Company')
    company_link.admin_order_field = 'company__name'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('company', 'manager')
