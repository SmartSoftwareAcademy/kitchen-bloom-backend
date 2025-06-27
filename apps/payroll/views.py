from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Sum, Q, Count, Avg, F
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta

from django.contrib.auth import get_user_model
User = get_user_model()

from apps.payroll.models import (
    PayrollPeriod, PayrollItem, EmployeePayroll, WorkAssignment, 
    CasualPayment, DeductionCategory
)
from apps.payroll.utils import (
    get_or_create_payroll_period,
    get_current_payroll_period,
    create_next_payroll_period
)
from apps.payroll.serializers import (
    PayrollPeriodSerializer, PayrollPeriodCreateSerializer, PayrollItemSerializer,
    EmployeePayrollSerializer, WorkAssignmentSerializer, WorkAssignmentCheckInSerializer,
    WorkAssignmentCheckOutSerializer, CasualPaymentSerializer, CasualPaymentCreateSerializer,
    CasualPaymentApproveSerializer, CasualPaymentPaySerializer, CasualPaymentDeductionSerializer,
    PayrollSummarySerializer, BranchPayrollSummarySerializer, DeductionSummarySerializer,
    PayrollReportSerializer, DeductionCategorySerializer
)
from apps.employees.models import Employee
from apps.branches.models import Branch


class DeductionCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for deduction categories."""
    queryset = DeductionCategory.objects.all()
    serializer_class = DeductionCategorySerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['deduction_type', 'is_active', 'affects_accounting']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'deduction_type', 'created_at']
    ordering = ['name']


class PayrollItemViewSet(viewsets.ModelViewSet):
    """ViewSet for payroll items."""
    queryset = PayrollItem.objects.all()
    serializer_class = PayrollItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['item_type', 'is_percentage', 'is_tax_deductible', 'is_mandatory', 'branch', 'deduction_category']
    search_fields = ['name']
    ordering_fields = ['name', 'item_type', 'amount', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """Filter by branch if specified."""
        queryset = super().get_queryset()
        branch_id = self.request.query_params.get('branch_id')
        if branch_id:
            queryset = queryset.filter(Q(branch_id=branch_id) | Q(branch__isnull=True))
        return queryset


class PayrollPeriodViewSet(viewsets.ModelViewSet):
    """ViewSet for payroll periods."""
    queryset = PayrollPeriod.objects.all()
    serializer_class = PayrollPeriodSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'branch']
    search_fields = ['notes']
    ordering_fields = ['start_date', 'end_date', 'status', 'created_at']
    ordering = ['-start_date']
    
    def get_queryset(self):
        """Filter by branch if specified."""
        queryset = super().get_queryset()
        branch_id = self.request.query_params.get('branch')
        status = self.request.query_params.get('status')
        
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if status:
            queryset = queryset.filter(status=status)
            
        return queryset

    def get_serializer_class(self):
        """Use different serializer for creation."""
        if self.action in ['create', 'generate_payroll']:
            return PayrollPeriodCreateSerializer
        return PayrollPeriodSerializer

    @action(detail=False, methods=['post'])
    def generate_payroll(self, request):
        """
        Generate payroll for a date range, automatically creating a period if needed.
        
        Expected request data:
        {
            'start_date': 'YYYY-MM-DD',
            'end_date': 'YYYY-MM-DD',
            'branch_id': <optional>,
            'notes': <optional>
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        start_date = serializer.validated_data['start_date']
        end_date = serializer.validated_data['end_date']
        branch_id = serializer.validated_data.get('branch_id')
        notes = serializer.validated_data.get('notes', '')
        
        # Get the current user (request.user should be an Employee instance)
        created_by = getattr(request.user, 'employee', None)
        
        # Get or create the payroll period
        branch = None
        if branch_id:
            from apps.branches.models import Branch
            branch = Branch.objects.get(id=branch_id)
            
        period = get_or_create_payroll_period(
            start_date=start_date,
            end_date=end_date,
            branch=branch,
            created_by=created_by
        )
        
        if notes:
            period.notes = notes
            period.save()
        
        # Process payroll for this period
        return self.process_payroll_for_period(period, request)
    
    @action(detail=True, methods=['post'])
    def process_payroll(self, request, pk=None):
        """Process payroll for all employees in the period."""
        period = self.get_object()
        return self.process_payroll_for_period(period, request)
    
    def process_payroll_for_period(self, period, request):
        """
        Process payroll for all employees in the given period.
        """
        # Get all active employees for the branch (or all if no branch)
        employees = Employee.objects.filter(is_active=True)
        if period.branch:
            employees = employees.filter(branch=period.branch)
        
        created_count = 0
        updated_count = 0
        
        for employee in employees:
            # Get or create employee payroll for this period
            employee_payroll, created = EmployeePayroll.objects.get_or_create(
                employee=employee,
                payroll_period=period,
                defaults={
                    'rate_structure': employee.rate_structure
                }
            )
            
            # Calculate payroll
            employee_payroll.calculate_payroll()
            employee_payroll.save()
            
            if created:
                created_count += 1
            else:
                updated_count += 1
        
        # Process casual payments for this period
        casual_payments = CasualPayment.objects.filter(
            period_start_date__lte=period.end_date,
            period_end_date__gte=period.start_date,
            status__in=['pending', 'approved']
        )
        
        if period.branch:
            casual_payments = casual_payments.filter(employee__branch=period.branch)
        
        for payment in casual_payments:
            # Update payment status if needed
            if payment.status == 'pending':
                payment.status = 'approved'
                payment.approved_by = getattr(request.user, 'employee', None)
                payment.approved_date = timezone.now()
                payment.save()
        
        # Update period status
        period.status = 'processing'
        period.save()
        
        return Response({
            'message': f'Payroll processed for {created_count + updated_count} employees',
            'created': created_count,
            'updated': updated_count,
            'period_id': period.id,
            'period_status': period.status,
            'casual_payments_processed': casual_payments.count()
        })

    @action(detail=True, methods=['post'])
    def approve_payroll(self, request, pk=None):
        """Approve all payrolls in the period."""
        period = self.get_object()
        
        # Approve all employee payrolls
        employee_payrolls = period.employee_payrolls.filter(status='calculated')
        for payroll in employee_payrolls:
            payroll.status = 'approved'
            payroll.save()
        
        # Update period status
        period.status = 'completed'
        period.save()
        
        # Create accounting entries for all approved payrolls
        for payroll in employee_payrolls:
            if hasattr(payroll, 'create_accounting_entries'):
                payroll.create_accounting_entries()
        
        return Response({
            'message': f'Payroll approved for {employee_payrolls.count()} employees',
            'period_id': period.id,
            'period_status': period.status
        })

    @action(detail=True, methods=['post'])
    def pay_all(self, request, pk=None):
        """Mark all approved payrolls as paid."""
        period = self.get_object()
        payment_date = request.data.get('payment_date', timezone.now().date())
        payment_method = request.data.get('payment_method', 'bank_transfer')
        payment_reference = request.data.get('payment_reference', '')
        
        # Pay all approved employee payrolls
        employee_payrolls = period.employee_payrolls.filter(status='approved')
        paid_count = 0
        
        for payroll in employee_payrolls:
            try:
                payroll.mark_as_paid(payment_date, payment_method, payment_reference)
                paid_count += 1
            except Exception as e:
                # Log the error but continue with other payrolls
                print(f"Error processing payroll {payroll.id}: {str(e)}")
        
        # Update period status if all payrolls are paid
        if employee_payrolls.count() == paid_count:
            period.status = 'closed'
            period.save()
        
        return Response({
            'message': f'Payments processed for {paid_count} of {employee_payrolls.count()} employees',
            'period_id': period.id,
            'period_status': period.status,
            'paid_count': paid_count,
            'total_employees': employee_payrolls.count()
        })

    @action(detail=False, methods=['get'])
    def branch_summary(self, request):
        """Get payroll summary by branch."""
        branch_id = request.query_params.get('branch_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = self.get_queryset()
        
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(end_date__lte=end_date)
        
        # Get branch summaries
        branches = Branch.objects.all()
        summaries = []
        
        for branch in branches:
            branch_periods = queryset.filter(branch=branch)
            total_employees = Employee.objects.filter(branch=branch, is_active=True).count()
            total_payroll = branch_periods.aggregate(total=Sum('employee_payrolls__net_pay'))['total'] or 0
            average_salary = branch_periods.aggregate(avg=Avg('employee_payrolls__net_pay'))['avg'] or 0
            casual_workers_count = Employee.objects.filter(
                branch=branch, 
                employment_type__in=['CASUAL', 'CONTRACT', 'TEMP'],
                is_active=True
            ).count()
            casual_payments_total = CasualPayment.objects.filter(
                employee__branch=branch,
                status='paid'
            ).aggregate(total=Sum('amount_paid'))['total'] or 0
            
            summaries.append({
                'branch': branch.name,
                'total_employees': total_employees,
                'total_payroll': total_payroll,
                'average_salary': average_salary,
                'casual_workers_count': casual_workers_count,
                'casual_payments_total': casual_payments_total
            })
        
        serializer = BranchPayrollSummarySerializer(summaries, many=True)
        return Response(serializer.data)


class EmployeePayrollViewSet(viewsets.ModelViewSet):
    """ViewSet for employee payroll records."""
    queryset = EmployeePayroll.objects.all()
    serializer_class = EmployeePayrollSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_method', 'employee', 'payroll_period', 'employee__branch']
    search_fields = ['employee__user__first_name', 'employee__user__last_name', 'employee__employee_id']
    ordering_fields = ['gross_pay', 'net_pay', 'payment_date', 'created_at']
    ordering = ['-payroll_period__start_date', 'employee__user__last_name']

    @action(detail=True, methods=['post'])
    def calculate(self, request, pk=None):
        """Recalculate payroll for this employee."""
        payroll = self.get_object()
        payroll.calculate_payroll()
        payroll.save()
        
        serializer = self.get_serializer(payroll)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def mark_as_paid(self, request, pk=None):
        """Mark payroll as paid."""
        payroll = self.get_object()
        payment_date = request.data.get('payment_date', timezone.now().date())
        payment_method = request.data.get('payment_method', 'bank_transfer')
        payment_reference = request.data.get('payment_reference', '')
        
        payroll.mark_as_paid(payment_date, payment_method, payment_reference)
        
        serializer = self.get_serializer(payroll)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def employee_summary(self, request):
        """Get payroll summary for a specific employee."""
        employee_id = request.query_params.get('employee_id')
        if not employee_id:
            return Response({'error': 'employee_id is required'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            employee = Employee.objects.get(id=employee_id)
        except Employee.DoesNotExist:
            return Response({'error': 'Employee not found'}, status=status.HTTP_404_NOT_FOUND)
        
        payrolls = self.get_queryset().filter(employee=employee)
        
        summary = {
            'employee': employee.full_name,
            'total_payrolls': payrolls.count(),
            'total_gross_pay': payrolls.aggregate(total=Sum('gross_pay'))['total'] or 0,
            'total_deductions': payrolls.aggregate(total=Sum('total_deductions'))['total'] or 0,
            'total_net_pay': payrolls.aggregate(total=Sum('net_pay'))['total'] or 0,
            'paid_count': payrolls.filter(status='paid').count(),
            'pending_count': payrolls.filter(status__in=['draft', 'calculated', 'approved']).count(),
            'average_salary': payrolls.aggregate(avg=Avg('net_pay'))['avg'] or 0
        }
        
        return Response(summary)


class WorkAssignmentViewSet(viewsets.ModelViewSet):
    """ViewSet for work assignments."""
    queryset = WorkAssignment.objects.all()
    serializer_class = WorkAssignmentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'employee', 'work_date', 'employee__branch']
    search_fields = ['assignment_number', 'work_description', 'employee__user__first_name', 'employee__user__last_name']
    ordering_fields = ['work_date', 'start_time', 'expected_hours', 'created_at']
    ordering = ['-work_date', '-start_time']

    @action(detail=True, methods=['post'])
    def check_in(self, request, pk=None):
        """Check in to work assignment."""
        assignment = self.get_object()
        serializer = WorkAssignmentCheckInSerializer(assignment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({'message': 'Checked in successfully'})

    @action(detail=True, methods=['post'])
    def check_out(self, request, pk=None):
        """Check out from work assignment."""
        assignment = self.get_object()
        serializer = WorkAssignmentCheckOutSerializer(assignment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({'message': 'Checked out successfully'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel work assignment."""
        assignment = self.get_object()
        reason = request.data.get('reason', '')
        assignment.cancel(reason)
        
        return Response({'message': 'Assignment cancelled'})

    @action(detail=False, methods=['get'])
    def overdue(self, request):
        """Get overdue assignments."""
        overdue_assignments = self.get_queryset().filter(
            status__in=['scheduled', 'in_progress'],
            work_date__lt=timezone.now().date()
        )
        
        serializer = self.get_serializer(overdue_assignments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def today(self, request):
        """Get all work assignments for today."""
        today = timezone.now().date()
        assignments = self.get_queryset().filter(work_date=today)
        serializer = self.get_serializer(assignments, many=True)
        return Response(serializer.data)


class CasualPaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for casual payments."""
    queryset = CasualPayment.objects.all()
    serializer_class = CasualPaymentSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'payment_frequency', 'employee', 'employee__branch']
    search_fields = ['payment_number', 'employee__user__first_name', 'employee__user__last_name']
    ordering_fields = ['period_start_date', 'net_amount', 'payment_date', 'created_at']
    ordering = ['-period_start_date', '-created_at']

    def get_serializer_class(self):
        """Use different serializer for creation."""
        if self.action == 'create':
            return CasualPaymentCreateSerializer
        return CasualPaymentSerializer

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve casual payment."""
        payment = self.get_object()
        serializer = CasualPaymentApproveSerializer(payment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({'message': 'Payment approved'})

    @action(detail=True, methods=['post'])
    def pay(self, request, pk=None):
        """Mark casual payment as paid."""
        payment = self.get_object()
        serializer = CasualPaymentPaySerializer(payment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({'message': 'Payment processed'})

    @action(detail=True, methods=['post'])
    def add_deduction(self, request, pk=None):
        """Add deduction to casual payment."""
        payment = self.get_object()
        serializer = CasualPaymentDeductionSerializer(payment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response({'message': 'Deduction added'})

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel casual payment."""
        payment = self.get_object()
        reason = request.data.get('reason', '')
        payment.cancel(reason)
        
        return Response({'message': 'Payment cancelled'})

    @action(detail=False, methods=['get'])
    def pending_approval(self, request):
        """Get payments pending approval."""
        pending_payments = self.get_queryset().filter(status='pending')
        serializer = self.get_serializer(pending_payments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def approved_unpaid(self, request):
        """Get approved but unpaid payments."""
        approved_payments = self.get_queryset().filter(status='approved')
        serializer = self.get_serializer(approved_payments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def partially_paid(self, request):
        """Get partially paid payments."""
        partial_payments = self.get_queryset().filter(status='partially_paid')
        serializer = self.get_serializer(partial_payments, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def deduction_summary(self, request):
        """Get deduction summary."""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        branch_id = request.query_params.get('branch_id')
        
        queryset = self.get_queryset()
        
        if start_date:
            queryset = queryset.filter(period_start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(period_end_date__lte=end_date)
        if branch_id:
            queryset = queryset.filter(employee__branch_id=branch_id)
        
        # Aggregate deductions by category
        deduction_data = {}
        for payment in queryset:
            for deduction in payment.deduction_details:
                category = deduction.get('category', 'Other')
                amount = deduction.get('amount', 0)
                
                if category not in deduction_data:
                    deduction_data[category] = {'total': 0, 'count': 0}
                
                deduction_data[category]['total'] += amount
                deduction_data[category]['count'] += 1
        
        # Calculate percentages
        total_deductions = sum(data['total'] for data in deduction_data.values())
        
        summaries = []
        for category, data in deduction_data.items():
            percentage = (data['total'] / total_deductions * 100) if total_deductions > 0 else 0
            summaries.append({
                'category': category,
                'total_amount': data['total'],
                'count': data['count'],
                'percentage_of_total': round(percentage, 2)
            })
        
        serializer = DeductionSummarySerializer(summaries, many=True)
        return Response(serializer.data)


class PayrollReportViewSet(viewsets.ModelViewSet):
    """ViewSet for payroll reports."""
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """Get comprehensive payroll summary."""
        period_id = request.query_params.get('period_id')
        branch_id = request.query_params.get('branch_id')
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if period_id:
            try:
                period = PayrollPeriod.objects.get(id=period_id)
            except PayrollPeriod.DoesNotExist:
                return Response({'error': 'Payroll period not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            # Use date range
            if not start_date or not end_date:
                return Response({'error': 'start_date and end_date are required'}, status=status.HTTP_400_BAD_REQUEST)
            
            period = PayrollPeriod.objects.filter(
                start_date__gte=start_date,
                end_date__lte=end_date
            ).first()
            
            if not period:
                return Response({'error': 'No payroll period found for the specified date range'}, status=status.HTTP_404_NOT_FOUND)
        
        # Get employee payrolls
        employee_payrolls = period.employee_payrolls.all()
        if branch_id:
            employee_payrolls = employee_payrolls.filter(employee__branch_id=branch_id)
        
        # Calculate summary
        total_employees = employee_payrolls.count()
        total_gross_pay = employee_payrolls.aggregate(total=Sum('gross_pay'))['total'] or 0
        total_deductions = employee_payrolls.aggregate(total=Sum('total_deductions'))['total'] or 0
        total_net_pay = employee_payrolls.aggregate(total=Sum('net_pay'))['total'] or 0
        paid_count = employee_payrolls.filter(status='paid').count()
        pending_count = employee_payrolls.filter(status__in=['draft', 'calculated', 'approved']).count()
        cancelled_count = employee_payrolls.filter(status='cancelled').count()
        
        # Get top earners
        top_earners = employee_payrolls.order_by('-net_pay')[:10]
        
        # Get casual payments for the period
        casual_payments = CasualPayment.objects.filter(
            period_start_date__gte=period.start_date,
            period_end_date__lte=period.end_date
        )
        if branch_id:
            casual_payments = casual_payments.filter(employee__branch_id=branch_id)
        
        # Prepare response
        report_data = {
            'period': period,
            'summary': {
                'total_employees': total_employees,
                'total_gross_pay': total_gross_pay,
                'total_deductions': total_deductions,
                'total_net_pay': total_net_pay,
                'paid_count': paid_count,
                'pending_count': pending_count,
                'cancelled_count': cancelled_count
            },
            'top_earners': top_earners,
            'casual_payments': casual_payments
        }
        
        serializer = PayrollReportSerializer(report_data)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def branch_comparison(self, request):
        """Compare payroll across branches."""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        if not start_date or not end_date:
            return Response({'error': 'start_date and end_date are required'}, status=status.HTTP_400_BAD_REQUEST)
        
        branches = Branch.objects.all()
        comparison_data = []
        
        for branch in branches:
            # Get employee payrolls for this branch
            employee_payrolls = EmployeePayroll.objects.filter(
                payroll_period__start_date__gte=start_date,
                payroll_period__end_date__lte=end_date,
                employee__branch=branch
            )
            
            # Get casual payments for this branch
            casual_payments = CasualPayment.objects.filter(
                period_start_date__gte=start_date,
                period_end_date__lte=end_date,
                employee__branch=branch
            )
            
            branch_data = {
                'branch': branch.name,
                'total_employees': employee_payrolls.count(),
                'total_payroll': employee_payrolls.aggregate(total=Sum('net_pay'))['total'] or 0,
                'average_salary': employee_payrolls.aggregate(avg=Avg('net_pay'))['avg'] or 0,
                'casual_workers_count': Employee.objects.filter(
                    branch=branch,
                    employment_type__in=['CASUAL', 'CONTRACT', 'TEMP'],
                    is_active=True
                ).count(),
                'casual_payments_total': casual_payments.filter(status='paid').aggregate(total=Sum('amount_paid'))['total'] or 0
            }
            
            comparison_data.append(branch_data)
        
        serializer = BranchPayrollSummarySerializer(comparison_data, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def close_period(self, request, pk=None):
        """Close the payroll period."""
        period = self.get_object()
        
        # Check if all payrolls are processed
        pending_payrolls = EmployeePayroll.objects.filter(
            payroll_period=period,
            status__in=['draft', 'calculated']
        )
        
        if pending_payrolls.exists():
            return Response(
                {'error': 'Cannot close period with pending payrolls.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        period.status = 'completed'
        period.save()
        
        return Response(
            {'message': 'Period closed successfully.'},
            status=status.HTTP_200_OK
        )
