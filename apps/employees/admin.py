from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.contenttypes.models import ContentType

from .models import Department, Employee
from apps.base.models import Address

User = get_user_model()


class DepartmentAdminForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Exclude current department and its descendants from parent choices
        if self.instance and self.instance.pk:
            self.fields['parent_department'].queryset = Department.objects.exclude(
                pk__in=[dept.pk for dept in self.instance.get_all_sub_departments()] + [self.instance.pk]
            )


class DepartmentAdmin(admin.ModelAdmin):
    form = DepartmentAdminForm
    list_display = ('name', 'code', 'parent_department', 'employee_count', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at', 'employee_count', 'sub_department_count')
    prepopulated_fields = {'code': ('name',)}
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'parent_department')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at', 'deleted_at'),
            'classes': ('collapse',)
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('employees')

    @admin.display(description=_('Employees'))
    def employee_count(self, obj):
        return obj.employees.count()
    
    @admin.display(description=_('Sub-Departments'))
    def sub_department_count(self, obj):
        return obj.sub_departments.count()


class AddressInline(GenericTabularInline):
    model = Address
    ct_field = 'content_type'
    ct_fk_field = 'object_id'
    extra = 1
    max_num = 5
    fields = ('address_type', 'address_line1', 'address_line2', 'city', 'state', 
              'postal_code', 'country', 'is_primary')
    readonly_fields = ('created_at', 'updated_at')
    
    def get_queryset(self, request):
        # Only show addresses that belong to the current object
        qs = super().get_queryset(request)
        if hasattr(self, 'parent_model') and hasattr(self, 'parent_obj'):
            return qs.filter(
                content_type=ContentType.objects.get_for_model(self.parent_model),
                object_id=self.parent_obj.pk
            )
        return qs.none()


class EmployeeAdminForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = '__all__'
    
    def __init__(self, *args, **kwargs):
        from apps.accounts.models import Role
        super().__init__(*args, **kwargs)
        
        # Limit manager choices to active employees with management roles
        if 'supervisor' in self.fields:
            self.fields['supervisor'].queryset = Employee.objects.filter(
                is_active=True,
                role__name__in=[Role.ADMIN, Role.MANAGER]
            )
        
        # Initialize role queryset with all roles
        if 'role' in self.fields:
            self.fields['role'].queryset = Role.objects.all()


class EmployeeAdmin(admin.ModelAdmin):
    form = EmployeeAdminForm
    list_display = ('employee_id', 'full_name', 'email', 'department', 'role', 'employment_type', 'is_active')
    list_filter = ('is_active', 'employment_type', 'department', 'hire_date')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name', 'user__email', 'phone_number')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at', 'full_name', 'email', 'age', 'tenure_years')
    inlines = [AddressInline]
    
    fieldsets = (
        ('Personal Information', {
            'fields': (
                'user', 'employee_id', 'date_of_birth', 'gender',
                'phone_number', 'emergency_contact_name',
                'emergency_contact_phone', 'emergency_contact_relation'
            )
        }),
        ('Employment Details', {
            'fields': (
                'department', 'role', 'supervisor', 'hire_date',
                'employment_type', 'salary', 'is_active'
            )
        }),
        ('Banking Information', {
            'classes': ('collapse',),
            'fields': ('bank_name', 'bank_account_number', 'bank_branch')
        }),
        ('Government IDs', {
            'classes': ('collapse',),
            'fields': ('tax_id', 'national_id', 'nhif_number', 'nssf_number', 'kra_pin')
        }),
        ('Additional Information', {
            'classes': ('collapse',),
            'fields': ('notes',)
        }),
        ('Timestamps', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at', 'deleted_at')
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'user', 'department', 'role', 'supervisor', 'supervisor__user'
        )
    
    @admin.display(description=_('Full Name'))
    def full_name(self, obj):
        return obj.full_name
    
    @admin.display(description=_('Email'))
    def email(self, obj):
        return obj.user.email
    
    @admin.display(description=_('Age'))
    def age(self, obj):
        return obj.age
    
    @admin.display(description=_('Tenure (Years)'))
    def tenure_years(self, obj):
        return obj.tenure_years
    
    def save_model(self, request, obj, form, change):
        # Set created_by/updated_by if not set
        if not obj.pk:
            obj.created_by = request.user
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)


# Register models
admin.site.register(Department, DepartmentAdmin)
admin.site.register(Employee, EmployeeAdmin)
