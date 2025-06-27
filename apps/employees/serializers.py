from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers
from django.contrib.auth import get_user_model
from apps.accounts.models import Role
from apps.branches.models import Branch
from .models import Department, Employee, Attendance, LeaveType, LeaveBalance, LeaveRequest, LeavePolicy
from apps.base.models import Address
from datetime import datetime, timedelta

User = get_user_model()


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for the global Address model."""
    class Meta:
        model = Address
        fields = [
            'id', 'address_type', 'address_line1', 'address_line2', 'city',
            'state', 'postal_code', 'country', 'is_primary', 'latitude',
            'longitude', 'created_at', 'updated_at'
        ]
        read_only_fields = ('id', 'created_at', 'updated_at')

class DepartmentSerializer(serializers.ModelSerializer):
    """Serializer for the Department model."""
    parent_department_name = serializers.CharField(
        source='parent_department.name', 
        read_only=True,
        allow_null=True
    )
    employee_count = serializers.IntegerField(read_only=True)
    sub_department_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = Department
        fields = [
            'id', 'name', 'code', 'description', 'parent_department',
            'parent_department_name', 'is_active', 'employee_count',
            'sub_department_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ('id', 'created_at', 'updated_at', 'code')
    
    def validate_parent_department(self, value):
        """Validate that a department is not set as its own parent."""
        if self.instance and self.instance == value:
            raise serializers.ValidationError(
                'A department cannot be its own parent.'
            )
        return value

class UserNestedSerializer(serializers.ModelSerializer):
    """Nested serializer for user details."""
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'is_active']
        read_only_fields = fields

class AttendanceSerializer(serializers.ModelSerializer):
    """Serializer for the Attendance model."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    working_hours = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True,
        help_text=_('Total working hours in decimal format')
    )
    is_checked_in = serializers.BooleanField(read_only=True)
    approved_by_name = serializers.CharField(
        source='approved_by.full_name',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = Attendance
        fields = [
            'id', 'employee', 'employee_name', 'date', 'check_in', 'check_out',
            'status', 'status_display', 'working_hours', 'is_checked_in',
            'notes', 'is_approved', 'approved_by', 'approved_by_name',
            'ip_address', 'location', 'device_info', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'employee_name', 'status_display', 'working_hours',
            'is_checked_in', 'approved_by_name', 'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'employee': {'required': True},
            'date': {'required': True}
        }

    def validate(self, data):
        """
        Validate the attendance data.
        """
        # Ensure check_out is after check_in
        if 'check_out' in data and 'check_in' in data:
            if data['check_out'] and data['check_in'] and data['check_out'] < data['check_in']:
                raise serializers.ValidationError({
                    'check_out': _('Check-out time cannot be before check-in time.')
                })

        # Prevent future dates
        if 'date' in data and data['date'] > timezone.now().date():
            raise serializers.ValidationError({
                'date': _('Cannot record attendance for future dates.')
            })

        return data

    def create(self, validated_data):
        """
        Create a new attendance record.
        """
        # Set the current user as the approver if not specified
        request = self.context.get('request')
        if request and request.user and request.user.is_authenticated:
            validated_data['approved_by'] = request.user.employee_profile
        
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """
        Update an existing attendance record.
        """
        # Update approved_by if status is being changed
        if 'status' in validated_data and validated_data['status'] != instance.status:
            request = self.context.get('request')
            if request and request.user and request.user.is_authenticated:
                validated_data['approved_by'] = request.user.employee_profile
        
        return super().update(instance, validated_data)
    
    def get_full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip()

class EmployeeListSerializer(serializers.ModelSerializer):
    """Serializer for listing employees with basic information."""
    full_name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email')
    department = serializers.StringRelatedField()
    role = serializers.StringRelatedField()
    manager = serializers.StringRelatedField()
    primary_address = serializers.SerializerMethodField()
    
    class Meta:
        model = Employee
        fields = [
            'id', 'employee_id', 'full_name', 'email', 'phone_number',
            'department', 'role', 'manager', 'hire_date', 'is_active',
            'primary_address'
        ]
        read_only_fields = fields
    
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()
    
    def get_primary_address(self, obj):
        primary_address = obj.addresses.filter(is_primary=True).first()
        if primary_address:
            return f"{primary_address.address_line1}, {primary_address.city}"
        return None

class EmployeeDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for Employee model with nested user and addresses."""
    user = UserNestedSerializer(read_only=True)
    department = DepartmentSerializer(read_only=True)
    department_id = serializers.PrimaryKeyRelatedField(
        queryset=Department.objects.all(),
        source='department',
        write_only=True,
        required=False
    )
    role = serializers.StringRelatedField()
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        source='role',
        write_only=True,
        required=False
    )
    manager = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(
            is_active=True,
            role__name__in=[Role.ADMIN, Role.MANAGER]
        ),
        required=False,
        allow_null=True,
        help_text=_('The manager of this employee. Must be an active employee with a management role.')
    )
    manager_details = serializers.SerializerMethodField()
    addresses = AddressSerializer(many=True, read_only=True)
    age = serializers.IntegerField(read_only=True)
    tenure_years = serializers.FloatField(read_only=True)
    
    class Meta:
        model = Employee
        fields = [
            # Basic info
            'id', 'employee_id', 'user', 'date_of_birth', 'gender', 'age',
            
            # Contact info
            'phone_number', 'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation',
            
            # Employment details
            'department', 'department_id', 'role', 'role_id', 'manager', 'manager_details',
            'hire_date', 'employment_type', 'salary', 'is_active', 'tenure_years',
            
            # Banking
            'bank_name', 'bank_account_number', 'bank_branch',
            
            # Government IDs
            'tax_id', 'national_id', 'nhif_number', 'nssf_number', 'kra_pin',
            
            # Addresses
            'addresses',
            
            # Metadata
            'notes', 'created_at', 'updated_at'
        ]
        read_only_fields = (
            'id', 'employee_id', 'created_at', 'updated_at', 'deleted_at',
            'age', 'tenure_years', 'manager_details', 'addresses'
        )
    
    def get_manager_details(self, obj):
        if obj.manager:
            return {
                'id': obj.manager.id,
                'name': str(obj.manager),
                'email': obj.manager.user.email if obj.manager.user else None
            }
        return None
    
    def validate(self, data):
        """Validate the employee data."""
        # Ensure manager has a management role
        manager = data.get('manager')
        if manager and not getattr(manager.role, 'is_management', False):
            raise serializers.ValidationError({
                'manager': 'Selected manager must have a management role.'
            })
        
        # Validate salary against role's salary range if role is provided
        if 'role' in data and 'salary' in data:
            role = data['role']
            salary = data['salary']
            if role.min_salary and salary < role.min_salary:
                raise serializers.ValidationError({
                    'salary': f'Salary must be at least {role.min_salary} for this role.'
                })
            if role.max_salary and salary > role.max_salary:
                raise serializers.ValidationError({
                    'salary': f'Salary cannot exceed {role.max_salary} for this role.'
                })
        
        return data
    
    def create(self, validated_data):
        """Create a new employee with related models."""
        # Extract nested data
        department = validated_data.pop('department', None)
        role = validated_data.pop('role', None)
        
        # Create the employee
        employee = Employee.objects.create(
            **validated_data,
            department=department,
            role=role
        )
        
        return employee
    
    def update(self, instance, validated_data):
        """Update an existing employee."""
        # Update simple fields
        for attr, value in validated_data.items():
            if attr not in ['department', 'role']:  # Handle these separately
                setattr(instance, attr, value)
        
        # Update department if provided
        if 'department' in validated_data:
            instance.department = validated_data['department']
        
        # Update role if provided
        if 'role' in validated_data:
            instance.role = validated_data['role']
        
        instance.save()
        return instance

class EmployeeCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a new employee with user account."""
    user_id = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        source='user',
        required=False,
        allow_null=True
    )
    username = serializers.CharField(write_only=True, required=False)
    email = serializers.EmailField(write_only=True)
    first_name = serializers.CharField(write_only=True, max_length=30)
    last_name = serializers.CharField(write_only=True, max_length=30)
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = Employee
        fields = [
            'user_id', 'username', 'email', 'first_name', 'last_name', 'password',
            'date_of_birth', 'gender', 'phone_number', 'department', 'role',
            'manager', 'hire_date', 'employment_type', 'salary',
            'emergency_contact_name', 'emergency_contact_phone',
            'emergency_contact_relation', 'bank_name', 'bank_account_number',
            'bank_branch', 'tax_id', 'national_id', 'nhif_number',
            'nssf_number', 'kra_pin', 'notes'
        ]
    
    def validate(self, data):
        """Validate the employee creation data."""
        # If no user_id is provided, we need to create a new user
        if 'user' not in data and not all([
            data.get('username'),
            data.get('email'),
            data.get('first_name'),
            data.get('last_name'),
            data.get('password')
        ]):
            raise serializers.ValidationError({
                'non_field_errors': [
                    'Either provide an existing user_id or all required fields to create a new user.'
                ]
            })
        
        # If creating a new user, check if username/email already exists
        if 'user' not in data:
            if User.objects.filter(username=data['username']).exists():
                raise serializers.ValidationError({
                    'username': 'A user with this username already exists.'
                })
            if User.objects.filter(email=data['email']).exists():
                raise serializers.ValidationError({
                    'email': 'A user with this email already exists.'
                })
        
        return data
    
    def create(self, validated_data):
        """Create a new employee and optionally a new user account."""
        user_data = {}
        
        # If user_id is provided, use existing user
        if 'user' in validated_data:
            user = validated_data.pop('user')
        else:
            # Create a new user
            user_data = {
                'username': validated_data.pop('username'),
                'email': validated_data.pop('email'),
                'first_name': validated_data.pop('first_name'),
                'last_name': validated_data.pop('last_name'),
                'password': validated_data.pop('password'),
                'is_active': True
            }
            user = User.objects.create_user(**user_data)
        
        # Create the employee
        employee = Employee.objects.create(user=user, **validated_data)
        
        return employee

class LeaveTypeSerializer(serializers.ModelSerializer):
    """Serializer for LeaveType model."""
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    applicable_employment_types_display = serializers.SerializerMethodField()
    
    class Meta:
        model = LeaveType
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at', 'created_by', 'last_modified_by')

    def get_applicable_employment_types_display(self, obj):
        """Get human-readable employment types."""
        employment_type_choices = dict(Employee.EMPLOYMENT_TYPE_CHOICES)
        return [employment_type_choices.get(et, et) for et in obj.applicable_employment_types]

    def validate(self, data):
        """Custom validation for leave type."""
        # Ensure default days per year is positive
        if data.get('default_days_per_year', 0) < 0:
            raise serializers.ValidationError("Default days per year cannot be negative")
        
        # Ensure pay percentage is between 0 and 100
        pay_percentage = data.get('pay_percentage', 100)
        if pay_percentage < 0 or pay_percentage > 100:
            raise serializers.ValidationError("Pay percentage must be between 0 and 100")
        
        return data

class LeaveBalanceSerializer(serializers.ModelSerializer):
    """Serializer for LeaveBalance model."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    available_days = serializers.ReadOnlyField()
    total_days = serializers.ReadOnlyField()
    
    class Meta:
        model = LeaveBalance
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def validate(self, data):
        """Custom validation for leave balance."""
        # Ensure used days don't exceed total allocated days
        total_allocated = (data.get('allocated_days', 0) + 
                          data.get('carried_over_days', 0) + 
                          data.get('adjusted_days', 0))
        
        if data.get('used_days', 0) > total_allocated:
            raise serializers.ValidationError("Used days cannot exceed total allocated days")
        
        return data

class LeaveRequestSerializer(serializers.ModelSerializer):
    """Serializer for LeaveRequest model."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    leave_type_name = serializers.CharField(source='leave_type.name', read_only=True)
    leave_type_category = serializers.CharField(source='leave_type.category', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    priority_display = serializers.CharField(source='get_priority_display', read_only=True)
    total_days = serializers.ReadOnlyField()
    
    # Computed fields
    is_approved = serializers.ReadOnlyField()
    is_pending = serializers.ReadOnlyField()
    is_rejected = serializers.ReadOnlyField()
    is_cancelled = serializers.ReadOnlyField()
    is_active = serializers.ReadOnlyField()
    is_upcoming = serializers.ReadOnlyField()
    is_completed = serializers.ReadOnlyField()
    
    # Leave balance information
    available_days = serializers.SerializerMethodField()
    leave_balance_info = serializers.SerializerMethodField()
    
    class Meta:
        model = LeaveRequest
        fields = '__all__'
        read_only_fields = ('request_number', 'created_at', 'updated_at', 'approved_on')

    def get_available_days(self, obj):
        """Get available leave days for this request."""
        if obj.leave_type and obj.employee:
            return obj.leave_type.get_available_days(obj.employee, obj.start_date.year)
        return 0

    def get_leave_balance_info(self, obj):
        """Get detailed leave balance information."""
        if not obj.leave_type or not obj.employee:
            return None
        
        try:
            balance = LeaveBalance.objects.get(
                employee=obj.employee,
                leave_type=obj.leave_type,
                year=obj.start_date.year
            )
            return {
                'allocated_days': balance.allocated_days,
                'used_days': balance.used_days,
                'carried_over_days': balance.carried_over_days,
                'adjusted_days': balance.adjusted_days,
                'available_days': balance.available_days,
                'total_days': balance.total_days
            }
        except LeaveBalance.DoesNotExist:
            return {
                'allocated_days': obj.leave_type.default_days_per_year,
                'used_days': 0,
                'carried_over_days': 0,
                'adjusted_days': 0,
                'available_days': obj.leave_type.default_days_per_year,
                'total_days': obj.leave_type.default_days_per_year
            }

    def validate(self, data):
        """Custom validation for leave request."""
        # Validate date range
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("Start date cannot be after end date")
        
        # Validate against blackout dates
        if start_date and end_date:
            # Get applicable leave policy
            employee = data.get('employee')
            if employee and employee.branch:
                try:
                    policy = LeavePolicy.objects.get(branch=employee.branch, is_active=True)
                    current_date = start_date
                    while current_date <= end_date:
                        if policy.is_blackout_date(current_date):
                            raise serializers.ValidationError(f"Leave is not allowed on {current_date} (blackout date)")
                        current_date += timedelta(days=1)
                except LeavePolicy.DoesNotExist:
                    pass
        
        # Validate leave balance
        if self.instance and self.instance.status == 'APPROVED':
            # Don't validate balance for approved requests
            return data
        
        leave_type = data.get('leave_type')
        employee = data.get('employee')
        total_days = data.get('total_days')
        
        if leave_type and employee and total_days:
            available_days = leave_type.get_available_days(employee, start_date.year if start_date else timezone.now().year)
            if total_days > available_days:
                raise serializers.ValidationError(f"Insufficient leave balance. Available: {available_days}, Requested: {total_days}")
        
        return data

    def create(self, validated_data):
        """Create leave request with proper status."""
        # Set status to PENDING if requires approval, otherwise APPROVED
        leave_type = validated_data.get('leave_type')
        if leave_type and not leave_type.requires_approval:
            validated_data['status'] = 'APPROVED'
        else:
            validated_data['status'] = 'PENDING'
        
        return super().create(validated_data)

class LeaveRequestApprovalSerializer(serializers.Serializer):
    """Serializer for leave request approval/rejection."""
    action = serializers.ChoiceField(choices=['approve', 'reject', 'cancel'])
    notes = serializers.CharField(required=False, allow_blank=True)
    rejection_reason = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        """Validate approval data."""
        action = data.get('action')
        
        if action == 'reject' and not data.get('rejection_reason'):
            raise serializers.ValidationError("Rejection reason is required when rejecting a request")
        
        return data

class LeavePolicySerializer(serializers.ModelSerializer):
    """Serializer for LeavePolicy model."""
    approval_levels_display = serializers.SerializerMethodField()
    
    class Meta:
        model = LeavePolicy
        fields = '__all__'
        read_only_fields = ('created_at', 'updated_at')

    def get_approval_levels_display(self, obj):
        """Get human-readable approval levels."""
        return obj.approval_levels if obj.approval_levels else []

    def validate(self, data):
        """Custom validation for leave policy."""
        # Validate blackout dates format
        blackout_dates = data.get('blackout_dates', [])
        for blackout in blackout_dates:
            if 'start' not in blackout or 'end' not in blackout:
                raise serializers.ValidationError("Blackout dates must have 'start' and 'end' fields")
            
            try:
                start_date = datetime.strptime(blackout['start'], '%Y-%m-%d').date()
                end_date = datetime.strptime(blackout['end'], '%Y-%m-%d').date()
                if start_date > end_date:
                    raise serializers.ValidationError("Blackout start date cannot be after end date")
            except ValueError:
                raise serializers.ValidationError("Invalid date format in blackout dates")
        
        return data

class LeaveBalanceAdjustmentSerializer(serializers.Serializer):
    """Serializer for leave balance adjustments."""
    days = serializers.DecimalField(max_digits=6, decimal_places=2)
    notes = serializers.CharField(required=False, allow_blank=True)
    adjustment_type = serializers.ChoiceField(choices=['allocate', 'adjust', 'carry_over'])

    def validate_days(self, value):
        """Validate days value."""
        if value <= 0:
            raise serializers.ValidationError("Days must be greater than 0")
        return value

class LeaveReportSerializer(serializers.Serializer):
    """Serializer for leave reports."""
    start_date = serializers.DateField()
    end_date = serializers.DateField()
    employee = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all(), required=False)
    leave_type = serializers.PrimaryKeyRelatedField(queryset=LeaveType.objects.all(), required=False)
    status = serializers.ChoiceField(choices=LeaveRequest.STATUS_CHOICES, required=False)
    branch = serializers.PrimaryKeyRelatedField(queryset=Branch.objects.all(), required=False)

    def validate(self, data):
        """Validate report parameters."""
        start_date = data.get('start_date')
        end_date = data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise serializers.ValidationError("Start date cannot be after end date")
        
        return data

class EmployeeLeaveSummarySerializer(serializers.Serializer):
    """Serializer for employee leave summary."""
    employee = EmployeeDetailSerializer()
    leave_balances = LeaveBalanceSerializer(many=True)
    pending_requests = serializers.IntegerField()
    approved_requests = serializers.IntegerField()
    total_days_taken = serializers.DecimalField(max_digits=6, decimal_places=2)
    total_days_available = serializers.DecimalField(max_digits=6, decimal_places=2)
