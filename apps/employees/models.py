from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from datetime import timedelta, datetime
from django.contrib.contenttypes.fields import GenericRelation
from apps.base.models import TimestampedModel, SoftDeleteModel
from apps.accounts.models import Role
from apps.branches.models import Branch
from decimal import Decimal, ROUND_HALF_UP

User = get_user_model()


class Department(TimestampedModel, SoftDeleteModel):
    """
    Department model represents different departments in the organization.
    """
    name = models.CharField(_('department name'),max_length=100,unique=True,help_text=_('The name of the department'))
    code = models.CharField(_('department code'),max_length=10,unique=True,help_text=_('Short code for the department'))
    description = models.TextField(_('description'),blank=True,help_text=_('Detailed description of the department'))
    parent_department = models.ForeignKey('self',on_delete=models.SET_NULL,null=True,blank=True,related_name='sub_departments',verbose_name=_('parent department'),help_text=_('The parent department if this is a sub-department'))
    is_active = models.BooleanField(_('is active'),default=True,help_text=_('Whether this department is currently active'))

    class Meta:
        ordering = ['name']
        verbose_name = _('department')
        verbose_name_plural = _('departments')

    def __str__(self):
        return self.name

    @property
    def employee_count(self):
        """Return the number of active employees in this department."""
        return self.employees.filter(is_active=True).count()

    @property
    def sub_department_count(self):
        """Return the number of active sub-departments."""
        return self.sub_departments.filter(is_active=True).count()

    def get_hierarchy(self, include_self=True):
        """
        Return a list representing the department hierarchy.
        """
        hierarchy = []
        if include_self:
            hierarchy.append(self)
        
        parent = self.parent_department
        while parent:
            hierarchy.append(parent)
            parent = parent.parent_department
            
        return hierarchy[::-1]  # Return in top-down order

    def get_all_sub_departments(self, include_self=True):
        """
        Return a queryset of all sub-departments (recursively).
        """
        def get_children(department):
            children = department.sub_departments.filter(is_active=True)
            result = list(children)
            for child in children:
                result.extend(get_children(child))
            return result
        
        result = []
        if include_self:
            result.append(self)
        
        result.extend(get_children(self))
        return result

class WorkCategory(TimestampedModel, SoftDeleteModel):
    """
    Unified work categories for all employee types (regular, casual, contract).
    """
    name = models.CharField(_('category name'), max_length=100, unique=True)
    code = models.CharField(_('category code'), max_length=20, unique=True)
    description = models.TextField(_('description'), blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='work_categories', verbose_name=_('department'))
    is_active = models.BooleanField(_('is active'), default=True)
    applicable_employment_types = models.JSONField(_('applicable employment types'), default=list, help_text=_('Employment types that can use this category'))
    required_skills = models.JSONField(_('required skills'), default=list, blank=True)
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        ordering = ['name']
        verbose_name = _('work category')
        verbose_name_plural = _('work categories')

    def __str__(self):
        return f"{self.name} ({self.code})"

class RateStructure(TimestampedModel, SoftDeleteModel):
    """
    Unified rate structure for all employee types with flexible calculation rules.
    """
    RATE_TYPE_CHOICES = [
        ('monthly', _('Monthly Salary')),
        ('hourly', _('Hourly Rate')),
        ('daily', _('Daily Rate')),
        ('weekly', _('Weekly Rate')),
        ('project', _('Project Based')),
        ('piece', _('Piece Rate')),
    ]

    name = models.CharField(_('rate name'), max_length=100)
    work_category = models.ForeignKey(WorkCategory, on_delete=models.CASCADE, related_name='rate_structures', verbose_name=_('work category'))
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='rate_structures', verbose_name=_('branch'), null=True, blank=True, help_text=_('Leave blank for company-wide rates'))
    rate_type = models.CharField(_('rate type'), max_length=20, choices=RATE_TYPE_CHOICES, default='monthly')
    base_amount = models.DecimalField(_('base amount'), max_digits=12, decimal_places=2, help_text=_('Base salary/rate amount'))
    currency = models.CharField(_('currency'), max_length=3, default='KES')
    
    # Flexible calculation rules
    calculation_rules = models.JSONField(_('calculation rules'), default=dict, help_text=_('JSON rules for rate calculation'))
    
    # Applicable employment types and conditions
    applicable_employment_types = models.JSONField(_('applicable employment types'), default=list)
    minimum_experience_years = models.PositiveIntegerField(_('minimum experience years'), default=0)
    maximum_experience_years = models.PositiveIntegerField(_('maximum experience years'), null=True, blank=True)
    
    # Time period
    effective_from = models.DateField(_('effective from'))
    effective_to = models.DateField(_('effective to'), null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(_('is active'), default=True)
    is_default = models.BooleanField(_('is default'), default=False)
    
    # Metadata
    created_by = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, related_name='created_rate_structures', verbose_name=_('created by'))
    last_modified_by = models.ForeignKey('Employee', on_delete=models.SET_NULL, null=True, related_name='modified_rate_structures', verbose_name=_('last modified by'))
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        ordering = ['work_category__name', '-effective_from']
        verbose_name = _('rate structure')
        verbose_name_plural = _('rate structures')
        unique_together = [['work_category', 'branch', 'rate_type', 'effective_from']]

    def __str__(self):
        branch_name = f" - {self.branch.name}" if self.branch else " - Company-wide"
        return f"{self.work_category.name}{branch_name} - {self.get_rate_type_display()} - {self.base_amount}"

    def clean(self):
        """Validate rate structure."""
        if self.effective_to and self.effective_from and self.effective_to < self.effective_from:
            raise ValidationError({
                'effective_to': _('Effective to date cannot be before effective from date.')
            })
        
        if self.is_default:
            # Ensure only one default rate per category, branch, and type
            if self.__class__.objects.filter(
                work_category=self.work_category,
                branch=self.branch,
                rate_type=self.rate_type,
                is_default=True
            ).exclude(pk=self.pk).exists():
                raise ValidationError(
                    _('Only one default rate can exist per work category, branch, and rate type.')
                )

    def calculate_rate(self, employee=None, work_date=None, hours_worked=0, **kwargs):
        """
        Calculate the actual rate based on employee, date, and work conditions.
        """
        if not self.is_effective_on_date(work_date or timezone.now().date()):
            return 0
        
        rate = self.base_amount
        
        # Apply calculation rules
        rules = self.calculation_rules or {}
        
        # Experience-based adjustments
        if employee and 'experience_multiplier' in rules:
            experience_years = employee.tenure_years or 0
            if experience_years > 0:
                multiplier = rules['experience_multiplier'].get('rate', 0)
                rate *= (1 + (experience_years * multiplier / 100))
        
        # Skill-based adjustments
        if employee and 'skill_bonuses' in rules and employee.skills:
            for skill in employee.skills:
                if skill in rules['skill_bonuses']:
                    rate *= (1 + rules['skill_bonuses'][skill] / 100)
        
        # Time-based adjustments
        if work_date:
            # Weekend bonus
            if work_date.weekday() >= 5 and 'weekend_bonus' in rules:
                rate *= (1 + rules['weekend_bonus'] / 100)
            
            # Holiday bonus (simplified - would need holiday calendar)
            if 'holiday_bonus' in rules:
                # Check if it's a holiday (simplified)
                pass
        
        # Overtime adjustments
        if 'overtime_threshold' in rules and hours_worked > rules['overtime_threshold']:
            overtime_hours = hours_worked - rules['overtime_threshold']
            overtime_rate = rules.get('overtime_multiplier', 1.5)
            rate = (rate * rules['overtime_threshold']) + (rate * overtime_rate * overtime_hours)
            return rate
        
        return round(rate, 2)

    def is_effective_on_date(self, date):
        """Check if this rate is effective on the given date."""
        if date < self.effective_from:
            return False
        if self.effective_to and date > self.effective_to:
            return False
        return True

    def is_applicable_to_employee(self, employee):
        """Check if this rate structure is applicable to the employee."""
        if employee.employment_type not in self.applicable_employment_types:
            return False
        
        if employee.tenure_years < self.minimum_experience_years:
            return False
        
        if self.maximum_experience_years and employee.tenure_years > self.maximum_experience_years:
            return False
        
        # Check branch compatibility
        if self.branch and employee.branch != self.branch:
            return False
        
        return True

class Employee(TimestampedModel, SoftDeleteModel):
    """
    Employee model extends the default User model with additional employee-specific fields.
    """
    GENDER_CHOICES = [
        ('M', _('Male')),
        ('F', _('Female')),
        ('O', _('Other')),
        ('N', _('Prefer not to say')),
    ]

    EMPLOYMENT_TYPE_CHOICES = [
        ('FT', _('Full Time')),
        ('PT', _('Part Time')),
        ('TEMP', _('Temporary')),
        ('SEA', _('Seasonal')),
        ('INT', _('Intern')),
        ('CASUAL', _('Casual Worker')),
        ('CONTRACT', _('Contract Worker')),
    ]

    user = models.OneToOneField(User,on_delete=models.CASCADE,related_name='employee_profile',verbose_name=_('user account'))
    employee_id = models.CharField(_('employee ID'),max_length=20,unique=True,help_text=_('Unique identifier for the employee'))
    date_of_birth = models.DateField(_('date of birth'),null=True,blank=True,help_text=_('Employee\'s date of birth'))
    gender = models.CharField(_('gender'),max_length=1,choices=GENDER_CHOICES,blank=True,help_text=_('Employee\'s gender'))
    phone_number = models.CharField(_('phone number'),max_length=20,blank=True,help_text=_('Employee\'s contact number'))
    
    # Address fields (using generic relation to the global Address model)
    addresses = GenericRelation(
        'base.Address',
        content_type_field='content_type',
        object_id_field='object_id',
        related_query_name='employee',
        verbose_name=_('addresses')
    )
    
    emergency_contact_name = models.CharField(_('emergency contact name'),max_length=100,blank=True,help_text=_('Name of emergency contact person'))
    emergency_contact_phone = models.CharField(_('emergency contact phone'),max_length=20,blank=True,help_text=_('Emergency contact phone number'))
    emergency_contact_relation = models.CharField(_('emergency contact relation'),max_length=50,blank=True,help_text=_('Relationship to employee'))
    
    # Branch and organizational structure
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees', verbose_name=_('branch'))
    department = models.ForeignKey(Department,on_delete=models.SET_NULL,null=True,blank=True,related_name='employees',verbose_name=_('department'))
    role = models.ForeignKey(Role,on_delete=models.SET_NULL,null=True,blank=True,related_name='employees',verbose_name=_('role'))
    work_category = models.ForeignKey(WorkCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees', verbose_name=_('work category'))
    hire_date = models.DateField(_('hire date'),null=True,blank=True,help_text=_('Date when employee was hired'))
    employment_type = models.CharField(_('employment type'),max_length=10,choices=EMPLOYMENT_TYPE_CHOICES,default='FT',help_text=_('Type of employment'))
    supervisor = models.ForeignKey('self',on_delete=models.SET_NULL,null=True,blank=True,related_name='subordinates',verbose_name=_('manager'))
    salary = models.DecimalField(_('salary'),max_digits=12,decimal_places=2,default=0,help_text=_('Monthly salary in local currency'))
    
    # Flexible rate management
    current_rate_structure = models.ForeignKey(RateStructure, on_delete=models.SET_NULL, null=True, blank=True, related_name='employees', verbose_name=_('current rate structure'))
    custom_rate = models.DecimalField(_('custom rate'), max_digits=12, decimal_places=2, null=True, blank=True, help_text=_('Custom rate override'))
    
    # Casual/Contract specific fields
    contract_start_date = models.DateField(_('contract start date'), null=True, blank=True)
    contract_end_date = models.DateField(_('contract end date'), null=True, blank=True)
    skills = models.JSONField(_('skills'), default=list, blank=True, help_text=_('Employee skills for rate calculation'))
    availability_schedule = models.JSONField(_('availability schedule'), default=dict, blank=True, help_text=_('Availability schedule'))
    
    is_active = models.BooleanField(_('is active'),default=True,help_text=_('Designates whether this employee is currently active'))
    bank_name = models.CharField(_('bank name'),max_length=100,blank=True,help_text=_('Name of the bank for salary payments'))
    bank_account_number = models.CharField(_('bank account number'),max_length=50,blank=True,help_text=_('Bank account number for salary payments'))
    bank_branch = models.CharField(_('bank branch'),max_length=100,blank=True,help_text=_('Branch of the bank'))
    tax_id = models.CharField(_('tax ID'),max_length=50,blank=True,help_text=_('Tax identification number'))
    national_id = models.CharField(_('national ID'),max_length=50,blank=True,help_text=_('National identification number'))
    shif_number = models.CharField(_('SHIF number'),max_length=50,blank=True,help_text=_('National Hospital Insurance Fund number'))
    nhif_number = models.CharField(_('NHIF number'),max_length=50,blank=True,help_text=_('National Hospital Insurance Fund number'))
    nssf_number = models.CharField(_('NSSF number'),max_length=50,blank=True,help_text=_('National Social Security Fund number'))
    kra_pin = models.CharField(_('KRA PIN'),max_length=50,blank=True,help_text=_('Kenya Revenue Authority Personal Identification Number'))
    notes = models.TextField(_('notes'),blank=True,help_text=_('Additional notes about the employee'))

    class Meta:
        ordering = ['user__last_name', 'user__first_name']
        verbose_name = _('employee')
        verbose_name_plural = _('employees')
        permissions = [
            ('view_sensitive_info', 'Can view sensitive employee information'),
            ('manage_employees', 'Can add, edit, and delete employees'),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id})"

    @property
    def full_name(self):
        """Return the employee's full name."""
        return self.user.get_full_name()

    @property
    def email(self):
        """Return the employee's email address."""
        return self.user.email

    @property
    def age(self):
        """Calculate and return the employee's age."""
        if not self.date_of_birth:
            return None
        today = timezone.now().date()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def tenure_years(self):
        """Calculate and return the employee's tenure in years."""
        if not self.hire_date:
            return 0
        today = timezone.now().date()
        return today.year - self.hire_date.year - (
            (today.month, today.day) < (self.hire_date.month, self.hire_date.day)
        )

    @property
    def tenure_months(self):
        """Calculate and return the employee's tenure in months."""
        if not self.hire_date:
            return 0
        today = timezone.now().date()
        years = today.year - self.hire_date.year
        months = today.month - self.hire_date.month
        return years * 12 + months

    @property
    def is_casual_worker(self):
        """Check if employee is a casual worker."""
        return self.employment_type in ['CASUAL', 'CONTRACT', 'TEMP']

    @property
    def current_rate(self):
        """Get the current applicable rate for the employee."""
        if self.custom_rate:
            return self.custom_rate
        
        if self.current_rate_structure:
            return self.current_rate_structure.calculate_rate(employee=self)
        
        # Fallback to role-based salary
        if self.role and self.role.base_salary:
            return self.role.base_salary
        
        return self.salary

    def get_applicable_rate_structure(self, work_date=None):
        """Get the applicable rate structure for this employee."""
        if self.current_rate_structure:
            return self.current_rate_structure
        
        # Find applicable rate structure based on work category and branch
        if self.work_category:
            queryset = RateStructure.objects.filter(
                work_category=self.work_category,
                is_active=True
            )
            
            # Try branch-specific rate first
            if self.branch:
                branch_rate = queryset.filter(branch=self.branch).first()
                if branch_rate:
                    return branch_rate
            
            # Fallback to company-wide rate
            company_rate = queryset.filter(branch__isnull=True).first()
            if company_rate:
                return company_rate
        
        return None

    def calculate_payment(self, hours_worked=0, work_date=None, **kwargs):
        """
        Calculate payment for work done based on employee's rate structure.
        """
        rate_structure = self.get_applicable_rate_structure(work_date)
        
        if rate_structure:
            return rate_structure.calculate_rate(
                employee=self,
                work_date=work_date,
                hours_worked=hours_worked,
                **kwargs
            )
        
        # Fallback calculation
        if self.employment_type in ['CASUAL', 'CONTRACT', 'TEMP']:
            # For casual workers, use hourly rate
            hourly_rate = self.current_rate / 160  # Assuming 160 hours per month
            return hourly_rate * hours_worked
        else:
            # For regular employees, return monthly salary
            return self.current_rate

    def get_absolute_url(self):
        """Return the URL to this employee's detail view."""
        from django.urls import reverse
        return reverse('employees:employee-detail', kwargs={'pk': self.pk})

    def get_reporting_line(self):
        """
        Return a list representing the reporting line from this employee up to the top.
        """
        reporting_line = []
        current = self.supervisor
        while current:
            reporting_line.append(current)
            current = current.supervisor
        return reporting_line

    def get_subordinates(self, include_indirect=True):
        """
        Get all employees who report to this employee.
        If include_indirect is True, include all levels of subordinates.
        """
        if include_indirect:
            # Get all subordinates recursively
            def get_all_subordinates(employee):
                direct_subs = list(employee.subordinates.all())
                all_subs = direct_subs.copy()
                for sub in direct_subs:
                    all_subs.extend(get_all_subordinates(sub))
                return all_subs

            return get_all_subordinates(self)
        return self.subordinates.all()

    @property
    def primary_address(self):
        """Return the primary address if it exists, or None."""
        return self.addresses.filter(is_primary=True).first()

    def clean(self):
        """
        Custom validation for the Employee model.
        """
        super().clean()

        # Ensure supervisor has a management role (ADMIN or MANAGER)
        if self.supervisor and self.supervisor.role:
            if self.supervisor.role.name not in [Role.ADMIN, Role.MANAGER]:
                raise ValidationError({
                    'supervisor': _('Manager must have a management role (Admin or Manager).')
                })
            
        # Validate that salary is within role's salary range if role is set
        if self.role:
            message = None
            
            if self.salary < self.role.base_salary:
                original_salary = self.salary
                self.salary = self.role.base_salary
                message = _(f'Salary {original_salary} was adjusted to base salary {self.role.base_salary} for this role.')
                        
            if self.role.max_salary and self.salary > self.role.max_salary:
                original_salary = self.salary
                self.salary = self.role.max_salary
                message = _(f'Salary {original_salary} was adjusted to maximum salary {self.role.max_salary} for this role.')
            
            if message:
                return {
                    'message': message,
                    'adjusted_salary': self.salary
                }

    def save(self, *args, **kwargs):
        # Ensure salary is always rounded to 2 decimal places before saving
        if self.salary is not None:
            self.salary = Decimal(self.salary).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        # If salary is updated, also update the current_rate_structure if it exists
        if self.salary and self.current_rate_structure and self.current_rate_structure.base_amount != self.salary:
            self.current_rate_structure.base_amount = self.salary

        self.full_clean()
        super().save(*args, **kwargs)

class Attendance(TimestampedModel, SoftDeleteModel):
    """
    Model to track employee attendance (check-in/check-out).
    """
    STATUS_CHOICES = [
        ('PRESENT', _('Present')),
        ('LATE', _('Late Arrival')),
        ('HALF_DAY', _('Half Day')),
        ('ABSENT', _('Absent')),
        ('LEAVE', _('On Leave')),
        ('HOLIDAY', _('Public Holiday')),
        ('WEEKEND', _('Weekend')),
    ]

    employee = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name=_('employee')
    )
    date = models.DateField(_('date'), default=timezone.now)
    check_in = models.DateTimeField(_('check in'), null=True, blank=True)
    check_out = models.DateTimeField(_('check out'), null=True, blank=True)
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='PRESENT'
    )
    notes = models.TextField(_('notes'), blank=True)
    is_approved = models.BooleanField(_('is approved'), default=True)
    approved_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_attendances',
        verbose_name=_('approved by')
    )
    ip_address = models.GenericIPAddressField(_('IP address'), null=True, blank=True)
    location = models.CharField(_('location'), max_length=255, blank=True)
    device_info = models.JSONField(_('device info'), null=True, blank=True)

    class Meta:
        verbose_name = _('attendance')
        verbose_name_plural = _('attendances')
        ordering = ['-date', 'employee__user__last_name']
        unique_together = ['employee', 'date']
        indexes = [
            models.Index(fields=['employee', 'date']),
            models.Index(fields=['date', 'status']),
        ]

    def __str__(self):
        return f"{self.employee} - {self.date} - {self.get_status_display()}"

    @property
    def working_hours(self):
        """Calculate working hours for this attendance record."""
        if not self.check_in or not self.check_out:
            return 0
        
        duration = self.check_out - self.check_in
        return round(duration.total_seconds() / 3600, 2)

    @property
    def is_checked_in(self):
        """Check if employee is currently checked in."""
        return bool(self.check_in and not self.check_out)

    def clean(self):
        """Validate attendance record."""
        super().clean()
        
        # Ensure check-out is after check-in
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValidationError({
                'check_out': _('Check-out time must be after check-in time.')
            })
        
        # Ensure only one attendance record per employee per day
        if self.pk is None:  # Only for new records
            if Attendance.objects.filter(employee=self.employee, date=self.date).exists():
                raise ValidationError({
                    'date': _('Attendance record already exists for this employee on this date.')
                })

    def save(self, *args, **kwargs):
        """Override save to handle automatic status updates."""
        # Auto-update status based on check-in/out times
        if self.check_in and self.check_out:
            # Calculate if late arrival (after 9 AM)
            late_threshold = self.check_in.replace(hour=9, minute=0, second=0, microsecond=0)
            if self.check_in > late_threshold:
                self.status = 'LATE'
            else:
                self.status = 'PRESENT'
        
        super().save(*args, **kwargs)

class LeaveType(TimestampedModel, SoftDeleteModel):
    """
    Different types of leave available in the organization.
    """
    LEAVE_CATEGORY_CHOICES = [
        ('PAID', _('Paid Leave')),
        ('UNPAID', _('Unpaid Leave')),
        ('SICK', _('Sick Leave')),
        ('MATERNITY', _('Maternity Leave')),
        ('PATERNITY', _('Paternity Leave')),
        ('COMPASSIONATE', _('Compassionate Leave')),
        ('BEREAVEMENT', _('Bereavement Leave')),
        ('STUDY', _('Study Leave')),
        ('SABBATICAL', _('Sabbatical Leave')),
        ('OTHER', _('Other')),
    ]

    name = models.CharField(_('leave type name'), max_length=100)
    category = models.CharField(_('leave category'), max_length=20, choices=LEAVE_CATEGORY_CHOICES, default='PAID')
    description = models.TextField(_('description'), blank=True)
    
    # Leave allocation rules
    default_days_per_year = models.PositiveIntegerField(_('default days per year'), default=21)
    max_days_per_request = models.PositiveIntegerField(_('maximum days per request'), null=True, blank=True)
    min_days_notice = models.PositiveIntegerField(_('minimum days notice'), default=7)
    max_consecutive_days = models.PositiveIntegerField(_('maximum consecutive days'), null=True, blank=True)
    
    # Eligibility rules
    requires_approval = models.BooleanField(_('requires approval'), default=True)
    applicable_employment_types = models.JSONField(_('applicable employment types'), default=list)
    minimum_tenure_months = models.PositiveIntegerField(_('minimum tenure months'), default=0)
    
    # Payroll impact
    is_paid = models.BooleanField(_('is paid leave'), default=True)
    pay_percentage = models.DecimalField(_('pay percentage'), max_digits=5, decimal_places=2, default=100.00, help_text=_('Percentage of salary paid during leave'))
    
    # Status
    is_active = models.BooleanField(_('is active'), default=True)
    is_default = models.BooleanField(_('is default'), default=False)
    
    # Branch specific
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='leave_types', verbose_name=_('branch'), null=True, blank=True, help_text=_('Leave blank for company-wide leave types'))

    class Meta:
        verbose_name = _('leave type')
        verbose_name_plural = _('leave types')
        ordering = ['name']
        unique_together = ['name', 'branch']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def is_applicable_to_employee(self, employee):
        """Check if this leave type is applicable to the employee."""
        if employee.employment_type not in self.applicable_employment_types:
            return False
        
        if employee.tenure_months < self.minimum_tenure_months:
            return False
        
        # Check branch compatibility
        if self.branch and employee.branch != self.branch:
            return False
        
        return True

    def get_available_days(self, employee, year=None):
        """Get available leave days for an employee in a given year."""
        if not year:
            year = timezone.now().year
        
        # Get leave balance for this type and year
        balance = LeaveBalance.objects.filter(
            employee=employee,
            leave_type=self,
            year=year
        ).first()
        
        if balance:
            return balance.available_days
        
        # Return default if no balance record exists
        return self.default_days_per_year

class LeaveBalance(TimestampedModel, SoftDeleteModel):
    """
    Track leave balance for each employee by leave type and year.
    """
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_balances', verbose_name=_('employee'))
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='leave_balances', verbose_name=_('leave type'))
    year = models.PositiveIntegerField(_('year'))
    
    # Balance tracking
    allocated_days = models.PositiveIntegerField(_('allocated days'), default=0)
    used_days = models.PositiveIntegerField(_('used days'), default=0)
    carried_over_days = models.PositiveIntegerField(_('carried over days'), default=0)
    adjusted_days = models.DecimalField(_('adjusted days'), max_digits=6, decimal_places=2, default=0, help_text=_('Manual adjustments'))
    
    # Notes
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('leave balance')
        verbose_name_plural = _('leave balances')
        ordering = ['-year', 'leave_type__name']
        unique_together = ['employee', 'leave_type', 'year']
        indexes = [
            models.Index(fields=['employee', 'year']),
            models.Index(fields=['leave_type', 'year']),
        ]

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.year})"

    @property
    def available_days(self):
        """Calculate available leave days."""
        return max(0, self.allocated_days + self.carried_over_days + self.adjusted_days - self.used_days)

    @property
    def total_days(self):
        """Calculate total allocated days."""
        return self.allocated_days + self.carried_over_days + self.adjusted_days

    def allocate_days(self, days, notes=''):
        """Allocate additional days."""
        self.allocated_days += days
        if notes:
            self.notes += f"\nAllocated {days} days: {notes}"
        self.save()

    def use_days(self, days, notes=''):
        """Use leave days."""
        if days > self.available_days:
            raise ValidationError(f"Insufficient leave balance. Available: {self.available_days}, Requested: {days}")
        
        self.used_days += days
        if notes:
            self.notes += f"\nUsed {days} days: {notes}"
        self.save()

    def adjust_days(self, days, notes=''):
        """Manually adjust days (positive or negative)."""
        self.adjusted_days += days
        if notes:
            self.notes += f"\nAdjusted {days} days: {notes}"
        self.save()

    def carry_over_to_next_year(self, max_carry_over=None):
        """Carry over unused days to next year."""
        unused_days = self.available_days
        
        if max_carry_over:
            unused_days = min(unused_days, max_carry_over)
        
        if unused_days > 0:
            next_year_balance, created = LeaveBalance.objects.get_or_create(
                employee=self.employee,
                leave_type=self.leave_type,
                year=self.year + 1,
                defaults={
                    'allocated_days': 0,
                    'carried_over_days': unused_days
                }
            )
            
            if not created:
                next_year_balance.carried_over_days += unused_days
                next_year_balance.save()
            
            self.notes += f"\nCarried over {unused_days} days to {self.year + 1}"
            self.save()

class LeaveRequest(TimestampedModel, SoftDeleteModel):
    """
    Employee leave requests with approval workflow.
    """
    STATUS_CHOICES = [
        ('DRAFT', _('Draft')),
        ('PENDING', _('Pending')),
        ('APPROVED', _('Approved')),
        ('REJECTED', _('Rejected')),
        ('CANCELLED', _('Cancelled')),
        ('IN_PROGRESS', _('In Progress')),
        ('COMPLETED', _('Completed')),
    ]

    PRIORITY_CHOICES = [
        ('LOW', _('Low')),
        ('NORMAL', _('Normal')),
        ('HIGH', _('High')),
        ('URGENT', _('Urgent')),
    ]

    # Basic information
    request_number = models.CharField(_('request number'), max_length=20, unique=True, help_text=_('Unique leave request identifier'))
    employee = models.ForeignKey(Employee, on_delete=models.CASCADE, related_name='leave_requests', verbose_name=_('employee'))
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name='leave_requests', verbose_name=_('leave type'))
    
    # Leave details
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'))
    start_half_day = models.BooleanField(_('start half day'), default=False, help_text=_('Leave starts in the afternoon'))
    end_half_day = models.BooleanField(_('end half day'), default=False, help_text=_('Leave ends in the morning'))
    
    # Calculated fields
    total_days = models.DecimalField(_('total days'), max_digits=5, decimal_places=2, null=True, blank=True)
    
    # Request details
    reason = models.TextField(_('reason'), blank=True)
    priority = models.CharField(_('priority'), max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    
    # Approval workflow
    requires_approval = models.BooleanField(_('requires approval'), default=True)
    approved_by = models.ForeignKey(
        Employee,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leave_requests',
        verbose_name=_('approved by')
    )
    approved_on = models.DateTimeField(_('approved on'), null=True, blank=True)
    rejection_reason = models.TextField(_('rejection reason'), blank=True)
    
    # Emergency contact
    emergency_contact_name = models.CharField(_('emergency contact name'), max_length=100, blank=True)
    emergency_contact_phone = models.CharField(_('emergency contact phone'), max_length=20, blank=True)
    emergency_contact_relation = models.CharField(_('emergency contact relation'), max_length=50, blank=True)
    
    # Additional information
    destination = models.CharField(_('destination'), max_length=200, blank=True)
    contact_number_while_away = models.CharField(_('contact number while away'), max_length=20, blank=True)
    handover_notes = models.TextField(_('handover notes'), blank=True)
    
    # Documents
    supporting_documents = models.JSONField(_('supporting documents'), default=list, blank=True, help_text=_('List of document URLs'))
    
    # Notes
    notes = models.TextField(_('notes'), blank=True)

    class Meta:
        verbose_name = _('leave request')
        verbose_name_plural = _('leave requests')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['employee', 'status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status', 'priority']),
        ]

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.start_date} to {self.end_date})"

    def save(self, *args, **kwargs):
        # Generate request number if not provided
        if not self.request_number:
            self.request_number = self.generate_request_number()
        
        # Calculate total days if not provided
        if not self.total_days:
            self.total_days = self.calculate_total_days()
        
        # Set requires_approval based on leave type
        if self.leave_type:
            self.requires_approval = self.leave_type.requires_approval
        
        super().save(*args, **kwargs)

    def generate_request_number(self):
        """Generate unique request number."""
        year = timezone.now().year
        count = LeaveRequest.objects.filter(
            created_at__year=year
        ).count() + 1
        return f"LR{year}{count:04d}"

    def calculate_total_days(self):
        """Calculate total leave days excluding weekends and holidays."""
        if not self.start_date or not self.end_date:
            return 0
        
        total_days = 0
        current_date = self.start_date
        
        while current_date <= self.end_date:
            # Skip weekends (Saturday=5, Sunday=6)
            if current_date.weekday() < 5:
                total_days += 1
            current_date += timedelta(days=1)
        
        # Adjust for half days
        if self.start_half_day:
            total_days -= 0.5
        if self.end_half_day:
            total_days -= 0.5
        
        return max(0, total_days)

    def can_approve(self, approver):
        """Check if the approver can approve this request."""
        # Employee cannot approve their own request
        if approver == self.employee:
            return False
        
        # Check if approver is supervisor or has approval permissions
        if approver == self.employee.supervisor:
            return True
        
        # Check for HR/Admin permissions
        if approver.role and approver.role.name in ['HR_MANAGER', 'ADMIN']:
            return True
        
        return False

    def approve(self, approver, notes=''):
        """Approve the leave request."""
        if not self.can_approve(approver):
            raise ValidationError("You don't have permission to approve this request")
        
        if self.status != 'PENDING':
            raise ValidationError("Only pending requests can be approved")
        
        # Check leave balance
        available_days = self.leave_type.get_available_days(self.employee, self.start_date.year)
        if self.total_days > available_days:
            raise ValidationError(f"Insufficient leave balance. Available: {available_days}, Requested: {self.total_days}")
        
        self.status = 'APPROVED'
        self.approved_by = approver
        self.approved_on = timezone.now()
        if notes:
            self.notes += f"\nApproved by {approver.full_name}: {notes}"
        self.save()
        
        # Update leave balance
        self.update_leave_balance()

    def reject(self, approver, reason):
        """Reject the leave request."""
        if not self.can_approve(approver):
            raise ValidationError("You don't have permission to reject this request")
        
        if self.status != 'PENDING':
            raise ValidationError("Only pending requests can be rejected")
        
        self.status = 'REJECTED'
        self.approved_by = approver
        self.approved_on = timezone.now()
        self.rejection_reason = reason
        self.notes += f"\nRejected by {approver.full_name}: {reason}"
        self.save()

    def cancel(self, cancelled_by, reason=''):
        """Cancel the leave request."""
        if cancelled_by != self.employee and not self.can_approve(cancelled_by):
            raise ValidationError("You don't have permission to cancel this request")
        
        if self.status in ['COMPLETED', 'CANCELLED']:
            raise ValidationError("Cannot cancel completed or already cancelled request")
        
        self.status = 'CANCELLED'
        if reason:
            self.notes += f"\nCancelled by {cancelled_by.full_name}: {reason}"
        self.save()
        
        # Restore leave balance if it was approved
        if self.status == 'APPROVED':
            self.restore_leave_balance()

    def update_leave_balance(self):
        """Update leave balance when request is approved."""
        balance, created = LeaveBalance.objects.get_or_create(
            employee=self.employee,
            leave_type=self.leave_type,
            year=self.start_date.year,
            defaults={'allocated_days': 0}
        )
        
        balance.use_days(self.total_days, f"Leave request {self.request_number}")

    def restore_leave_balance(self):
        """Restore leave balance when request is cancelled."""
        try:
            balance = LeaveBalance.objects.get(
                employee=self.employee,
                leave_type=self.leave_type,
                year=self.start_date.year
            )
            balance.adjust_days(self.total_days, f"Restored from cancelled request {self.request_number}")
        except LeaveBalance.DoesNotExist:
            pass

    @property
    def is_approved(self):
        """Check if request is approved."""
        return self.status == 'APPROVED'

    @property
    def is_pending(self):
        """Check if request is pending approval."""
        return self.status == 'PENDING'

    @property
    def is_rejected(self):
        """Check if request is rejected."""
        return self.status == 'REJECTED'

    @property
    def is_cancelled(self):
        """Check if request is cancelled."""
        return self.status == 'CANCELLED'

    @property
    def is_active(self):
        """Check if leave is currently active."""
        if not self.is_approved:
            return False
        
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

    @property
    def is_upcoming(self):
        """Check if leave is upcoming."""
        if not self.is_approved:
            return False
        
        today = timezone.now().date()
        return self.start_date > today

    @property
    def is_completed(self):
        """Check if leave is completed."""
        if not self.is_approved:
            return False
        
        today = timezone.now().date()
        return self.end_date < today

class LeavePolicy(TimestampedModel, SoftDeleteModel):
    """
    Leave policies and rules for the organization.
    """
    name = models.CharField(_('policy name'), max_length=100)
    description = models.TextField(_('description'), blank=True)
    
    # Policy rules
    max_concurrent_leaves = models.PositiveIntegerField(_('max concurrent leaves'), default=3, help_text=_('Maximum number of employees on leave at the same time'))
    blackout_dates = models.JSONField(_('blackout dates'), default=list, help_text=_('Dates when leave is not allowed'))
    minimum_notice_days = models.PositiveIntegerField(_('minimum notice days'), default=7)
    max_leave_days_per_year = models.PositiveIntegerField(_('max leave days per year'), default=30)
    
    # Approval workflow
    approval_levels = models.JSONField(_('approval levels'), default=list, help_text=_('List of approval levels and roles'))
    auto_approve_days = models.PositiveIntegerField(_('auto approve days'), default=0, help_text=_('Days below which leave is auto-approved'))
    
    # Branch specific
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name='leave_policies', verbose_name=_('branch'), null=True, blank=True)
    
    # Status
    is_active = models.BooleanField(_('is active'), default=True)
    is_default = models.BooleanField(_('is default'), default=False)

    class Meta:
        verbose_name = _('leave policy')
        verbose_name_plural = _('leave policies')
        ordering = ['name']

    def __str__(self):
        return self.name

    def is_blackout_date(self, date):
        """Check if a date is in blackout period."""
        for blackout in self.blackout_dates:
            start_date = datetime.strptime(blackout['start'], '%Y-%m-%d').date()
            end_date = datetime.strptime(blackout['end'], '%Y-%m-%d').date()
            if start_date <= date <= end_date:
                return True
        return False

    def can_approve_auto(self, leave_request):
        """Check if leave request can be auto-approved."""
        if leave_request.total_days <= self.auto_approve_days:
            return True
        return False

    def get_approval_workflow(self, leave_request):
        """Get approval workflow for a leave request."""
        return self.approval_levels
