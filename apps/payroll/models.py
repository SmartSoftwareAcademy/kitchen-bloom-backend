from django.db import models
from django.db.models import Sum, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from apps.employees.models import Employee, RateStructure
from apps.branches.models import Branch
from apps.accounting.models import Expense, Revenue
from apps.base.models import TimestampedModel, SoftDeleteModel


class PayrollPeriod(TimestampedModel, SoftDeleteModel):
    """Period for payroll processing."""
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'))
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='payroll_periods', verbose_name=_('branch'), null=True, blank=True, help_text=_('Leave blank for company-wide payroll'))
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=[
            ('draft', _('Draft')),
            ('processing', _('Processing')),
            ('completed', _('Completed')),
            ('closed', _('Closed'))
        ],
        default='draft'
    )
    notes = models.TextField(_('notes'), blank=True)
    created_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_payroll_periods',
        verbose_name=_('created by')
    )
    last_modified_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        related_name='modified_payroll_periods',
        verbose_name=_('last modified by')
    )

    class Meta:
        verbose_name = _('payroll period')
        verbose_name_plural = _('payroll periods')
        ordering = ['-start_date']

    def __str__(self):
        branch_name = f" - {self.branch.name}" if self.branch else " - Company-wide"
        return f"{self.start_date} to {self.end_date}{branch_name}"

    def clean(self):
        """Validate payroll period."""
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValidationError(_('Start date cannot be after end date.'))

    def get_total_payroll(self):
        """Get total payroll amount for this period."""
        return self.employee_payrolls.aggregate(total=Sum('net_pay'))['total'] or 0

    def get_employees_for_payroll(self):
        """Get employees eligible for payroll in this period."""
        if self.branch:
            return Employee.objects.filter(branch=self.branch, is_active=True)
        return Employee.objects.filter(is_active=True)

class DeductionCategory(TimestampedModel, SoftDeleteModel):
    """
    Categories for different types of deductions.
    """
    DEDUCTION_TYPES = [
        ('damage', _('Damage/Loss')),
        ('absenteeism', _('Absenteeism')),
        ('lateness', _('Lateness')),
        ('performance', _('Performance')),
        ('advance', _('Salary Advance')),
        ('loan', _('Loan Repayment')),
        ('tax', _('Tax')),
        ('insurance', _('Insurance')),
        ('other', _('Other')),
    ]

    name = models.CharField(_('category name'), max_length=100)
    deduction_type = models.CharField(_('deduction type'), max_length=20, choices=DEDUCTION_TYPES, default='other')
    description = models.TextField(_('description'), blank=True)
    is_active = models.BooleanField(_('is active'), default=True)
    affects_accounting = models.BooleanField(_('affects accounting'), default=False, help_text=_('Whether this deduction affects cash flow/accounting'))
    accounting_category = models.CharField(_('accounting category'), max_length=50, blank=True, help_text=_('Accounting category for cash flow tracking'))
    created_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name='created_deduction_categories', verbose_name=_('created by'))

    class Meta:
        verbose_name = _('deduction category')
        verbose_name_plural = _('deduction categories')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_deduction_type_display()})"

class PayrollItem(TimestampedModel, SoftDeleteModel):
    """Item in payroll."""
    ITEM_TYPES = [
        ('salary', _('Salary')),
        ('allowance', _('Allowance')),
        ('deduction', _('Deduction')),
        ('tax', _('Tax')),
        ('bonus', _('Bonus')),
        ('overtime', _('Overtime')),
    ]

    name = models.CharField(_('name'), max_length=100)
    item_type = models.CharField(_('item type'), max_length=20, choices=ITEM_TYPES, default='salary')
    amount = models.DecimalField(_('amount'), max_digits=12, decimal_places=2, default=0)
    percentage = models.DecimalField(_('percentage'), max_digits=5, decimal_places=2, default=0)
    is_percentage = models.BooleanField(_('is percentage'), default=False, help_text=_('If true, amount represents a percentage of basic salary.'))
    is_tax_deductible = models.BooleanField(_('is tax deductible'), default=False)
    is_mandatory = models.BooleanField(_('is mandatory'), default=False, help_text=_('Whether this item is mandatory for all employees'))
    applicable_employment_types = models.JSONField(_('applicable employment types'), default=list, help_text=_('Employment types this item applies to'))
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='payroll_items', verbose_name=_('branch'), null=True, blank=True, help_text=_('Leave blank for company-wide items'))
    deduction_category = models.ForeignKey(DeductionCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='payroll_items', verbose_name=_('deduction category'))
    created_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name='created_payroll_items', verbose_name=_('created by'))
    last_modified_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name='modified_payroll_items', verbose_name=_('last modified by'))

    class Meta:
        verbose_name = _('payroll item')
        verbose_name_plural = _('payroll items')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_item_type_display()})"

class EmployeePayroll(TimestampedModel, SoftDeleteModel):
    """Payroll record for an employee."""
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='payrolls', verbose_name=_('employee'))
    payroll_period = models.ForeignKey(PayrollPeriod, on_delete=models.CASCADE, related_name='employee_payrolls', verbose_name=_('payroll period'))
    rate_structure = models.ForeignKey(RateStructure, on_delete=models.SET_NULL, null=True, related_name='employee_payrolls', verbose_name=_('rate structure'))
    basic_salary = models.DecimalField(_('basic salary'), max_digits=12, decimal_places=2, default=0)
    gross_pay = models.DecimalField(_('gross pay'), max_digits=12, decimal_places=2, default=0)
    total_deductions = models.DecimalField(_('total deductions'), max_digits=12, decimal_places=2, default=0)
    net_pay = models.DecimalField(_('net_pay'), max_digits=12, decimal_places=2, default=0)
    status = models.CharField(_('status'), max_length=20, choices=[
            ('draft', _('Draft')),
            ('calculated', _('Calculated')),
            ('approved', _('Approved')),
            ('paid', _('Paid')),
            ('cancelled', _('Cancelled'))
        ], default='draft')
    payment_date = models.DateField(_('payment date'), null=True, blank=True)
    payment_method = models.CharField(_('payment method'), max_length=20, choices=[
            ('bank_transfer', _('Bank Transfer')),
            ('cash', _('Cash')),
            ('check', _('Check')),
            ('mobile_money', _('Mobile Money')),
            ('other', _('Other'))
        ], default='bank_transfer')
    payment_reference = models.CharField(_('payment reference'), max_length=100, blank=True)
    notes = models.TextField(_('notes'), blank=True)
    created_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name='created_employee_payrolls', verbose_name=_('created by'))
    last_modified_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name='modified_employee_payrolls', verbose_name=_('last modified by'))
    expense = models.OneToOneField(Expense, on_delete=models.SET_NULL, null=True, blank=True, related_name='payroll', verbose_name=_('expense'))

    class Meta:
        verbose_name = _('employee payroll')
        verbose_name_plural = _('employee payrolls')
        ordering = ['-payroll_period__start_date', 'employee__user__email']
        unique_together = ['employee', 'payroll_period']

    def __str__(self):
        return f"{self.employee} - {self.payroll_period}"

    def clean(self):
        """Validate employee payroll."""
        if self.status == 'paid' and not self.payment_date:
            raise ValidationError(_('Payment date is required for paid status.'))
        if self.status == 'paid' and not self.payment_method:
            raise ValidationError(_('Payment method is required for paid status.'))

    def calculate_payroll(self):
        """Calculate payroll amounts based on employee's rate structure."""
        # Get the applicable rate structure
        if self.rate_structure:
            self.basic_salary = self.rate_structure.calculate_rate(employee=self.employee)
        else:
            self.basic_salary = self.employee.current_rate

        # Start with basic salary
        self.gross_pay = self.basic_salary
        self.total_deductions = 0

        # Calculate allowances and bonuses
        for item in PayrollItem.objects.filter(
            item_type__in=['allowance', 'bonus'],
            is_active=True
        ).filter(
            Q(applicable_employment_types__contains=[self.employee.employment_type]) |
            Q(applicable_employment_types=[])
        ).filter(
            Q(branch=self.employee.branch) | Q(branch__isnull=True)
        ):
            if item.is_percentage:
                amount = self.basic_salary * (item.percentage / 100)
            else:
                amount = item.amount
            self.gross_pay += amount

        # Calculate deductions
        for item in PayrollItem.objects.filter(
            item_type__in=['deduction', 'tax'],
            is_active=True
        ).filter(
            Q(applicable_employment_types__contains=[self.employee.employment_type]) |
            Q(applicable_employment_types=[])
        ).filter(
            Q(branch=self.employee.branch) | Q(branch__isnull=True)
        ):
            if item.is_percentage:
                amount = self.basic_salary * (item.percentage / 100)
            else:
                amount = item.amount
            self.total_deductions += amount

        # Calculate net pay
        self.net_pay = self.gross_pay - self.total_deductions

    def mark_as_paid(self, payment_date=None, payment_method=None, payment_reference=None):
        """Mark the payroll as paid."""
        self.status = 'paid'
        self.payment_date = payment_date or timezone.now().date()
        if payment_method:
            self.payment_method = payment_method
        if payment_reference:
            self.payment_reference = payment_reference
        self.save()

    def cancel(self, notes=None):
        """Cancel the payroll."""
        self.status = 'cancelled'
        if notes:
            self.notes = notes
        self.save()

class WorkAssignment(TimestampedModel, SoftDeleteModel):
    """
    Work assignments for all employee types (regular, casual, contract).
    """
    ASSIGNMENT_STATUS = [
        ('scheduled', _('Scheduled')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('cancelled', _('Cancelled')),
        ('no_show', _('No Show')),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='work_assignments', verbose_name=_('employee'))
    assignment_number = models.CharField(_('assignment number'), max_length=20, unique=True, help_text=_('Unique assignment identifier'))
    
    # Work details
    work_date = models.DateField(_('work date'))
    start_time = models.TimeField(_('start time'))
    end_time = models.TimeField(_('end time'), null=True, blank=True)
    expected_hours = models.DecimalField(_('expected hours'), max_digits=5, decimal_places=2)
    actual_hours = models.DecimalField(_('actual hours'), max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Work conditions
    work_location = models.CharField(_('work location'), max_length=200, blank=True)
    work_description = models.TextField(_('work description'))
    special_requirements = models.JSONField(_('special requirements'), default=dict, blank=True)
    
    # Status and tracking
    status = models.CharField(_('status'), max_length=20, choices=ASSIGNMENT_STATUS, default='scheduled')
    check_in_time = models.DateTimeField(_('check in time'), null=True, blank=True)
    check_out_time = models.DateTimeField(_('check out time'), null=True, blank=True)
    
    # Payment calculation
    calculated_rate = models.DecimalField(_('calculated rate'), max_digits=10, decimal_places=2, null=True, blank=True)
    total_payment = models.DecimalField(_('total payment'), max_digits=12, decimal_places=2, null=True, blank=True)
    
    # Approval and notes
    assigned_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name='assigned_work', verbose_name=_('assigned by'))
    approved_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_assignments', verbose_name=_('approved by'))
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('work assignment')
        verbose_name_plural = _('work assignments')
        ordering = ['-work_date', '-start_time']
        unique_together = [['employee', 'work_date', 'start_time']]

    def __str__(self):
        return f"{self.assignment_number} - {self.employee} - {self.work_date}"

    def save(self, *args, **kwargs):
        """Generate assignment number if not provided."""
        if not self.assignment_number:
            self.assignment_number = self.generate_assignment_number()
        super().save(*args, **kwargs)

    def generate_assignment_number(self):
        """Generate unique assignment number."""
        import random
        import string
        
        while True:
            # Format: A-YYYYMMDD-XXXX (e.g., A-20240115-1234)
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = ''.join(random.choices(string.digits, k=4))
            assignment_number = f"A-{date_part}-{random_part}"
            
            if not WorkAssignment.objects.filter(assignment_number=assignment_number).exists():
                return assignment_number

    def check_in(self, check_in_time=None):
        """Record check-in time."""
        self.status = 'in_progress'
        self.check_in_time = check_in_time or timezone.now()
        self.save()

    def check_out(self, check_out_time=None, actual_hours=None):
        """Record check-out time and calculate payment."""
        self.status = 'completed'
        self.check_out_time = check_out_time or timezone.now()
        
        if actual_hours is not None:
            self.actual_hours = actual_hours
        elif self.check_in_time and self.check_out_time:
            # Calculate actual hours from check-in/out times
            duration = self.check_out_time - self.check_in_time
            self.actual_hours = round(duration.total_seconds() / 3600, 2)
        
        # Calculate payment using employee's rate structure
        if self.actual_hours:
            self.total_payment = self.employee.calculate_payment(
                hours_worked=self.actual_hours,
                work_date=self.work_date
            )
        
        self.save()

    def cancel(self, reason=''):
        """Cancel the assignment."""
        self.status = 'cancelled'
        if reason:
            self.notes = f"Cancelled: {reason}\n{self.notes}"
        self.save()

    @property
    def is_overdue(self):
        """Check if assignment is overdue."""
        if self.status in ['completed', 'cancelled', 'no_show']:
            return False
        return timezone.now().date() > self.work_date

    @property
    def duration_hours(self):
        """Calculate actual duration in hours."""
        if not self.check_in_time or not self.check_out_time:
            return 0
        duration = self.check_out_time - self.check_in_time
        return round(duration.total_seconds() / 3600, 2)

class CasualPayment(TimestampedModel, SoftDeleteModel):
    """
    Comprehensive casual payment system with deductions and accounting integration.
    """
    PAYMENT_STATUS = [
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('paid', _('Paid')),
        ('cancelled', _('Cancelled')),
        ('partially_paid', _('Partially Paid')),
    ]

    PAYMENT_FREQUENCY = [
        ('daily', _('Daily')),
        ('weekly', _('Weekly')),
        ('biweekly', _('Bi-weekly')),
        ('monthly', _('Monthly')),
        ('project', _('Project Based')),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('cash', _('Cash')),
        ('bank_transfer', _('Bank Transfer')),
        ('mobile_money', _('Mobile Money')),
        ('check', _('Check')),
    ]

    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='casual_payments', verbose_name=_('employee'))
    payment_number = models.CharField(_('payment number'), max_length=20, unique=True, help_text=_('Unique payment identifier'))
    
    # Payment period
    payment_frequency = models.CharField(_('payment frequency'), max_length=20, choices=PAYMENT_FREQUENCY, default='daily')
    period_start_date = models.DateField(_('period start date'))
    period_end_date = models.DateField(_('period end date'))
    
    # Work details
    total_hours_worked = models.DecimalField(_('total hours worked'), max_digits=8, decimal_places=2, default=0)
    hourly_rate = models.DecimalField(_('hourly rate'), max_digits=10, decimal_places=2, default=0)
    base_amount = models.DecimalField(_('base amount'), max_digits=12, decimal_places=2, default=0)
    
    # Deductions and adjustments
    total_deductions = models.DecimalField(_('total deductions'), max_digits=12, decimal_places=2, default=0)
    deduction_details = models.JSONField(_('deduction details'), default=list, help_text=_('Detailed breakdown of deductions'))
    
    # Final amounts
    gross_amount = models.DecimalField(_('gross amount'), max_digits=12, decimal_places=2, default=0)
    net_amount = models.DecimalField(_('net amount'), max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(_('amount paid'), max_digits=12, decimal_places=2, default=0)
    amount_held = models.DecimalField(_('amount held'), max_digits=12, decimal_places=2, default=0)
    
    # Status and payment
    status = models.CharField(_('status'), max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_date = models.DateField(_('payment date'), null=True, blank=True)
    payment_method = models.CharField(_('payment method'), max_length=20, choices=PAYMENT_METHOD_CHOICES, default='cash')
    payment_reference = models.CharField(_('payment reference'), max_length=100, blank=True)
    
    # Approval workflow
    created_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, related_name='created_casual_payments', verbose_name=_('created by'))
    approved_by = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_casual_payments', verbose_name=_('approved by'))
    approved_date = models.DateTimeField(_('approved date'), null=True, blank=True)
    
    # Accounting integration
    expense = models.OneToOneField(Expense, on_delete=models.SET_NULL, null=True, blank=True, related_name='casual_payment', verbose_name=_('expense'))
    deduction_revenue = models.OneToOneField(Revenue, on_delete=models.SET_NULL, null=True, blank=True, related_name='casual_deduction', verbose_name=_('deduction revenue'))
    
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('casual payment')
        verbose_name_plural = _('casual payments')
        ordering = ['-period_start_date', '-created_at']

    def __str__(self):
        return f"{self.payment_number} - {self.employee} - {self.period_start_date} to {self.period_end_date}"

    def save(self, *args, **kwargs):
        """Generate payment number if not provided."""
        if not self.payment_number:
            self.payment_number = self.generate_payment_number()
        super().save(*args, **kwargs)

    def generate_payment_number(self):
        """Generate unique payment number."""
        import random
        import string
        
        while True:
            # Format: CP-YYYYMMDD-XXXX (e.g., CP-20240115-1234)
            date_part = timezone.now().strftime('%Y%m%d')
            random_part = ''.join(random.choices(string.digits, k=4))
            payment_number = f"CP-{date_part}-{random_part}"
            
            if not CasualPayment.objects.filter(payment_number=payment_number).exists():
                return payment_number

    def calculate_payment(self):
        """Calculate all payment components."""
        # Base amount
        self.base_amount = self.total_hours_worked * self.hourly_rate
        
        # Calculate gross amount (base + bonuses)
        self.gross_amount = self.base_amount
        
        # Apply deductions
        self.net_amount = self.gross_amount - self.total_deductions
        
        # Calculate amounts
        self.amount_paid = min(self.net_amount, self.amount_paid)
        self.amount_held = self.net_amount - self.amount_paid
        
        return self.net_amount

    def add_deduction(self, category, amount, reason, description=''):
        """Add a deduction to the payment."""
        deduction = {
            'category': category,
            'amount': float(amount),
            'reason': reason,
            'description': description,
            'date_added': timezone.now().isoformat()
        }
        
        self.deduction_details.append(deduction)
        self.total_deductions += amount
        self.calculate_payment()
        self.save()

    def approve(self, approved_by):
        """Approve the payment."""
        self.status = 'approved'
        self.approved_by = approved_by
        self.approved_date = timezone.now()
        self.save()

    def mark_as_paid(self, payment_date=None, payment_method=None, payment_reference=None, partial_amount=None):
        """Mark the payment as paid (full or partial)."""
        if partial_amount:
            self.amount_paid = partial_amount
            self.amount_held = self.net_amount - partial_amount
            self.status = 'partially_paid'
        else:
            self.amount_paid = self.net_amount
            self.amount_held = 0
            self.status = 'paid'
        
        self.payment_date = payment_date or timezone.now().date()
        if payment_method:
            self.payment_method = payment_method
        if payment_reference:
            self.payment_reference = payment_reference
        
        # Create accounting entries
        self.create_accounting_entries()
        self.save()

    def create_accounting_entries(self):
        """Create accounting entries for payment and deductions."""
        from apps.accounting.models import ExpenseCategory, RevenueCategory
        
        # Create expense entry for payment
        if not self.expense and self.amount_paid > 0:
            expense_category, _ = ExpenseCategory.objects.get_or_create(
                name='Casual Worker Payments',
                defaults={'description': 'Payments to casual workers'}
            )
            
            self.expense = Expense.objects.create(
                expense_type='casual_payment',
                category=expense_category,
                amount=self.amount_paid,
                expense_date=self.payment_date or timezone.now().date(),
                description=f"Casual payment for {self.employee} - {self.period_start_date} to {self.period_end_date}",
                payment_method=self.payment_method,
                payment_reference=self.payment_reference,
                created_by=self.created_by
            )

        # Create revenue entry for deductions (if any)
        if not self.deduction_revenue and self.total_deductions > 0:
            revenue_category, _ = RevenueCategory.objects.get_or_create(
                name='Employee Deductions',
                defaults={'description': 'Deductions from employee payments'}
            )
            
            self.deduction_revenue = Revenue.objects.create(
                revenue_type='employee_deduction',
                category=revenue_category,
                amount=self.total_deductions,
                revenue_date=self.payment_date or timezone.now().date(),
                description=f"Deductions from {self.employee} - {self.period_start_date} to {self.period_end_date}",
                payment_method=self.payment_method,
                payment_reference=self.payment_reference,
                created_by=self.created_by
            )

    def cancel(self, reason=''):
        """Cancel the payment."""
        self.status = 'cancelled'
        if reason:
            self.notes = f"Cancelled: {reason}\n{self.notes}"
        self.save()

    @property
    def is_partially_paid(self):
        """Check if payment is partially paid."""
        return self.status == 'partially_paid' or (self.amount_paid > 0 and self.amount_paid < self.net_amount)

    @property
    def outstanding_amount(self):
        """Get outstanding amount."""
        return self.net_amount - self.amount_paid

