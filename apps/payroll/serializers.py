from rest_framework import serializers
from django.db.models import Sum, Q
from django.utils import timezone
from apps.employees.models import Employee
from .models import PayrollPeriod, PayrollItem, EmployeePayroll, CasualPayment, DeductionCategory, WorkAssignment


class DeductionCategorySerializer(serializers.ModelSerializer):
    """Serializer for deduction categories."""
    
    class Meta:
        model = DeductionCategory
        fields = '__all__'
        read_only_fields = ('created_by',)


class PayrollItemSerializer(serializers.ModelSerializer):
    """Serializer for payroll items."""
    deduction_category_name = serializers.CharField(source='deduction_category.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    
    class Meta:
        model = PayrollItem
        fields = '__all__'
        read_only_fields = ('created_by', 'last_modified_by')


class PayrollPeriodSerializer(serializers.ModelSerializer):
    """Serializer for payroll periods."""
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    total_payroll = serializers.SerializerMethodField()
    employee_count = serializers.SerializerMethodField()
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    last_modified_by_name = serializers.CharField(source='last_modified_by.full_name', read_only=True)
    
    class Meta:
        model = PayrollPeriod
        fields = '__all__'
        read_only_fields = ('created_by', 'last_modified_by')
    
    def get_total_payroll(self, obj):
        """Get total payroll amount for this period."""
        return obj.get_total_payroll()
    
    def get_employee_count(self, obj):
        """Get number of employees in this payroll period."""
        return obj.employee_payrolls.count()


class PayrollPeriodCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating payroll periods with automatic employee inclusion."""
    
    class Meta:
        model = PayrollPeriod
        fields = ['start_date', 'end_date', 'branch', 'notes']
    
    def create(self, validated_data):
        """Create payroll period and automatically include eligible employees."""
        payroll_period = super().create(validated_data)
        
        # Get eligible employees
        employees = payroll_period.get_employees_for_payroll()
        
        # Create employee payroll records
        for employee in employees:
            EmployeePayroll.objects.get_or_create(
                employee=employee,
                payroll_period=payroll_period,
                defaults={
                    'rate_structure': employee.get_applicable_rate_structure(),
                    'basic_salary': employee.current_rate,
                    'created_by': self.context['request'].user.employee_profile if hasattr(self.context['request'].user, 'employee_profile') else None
                }
            )
        
        return payroll_period


class EmployeePayrollSerializer(serializers.ModelSerializer):
    """Serializer for employee payroll records."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    branch_name = serializers.CharField(source='employee.branch.name', read_only=True)
    department_name = serializers.CharField(source='employee.department.name', read_only=True)
    role_name = serializers.CharField(source='employee.role.name', read_only=True)
    payroll_period_display = serializers.CharField(source='payroll_period.__str__', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    last_modified_by_name = serializers.CharField(source='last_modified_by.full_name', read_only=True)
    
    class Meta:
        model = EmployeePayroll
        fields = '__all__'
        read_only_fields = ('created_by', 'last_modified_by', 'expense')
    
    def update(self, instance, validated_data):
        """Update payroll and recalculate amounts."""
        instance = super().update(instance, validated_data)
        instance.calculate_payroll()
        instance.save()
        return instance


class WorkAssignmentSerializer(serializers.ModelSerializer):
    """Serializer for work assignments."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    assigned_by_name = serializers.CharField(source='assigned_by.full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)
    duration_hours = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = WorkAssignment
        fields = '__all__'
        read_only_fields = ('assignment_number', 'calculated_rate', 'total_payment')
    
    def create(self, validated_data):
        """Create work assignment with automatic rate calculation."""
        assignment = super().create(validated_data)
        
        # Calculate rate based on employee's rate structure
        rate_structure = assignment.employee.get_applicable_rate_structure(assignment.work_date)
        if rate_structure:
            assignment.calculated_rate = rate_structure.calculate_rate(
                employee=assignment.employee,
                work_date=assignment.work_date,
                hours_worked=assignment.expected_hours
            )
            assignment.save()
        
        return assignment


class WorkAssignmentCheckInSerializer(serializers.Serializer):
    """Serializer for checking in to work assignment."""
    check_in_time = serializers.DateTimeField(required=False)
    
    def update(self, instance, validated_data):
        """Check in to work assignment."""
        check_in_time = validated_data.get('check_in_time')
        instance.check_in(check_in_time)
        return instance


class WorkAssignmentCheckOutSerializer(serializers.Serializer):
    """Serializer for checking out from work assignment."""
    check_out_time = serializers.DateTimeField(required=False)
    actual_hours = serializers.DecimalField(max_digits=5, decimal_places=2, required=False)
    
    def update(self, instance, validated_data):
        """Check out from work assignment."""
        check_out_time = validated_data.get('check_out_time')
        actual_hours = validated_data.get('actual_hours')
        instance.check_out(check_out_time, actual_hours)
        return instance


class CasualPaymentSerializer(serializers.ModelSerializer):
    """Serializer for casual payments."""
    employee_name = serializers.CharField(source='employee.full_name', read_only=True)
    employee_id = serializers.CharField(source='employee.employee_id', read_only=True)
    branch_name = serializers.CharField(source='employee.branch.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    approved_by_name = serializers.CharField(source='approved_by.full_name', read_only=True)
    is_partially_paid = serializers.ReadOnlyField()
    outstanding_amount = serializers.ReadOnlyField()
    
    class Meta:
        model = CasualPayment
        fields = '__all__'
        read_only_fields = ('payment_number', 'created_by', 'approved_by', 'approved_date', 'expense', 'deduction_revenue')
    
    def create(self, validated_data):
        """Create casual payment with automatic calculation."""
        payment = super().create(validated_data)
        payment.calculate_payment()
        payment.save()
        return payment
    
    def update(self, instance, validated_data):
        """Update casual payment and recalculate amounts."""
        instance = super().update(instance, validated_data)
        instance.calculate_payment()
        instance.save()
        return instance


class CasualPaymentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating casual payments with work assignment integration."""
    work_assignments = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False,
        help_text="List of work assignment IDs to include in payment"
    )
    
    class Meta:
        model = CasualPayment
        fields = [
            'employee', 'payment_frequency', 'period_start_date', 'period_end_date',
            'total_hours_worked', 'hourly_rate', 'work_assignments', 'notes'
        ]
    
    def create(self, validated_data):
        """Create casual payment from work assignments."""
        work_assignments = validated_data.pop('work_assignments', [])
        
        # Create the payment
        payment = CasualPayment.objects.create(**validated_data)
        
        # If work assignments provided, calculate from them
        if work_assignments:
            assignments = WorkAssignment.objects.filter(
                id__in=work_assignments,
                employee=payment.employee,
                status='completed'
            )
            
            total_hours = 0
            for assignment in assignments:
                total_hours += assignment.actual_hours or assignment.expected_hours
            
            payment.total_hours_worked = total_hours
            payment.calculate_payment()
            payment.save()
        
        return payment


class CasualPaymentApproveSerializer(serializers.Serializer):
    """Serializer for approving casual payments."""
    approved_by = serializers.PrimaryKeyRelatedField(queryset=Employee.objects.all())
    
    def update(self, instance, validated_data):
        """Approve the casual payment."""
        approved_by = validated_data['approved_by']
        instance.approve(approved_by)
        return instance


class CasualPaymentPaySerializer(serializers.Serializer):
    """Serializer for marking casual payments as paid."""
    payment_date = serializers.DateField(required=False)
    payment_method = serializers.ChoiceField(choices=CasualPayment.PAYMENT_METHOD_CHOICES, required=False)
    payment_reference = serializers.CharField(max_length=100, required=False)
    partial_amount = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)
    
    def update(self, instance, validated_data):
        """Mark the casual payment as paid."""
        instance.mark_as_paid(**validated_data)
        return instance


class CasualPaymentDeductionSerializer(serializers.Serializer):
    """Serializer for adding deductions to casual payments."""
    category = serializers.CharField(max_length=100)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    reason = serializers.CharField(max_length=200)
    description = serializers.CharField(max_length=500, required=False)
    
    def update(self, instance, validated_data):
        """Add deduction to the casual payment."""
        instance.add_deduction(**validated_data)
        return instance


class PayrollSummarySerializer(serializers.Serializer):
    """Serializer for payroll summary data."""
    period = PayrollPeriodSerializer()
    total_employees = serializers.IntegerField()
    total_gross_pay = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_deductions = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_net_pay = serializers.DecimalField(max_digits=12, decimal_places=2)
    paid_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    cancelled_count = serializers.IntegerField()


class BranchPayrollSummarySerializer(serializers.Serializer):
    """Serializer for branch-specific payroll summary."""
    branch = serializers.CharField()
    total_employees = serializers.IntegerField()
    total_payroll = serializers.DecimalField(max_digits=12, decimal_places=2)
    average_salary = serializers.DecimalField(max_digits=12, decimal_places=2)
    casual_workers_count = serializers.IntegerField()
    casual_payments_total = serializers.DecimalField(max_digits=12, decimal_places=2)


class DeductionSummarySerializer(serializers.Serializer):
    """Serializer for deduction summary data."""
    category = serializers.CharField()
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    count = serializers.IntegerField()
    percentage_of_total = serializers.DecimalField(max_digits=5, decimal_places=2)


class PayrollReportSerializer(serializers.Serializer):
    """Serializer for comprehensive payroll reports."""
    period = PayrollPeriodSerializer()
    summary = PayrollSummarySerializer()
    branch_summaries = BranchPayrollSummarySerializer(many=True)
    deduction_summaries = DeductionSummarySerializer(many=True)
    top_earners = EmployeePayrollSerializer(many=True)
    casual_payments = CasualPaymentSerializer(many=True)



class CasualPaymentListSerializer(serializers.ModelSerializer):
    """Simplified serializer for casual payment lists."""
    employee_name = serializers.CharField(source='employee.user.get_full_name', read_only=True)
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = CasualPayment
        fields = [
            'id', 'employee_name', 'payment_type', 'payment_type_display', 
            'amount', 'work_date', 'status', 'status_display', 'created_at'
        ]

