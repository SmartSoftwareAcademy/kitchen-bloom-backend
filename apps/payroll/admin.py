from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import PayrollPeriod, EmployeePayroll


class EmployeePayrollInline(admin.TabularInline):
    """Inline admin for EmployeePayroll."""
    model = EmployeePayroll
    extra = 0
    fields = (
        'employee',
        'basic_salary',
        'gross_pay',
        'total_deductions',
        'net_pay',
        'status',
        'payment_date',
        'payment_method',
        'payment_reference'
    )
    readonly_fields = (
        'gross_pay',
        'total_deductions',
        'net_pay'
    )


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    """Admin configuration for PayrollPeriod."""
    list_display = (
        'start_date',
        'end_date',
        'status',
        'total_payroll',
        'created_by',
        'created_at'
    )
    list_filter = (
        'status',
        'created_at',
        'start_date'
    )
    search_fields = (
        'notes',
        'created_by__user__email'
    )
    ordering = ('-start_date',)
    inlines = [EmployeePayrollInline]
    actions = ['mark_as_processing', 'mark_as_completed', 'mark_as_closed']

    def total_payroll(self, obj):
        """Display total payroll amount for this period."""
        return obj.get_total_payroll()
    total_payroll.short_description = _('Total Payroll')
    total_payroll.admin_order_field = 'total_payroll'

    def mark_as_processing(self, request, queryset):
        """Mark selected payroll periods as processing."""
        updated = queryset.update(status='processing')
        self.message_user(request, f'Successfully marked {updated} payroll periods as processing.')
    mark_as_processing.short_description = _('Mark selected periods as processing')

    def mark_as_completed(self, request, queryset):
        """Mark selected payroll periods as completed."""
        updated = queryset.update(status='completed')
        self.message_user(request, f'Successfully marked {updated} payroll periods as completed.')
    mark_as_completed.short_description = _('Mark selected periods as completed')

    def mark_as_closed(self, request, queryset):
        """Mark selected payroll periods as closed."""
        updated = queryset.update(status='closed')
        self.message_user(request, f'Successfully marked {updated} payroll periods as closed.')
    mark_as_closed.short_description = _('Mark selected periods as closed')


@admin.register(EmployeePayroll)
class EmployeePayrollAdmin(admin.ModelAdmin):
    """Admin configuration for EmployeePayroll."""
    list_display = (
        'employee',
        'payroll_period',
        'basic_salary',
        'gross_pay',
        'total_deductions',
        'net_pay',
        'status',
        'payment_date',
        'created_by',
        'created_at'
    )
    list_filter = (
        'status',
        'payroll_period__start_date',
        'payment_method',
        'created_at'
    )
    search_fields = (
        'employee__user__email',
        'employee__user__first_name',
        'employee__user__last_name',
        'payment_reference',
        'created_by__user__email'
    )
    ordering = ('-payroll_period__start_date', 'employee__user__email')
    readonly_fields = (
        'gross_pay',
        'total_deductions',
        'net_pay'
    )
    actions = [
        'calculate_payroll',
        'mark_as_paid',
        'mark_as_approved',
        'mark_as_cancelled'
    ]

    def calculate_payroll(self, request, queryset):
        """Calculate payroll for selected records."""
        for obj in queryset:
            obj.calculate_payroll()
            obj.save()
        self.message_user(request, f'Successfully calculated payroll for {queryset.count()} records.')
    calculate_payroll.short_description = _('Calculate payroll')

    def mark_as_paid(self, request, queryset):
        """Mark selected payrolls as paid."""
        for obj in queryset:
            obj.mark_as_paid()
        self.message_user(request, f'Successfully marked {queryset.count()} payrolls as paid.')
    mark_as_paid.short_description = _('Mark selected payrolls as paid')

    def mark_as_approved(self, request, queryset):
        """Mark selected payrolls as approved."""
        updated = queryset.update(status='approved')
        self.message_user(request, f'Successfully marked {updated} payrolls as approved.')
    mark_as_approved.short_description = _('Mark selected payrolls as approved')

    def mark_as_cancelled(self, request, queryset):
        """Mark selected payrolls as cancelled."""
        for obj in queryset:
            try:
                obj.cancel()
            except ValidationError as e:
                self.message_user(request, str(e), level='error')
        self.message_user(request, f'Successfully cancelled {queryset.count()} payrolls.')
    mark_as_cancelled.short_description = _('Cancel selected payrolls')

    def get_queryset(self, request):
        """Customize queryset to include related fields."""
        qs = super().get_queryset(request)
        return qs.select_related(
            'employee',
            'employee__user',
            'payroll_period',
            'created_by',
            'created_by__user'
        )

    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly based on status."""
        readonly = super().get_readonly_fields(request, obj)
        if obj and obj.status != 'draft':
            return readonly + (
                'basic_salary',
                'salary_structure',
                'payroll_period'
            )
        return readonly
