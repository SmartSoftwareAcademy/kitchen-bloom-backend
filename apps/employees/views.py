from django.db.models import Q, Sum, Count
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.translation import gettext_lazy as _  # noqa: F401
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, DjangoModelPermissions
from rest_framework.pagination import PageNumberPagination
from datetime import datetime, timedelta

from .models import Department, Employee, Attendance, LeaveType, LeaveBalance, LeaveRequest, LeavePolicy
from .serializers import (
    DepartmentSerializer, EmployeeListSerializer,
    EmployeeDetailSerializer, EmployeeCreateSerializer,
    AddressSerializer, AttendanceSerializer,
    LeaveTypeSerializer, LeaveBalanceSerializer, LeaveRequestSerializer,
    LeaveRequestApprovalSerializer, LeavePolicySerializer,
    LeaveBalanceAdjustmentSerializer, LeaveReportSerializer,
    EmployeeLeaveSummarySerializer
)
from apps.base.utils import get_request_branch_id

class StandardResultsSetPagination(PageNumberPagination):
    """Custom pagination class."""
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class DepartmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows departments to be viewed or edited.
    """
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated, IsAdminUser]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'description']
    ordering_fields = ['name', 'code', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        """
        Optionally filter by active status and/or parent department.
        """
        queryset = super().get_queryset()
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by parent department
        parent_id = self.request.query_params.get('parent_id')
        if parent_id is not None:
            if parent_id == 'null':
                queryset = queryset.filter(parent_department__isnull=True)
            else:
                queryset = queryset.filter(parent_department_id=parent_id)
        
        return queryset.select_related('parent_department')
    
    def perform_destroy(self, instance):
        """
        Prevent deletion if department has employees or sub-departments.
        """
        if instance.employees.exists():
            return Response(
                {'detail': 'Cannot delete department with employees. Reassign or delete employees first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if instance.sub_departments.exists():
            return Response(
                {'detail': 'Cannot delete department with sub-departments. Delete or reassign them first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        instance.delete()
    
    @action(detail=True, methods=['get'])
    def employees(self, request, pk=None):
        """
        Get all employees in this department.
        """
        department = self.get_object()
        employees = department.employees.all()
        
        # Apply filtering
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            employees = employees.filter(is_active=is_active.lower() == 'true')
        
        # Apply pagination
        page = self.paginate_queryset(employees)
        if page is not None:
            serializer = EmployeeListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = EmployeeListSerializer(employees, many=True)
        return Response(serializer.data)

class EmployeeViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows employees to be viewed or edited.
    """
    queryset = Employee.objects.all()
    permission_classes = [IsAuthenticated, DjangoModelPermissions]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = [
        'employee_id', 'user__first_name', 'user__last_name', 'user__email',
        'phone_number', 'department__name', 'role__name'
    ]
    ordering_fields = [
        'user__last_name', 'user__first_name', 'hire_date',
        'department__name', 'role__name', 'is_active'
    ]
    ordering = ['user__last_name', 'user__first_name']

    def get_serializer_class(self):
        """
        Use different serializers for different actions.
        """
        if self.action == 'create':
            return EmployeeCreateSerializer
        elif self.action == 'list':
            return EmployeeListSerializer
        return EmployeeDetailSerializer
    
    def get_queryset(self):
        """
        Filter employees based on user permissions and query parameters.
        """
        queryset = super().get_queryset()
        user = self.request.user
        request = self.request
        
        # Non-admin users can only see active employees
        if not user.is_staff:
            queryset = queryset.filter(is_active=True)
            
            # For non-admin users, only show employees with management roles
            # when accessing the list view
            if request.resolver_match.url_name == 'employee-list':
                from apps.accounts.models import Role
                queryset = queryset.filter(
                    role__name__in=[Role.ADMIN, Role.MANAGER]
                )
        
        # Filter by department
        department_id = self.request.query_params.get('department_id')
        if department_id is not None:
            queryset = queryset.filter(department_id=department_id)
        
        # Filter by role
        role_id = self.request.query_params.get('role_id')
        if role_id is not None:
            queryset = queryset.filter(role_id=role_id)
        
        # Filter by employment type
        employment_type = self.request.query_params.get('employment_type')
        if employment_type is not None:
            queryset = queryset.filter(employment_type=employment_type)
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by search query
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(employee_id__icontains=search) |
                Q(user__email__icontains=search) |
                Q(phone_number__icontains=search)
            )
        
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(branch__id=branch_id)
        
        return queryset.select_related(
            'user', 'department', 'role', 'manager', 'manager__user'
        )
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticated, IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """
        Set the created_by and updated_by fields to the current user.
        """
        serializer.save(created_by=self.request.user, updated_by=self.request.user)
    
    def perform_update(self, serializer):
        """
        Set the updated_by field to the current user.
        """
        serializer.save(updated_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def direct_reports(self, request, pk=None):
        """
        Get all direct reports for this employee.
        """
        employee = self.get_object()
        direct_reports = employee.direct_reports.all()
        
        # Apply pagination
        page = self.paginate_queryset(direct_reports)
        if page is not None:
            serializer = EmployeeListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = EmployeeListSerializer(direct_reports, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get', 'post'])
    def addresses(self, request, pk=None):
        """
        List or create addresses for this employee.
        """
        employee = self.get_object()
        
        if request.method == 'GET':
            addresses = employee.addresses.all()
            serializer = AddressSerializer(addresses, many=True)
            return Response(serializer.data)
        
        elif request.method == 'POST':
            # Ensure only one primary address exists
            is_primary = request.data.get('is_primary', False)
            if is_primary:
                employee.addresses.filter(is_primary=True).update(is_primary=False)
            
            # Create the address
            serializer = AddressSerializer(data=request.data)
            if serializer.is_valid():
                # Set the content type and object ID for the generic relation
                content_type = ContentType.objects.get_for_model(Employee)
                serializer.save(
                    content_type=content_type,
                    object_id=employee.id,
                    is_primary=is_primary
                )
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def reporting_line(self, request, pk=None):
        """
        Get the reporting line (hierarchy) for this employee.
        """
        employee = self.get_object()
        reporting_line = employee.get_reporting_line()
        serializer = self.get_serializer(reporting_line, many=True)
        return Response(serializer.data)

class AttendanceViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows attendance records to be viewed or edited.
    """
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter, filters.BaseFilterBackend]
    search_fields = [
        'employee__user__first_name', 'employee__user__last_name',
        'employee__employee_id', 'status', 'notes'
    ]
    ordering_fields = [
        'date', 'check_in', 'check_out', 'status',
        'is_approved', 'created_at', 'updated_at'
    ]
    ordering = ['-date', '-check_in']
    filterset_fields = {
        'employee': ['exact'],
        'date': ['exact', 'gte', 'lte', 'gt', 'lt'],
        'status': ['exact', 'in'],
        'is_approved': ['exact'],
    }

    def get_queryset(self):
        """
        Filter queryset based on user permissions and request parameters.
        """
        queryset = super().get_queryset()
        
        # Regular users can only see their own attendance
        if not self.request.user.is_staff:
            queryset = queryset.filter(employee__user=self.request.user)
        
        # Filter by employee_id if provided
        employee_id = self.request.query_params.get('employee_id')
        if employee_id and self.request.user.is_staff:
            queryset = queryset.filter(employee_id=employee_id)
        
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(date__gte=start_date)
        if end_date:
            queryset = queryset.filter(date__lte=end_date)
        
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(branch__id=branch_id)
        
        return queryset.select_related('employee__user', 'approved_by__user')

    def perform_create(self, serializer):
        """Set the employee to the current user if not specified."""
        if 'employee' not in serializer.validated_data and hasattr(self.request.user, 'employee_profile'):
            serializer.save(employee=self.request.user.employee_profile)
        else:
            serializer.save()

    @action(detail=True, methods=['post'])
    def check_in(self, request, pk=None):
        """Check in an employee."""
        attendance = self.get_object()
        
        if attendance.check_in:
            return Response(
                {'error': _('Employee is already checked in.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attendance.check_in = timezone.now()
        attendance.save()
        
        return Response({'status': _('Checked in successfully')})

    @action(detail=True, methods=['post'])
    def check_out(self, request, pk=None):
        """Check out an employee."""
        attendance = self.get_object()
        
        if not attendance.check_in:
            return Response(
                {'error': _('Employee is not checked in.')},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if attendance.check_out:
            return Response(
                {'error': _('Employee is already checked out.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        attendance.check_out = timezone.now()
        attendance.save()
        
        return Response({'status': _('Checked out successfully')})

    @action(detail=False, methods=['get'])
    def current_status(self, request):
        """Get current check-in status for the authenticated user or specified employee."""
        employee_id = request.query_params.get('employee_id')
        
        if employee_id and request.user.is_staff:
            employee = Employee.objects.filter(id=employee_id).first()
        elif hasattr(request.user, 'employee_profile'):
            employee = request.user.employee_profile
        else:
            return Response(
                {'error': _('No employee profile found.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not employee:
            return Response(
                {'error': _('Employee not found.')},
                status=status.HTTP_404_NOT_FOUND
            )
        
        today = timezone.now().date()
        attendance, created = Attendance.objects.get_or_create(
            employee=employee,
            date=today,
            defaults={'status': 'PRESENT'}
        )
        
        serializer = self.get_serializer(attendance)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve an attendance record."""
        if not request.user.is_staff:
            return Response(
                {'error': _('Only staff members can approve attendance.')},
                status=status.HTTP_403_FORBIDDEN
            )
        
        attendance = self.get_object()
        attendance.is_approved = True
        attendance.approved_by = request.user.employee_profile
        attendance.save()
        
        return Response({'status': _('Attendance approved successfully')})

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Reject an attendance record."""
        if not request.user.is_staff:
            return Response(
                {'error': _('Only staff members can reject attendance.')},
                status=status.HTTP_403_FORBIDDEN
            )
        
        attendance = self.get_object()
        attendance.is_approved = False
        attendance.approved_by = request.user.employee_profile
        attendance.notes = request.data.get('reason', attendance.notes)
        attendance.save()
        
        return Response({'status': _('Attendance rejected')})

class LeaveTypeViewSet(viewsets.ModelViewSet):
    """ViewSet for LeaveType model."""
    queryset = LeaveType.objects.all()
    serializer_class = LeaveTypeSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['category', 'is_active', 'is_paid', 'branch']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'category', 'default_days_per_year']
    ordering = ['name']

    def get_queryset(self):
        """Filter by branch if specified."""
        queryset = super().get_queryset()
        branch = self.request.query_params.get('branch')
        if branch:
            queryset = queryset.filter(Q(branch_id=branch) | Q(branch__isnull=True))
        return queryset

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle leave type active status."""
        leave_type = self.get_object()
        leave_type.is_active = not leave_type.is_active
        leave_type.save()
        return Response({
            'id': leave_type.id,
            'is_active': leave_type.is_active,
            'message': f"Leave type {'activated' if leave_type.is_active else 'deactivated'}"
        })

    @action(detail=False, methods=['get'])
    def categories(self, request):
        """Get all leave categories."""
        categories = LeaveType.LEAVE_CATEGORY_CHOICES
        return Response([{'value': choice[0], 'label': choice[1]} for choice in categories])

    @action(detail=False, methods=['get'])
    def applicable_types(self, request):
        """Get leave types applicable to current user."""
        user = request.user
        if hasattr(user, 'employee_profile'):
            employee = user.employee_profile
            applicable_types = LeaveType.objects.filter(
                is_active=True
            ).filter(
                Q(applicable_employment_types__contains=[employee.employment_type]) |
                Q(applicable_employment_types=[])
            ).filter(
                Q(branch=employee.branch) | Q(branch__isnull=True)
            )
            serializer = self.get_serializer(applicable_types, many=True)
            return Response(serializer.data)
        return Response([])

class LeaveBalanceViewSet(viewsets.ModelViewSet):
    """ViewSet for LeaveBalance model."""
    queryset = LeaveBalance.objects.all()
    serializer_class = LeaveBalanceSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['employee', 'leave_type', 'year']
    ordering_fields = ['year', 'leave_type__name']
    ordering = ['-year', 'leave_type__name']

    def get_queryset(self):
        """Filter by current user's employee profile."""
        queryset = super().get_queryset()
        user = self.request.user
        
        # If user is employee, show only their balances
        if hasattr(user, 'employee_profile'):
            queryset = queryset.filter(employee=user.employee_profile)
        
        return queryset

    @action(detail=True, methods=['post'])
    def adjust_balance(self, request, pk=None):
        """Adjust leave balance."""
        balance = self.get_object()
        serializer = LeaveBalanceAdjustmentSerializer(data=request.data)
        
        if serializer.is_valid():
            days = serializer.validated_data['days']
            notes = serializer.validated_data.get('notes', '')
            adjustment_type = serializer.validated_data['adjustment_type']
            
            if adjustment_type == 'allocate':
                balance.allocate_days(days, notes)
            elif adjustment_type == 'adjust':
                balance.adjust_days(days, notes)
            elif adjustment_type == 'carry_over':
                balance.carry_over_to_next_year(days)
            
            return Response({
                'message': f'Balance adjusted successfully',
                'new_balance': self.get_serializer(balance).data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def my_balances(self, request):
        """Get current user's leave balances."""
        user = request.user
        if not hasattr(user, 'employee_profile'):
            return Response([])
        
        current_year = timezone.now().year
        balances = self.get_queryset().filter(year=current_year)
        serializer = self.get_serializer(balances, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['post'])
    def bulk_allocate(self, request):
        """Bulk allocate leave days to employees."""
        employee_ids = request.data.get('employee_ids', [])
        leave_type_id = request.data.get('leave_type_id')
        days = request.data.get('days', 0)
        year = request.data.get('year', timezone.now().year)
        notes = request.data.get('notes', '')
        
        if not employee_ids or not leave_type_id:
            return Response(
                {'error': 'Employee IDs and leave type ID are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            leave_type = LeaveType.objects.get(id=leave_type_id)
        except LeaveType.DoesNotExist:
            return Response(
                {'error': 'Leave type not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        allocated_count = 0
        for employee_id in employee_ids:
            try:
                employee = Employee.objects.get(id=employee_id)
                balance, created = LeaveBalance.objects.get_or_create(
                    employee=employee,
                    leave_type=leave_type,
                    year=year,
                    defaults={'allocated_days': 0}
                )
                balance.allocate_days(days, notes)
                allocated_count += 1
            except Employee.DoesNotExist:
                continue
        
        return Response({
            'message': f'Successfully allocated {days} days to {allocated_count} employees'
        })

class LeaveRequestViewSet(viewsets.ModelViewSet):
    """ViewSet for LeaveRequest model."""
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['status', 'priority', 'leave_type', 'employee', 'start_date', 'end_date']
    search_fields = ['request_number', 'reason', 'employee__user__first_name', 'employee__user__last_name']
    ordering_fields = ['created_at', 'start_date', 'end_date', 'status', 'priority']
    ordering = ['-created_at']

    def get_queryset(self):
        """Filter based on user permissions."""
        queryset = super().get_queryset()
        user = self.request.user
        
        if hasattr(user, 'employee_profile'):
            employee = user.employee_profile
            
            # If user is regular employee, show only their requests
            if employee.role and employee.role.name not in ['ADMIN', 'HR_MANAGER', 'MANAGER']:
                queryset = queryset.filter(employee=employee)
            else:
                # Managers can see requests from their subordinates
                if employee.role.name == 'MANAGER':
                    subordinates = employee.get_subordinates()
                    queryset = queryset.filter(employee__in=subordinates)
        
        return queryset

    def perform_create(self, serializer):
        """Set employee to current user when creating request."""
        if hasattr(self.request.user, 'employee_profile'):
            serializer.save(employee=self.request.user.employee_profile)
        else:
            serializer.save()

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a leave request."""
        leave_request = self.get_object()
        serializer = LeaveRequestApprovalSerializer(data=request.data)
        
        if serializer.is_valid():
            action = serializer.validated_data['action']
            notes = serializer.validated_data.get('notes', '')
            
            try:
                if action == 'approve':
                    leave_request.approve(request.user.employee_profile, notes)
                    message = 'Leave request approved successfully'
                elif action == 'reject':
                    rejection_reason = serializer.validated_data['rejection_reason']
                    leave_request.reject(request.user.employee_profile, rejection_reason)
                    message = 'Leave request rejected successfully'
                elif action == 'cancel':
                    leave_request.cancel(request.user.employee_profile, notes)
                    message = 'Leave request cancelled successfully'
                
                return Response({
                    'message': message,
                    'request': self.get_serializer(leave_request).data
                })
            
            except Exception as e:
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """Get current user's leave requests."""
        user = request.user
        if not hasattr(user, 'employee_profile'):
            return Response([])
        
        requests = self.get_queryset().filter(employee=user.employee_profile)
        serializer = self.get_serializer(requests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Get pending leave requests for approval."""
        user = request.user
        if not hasattr(user, 'employee_profile'):
            return Response([])
        
        employee = user.employee_profile
        pending_requests = []
        
        # Get requests that this user can approve
        all_requests = LeaveRequest.objects.filter(status='PENDING')
        
        for req in all_requests:
            if req.can_approve(employee):
                pending_requests.append(req)
        
        serializer = self.get_serializer(pending_requests, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def calendar_view(self, request):
        """Get leave requests for calendar view."""
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        queryset = self.get_queryset().filter(status='APPROVED')
        
        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(end_date__lte=end_date)
        
        # Format for calendar
        calendar_data = []
        for request in queryset:
            calendar_data.append({
                'id': request.id,
                'title': f"{request.employee.full_name} - {request.leave_type.name}",
                'start': request.start_date.isoformat(),
                'end': request.end_date.isoformat(),
                'status': request.status,
                'employee_name': request.employee.full_name,
                'leave_type': request.leave_type.name,
                'total_days': request.total_days
            })
        
        return Response(calendar_data)

    @action(detail=False, methods=['post'])
    def bulk_approve(self, request):
        """Bulk approve leave requests."""
        request_ids = request.data.get('request_ids', [])
        action = request.data.get('action', 'approve')
        notes = request.data.get('notes', '')
        
        if not request_ids:
            return Response(
                {'error': 'Request IDs are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        approved_count = 0
        errors = []
        
        for request_id in request_ids:
            try:
                leave_request = LeaveRequest.objects.get(id=request_id)
                
                if action == 'approve':
                    leave_request.approve(request.user.employee_profile, notes)
                elif action == 'reject':
                    leave_request.reject(request.user.employee_profile, notes)
                
                approved_count += 1
            except Exception as e:
                errors.append(f"Request {request_id}: {str(e)}")
        
        return Response({
            'message': f'Successfully processed {approved_count} requests',
            'errors': errors
        })

class LeavePolicyViewSet(viewsets.ModelViewSet):
    """ViewSet for LeavePolicy model."""
    queryset = LeavePolicy.objects.all()
    serializer_class = LeavePolicySerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ['is_active', 'is_default', 'branch']
    search_fields = ['name', 'description']
    ordering_fields = ['name']
    ordering = ['name']

    def get_queryset(self):
        """Filter by branch if specified."""
        queryset = super().get_queryset()
        branch = self.request.query_params.get('branch')
        if branch:
            queryset = queryset.filter(Q(branch_id=branch) | Q(branch__isnull=True))
        return queryset

    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle policy active status."""
        policy = self.get_object()
        policy.is_active = not policy.is_active
        policy.save()
        return Response({
            'id': policy.id,
            'is_active': policy.is_active,
            'message': f"Policy {'activated' if policy.is_active else 'deactivated'}"
        })

    @action(detail=False, methods=['get'])
    def applicable_policy(self, request):
        """Get applicable policy for current user's branch."""
        user = request.user
        if hasattr(user, 'employee_profile') and user.employee_profile.branch:
            try:
                policy = LeavePolicy.objects.get(
                    branch=user.employee_profile.branch,
                    is_active=True
                )
                serializer = self.get_serializer(policy)
                return Response(serializer.data)
            except LeavePolicy.DoesNotExist:
                # Return default policy
                try:
                    default_policy = LeavePolicy.objects.get(is_default=True, is_active=True)
                    serializer = self.get_serializer(default_policy)
                    return Response(serializer.data)
                except LeavePolicy.DoesNotExist:
                    return Response(None)
        return Response(None)

class LeaveReportViewSet(viewsets.ViewSet):
    """ViewSet for leave reports."""
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def leave_summary(self, request):
        """Generate leave summary report."""
        serializer = LeaveReportSerializer(data=request.data)
        
        if serializer.is_valid():
            data = serializer.validated_data
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            employee = data.get('employee')
            leave_type = data.get('leave_type')
            status = data.get('status')
            branch = data.get('branch')
            
            queryset = LeaveRequest.objects.all()
            
            if start_date:
                queryset = queryset.filter(start_date__gte=start_date)
            if end_date:
                queryset = queryset.filter(end_date__lte=end_date)
            if employee:
                queryset = queryset.filter(employee=employee)
            if leave_type:
                queryset = queryset.filter(leave_type=leave_type)
            if status:
                queryset = queryset.filter(status=status)
            if branch:
                queryset = queryset.filter(employee__branch=branch)
            
            # Aggregate data
            summary = queryset.aggregate(
                total_requests=Count('id'),
                total_days=Sum('total_days'),
                approved_requests=Count('id', filter=Q(status='APPROVED')),
                pending_requests=Count('id', filter=Q(status='PENDING')),
                rejected_requests=Count('id', filter=Q(status='REJECTED'))
            )
            
            # Group by leave type
            by_type = queryset.values('leave_type__name').annotate(
                count=Count('id'),
                total_days=Sum('total_days')
            )
            
            # Group by employee
            by_employee = queryset.values('employee__user__first_name', 'employee__user__last_name').annotate(
                count=Count('id'),
                total_days=Sum('total_days')
            )
            
            return Response({
                'summary': summary,
                'by_type': by_type,
                'by_employee': by_employee,
                'requests': LeaveRequestSerializer(queryset, many=True).data
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def employee_summary(self, request):
        """Get leave summary for all employees."""
        employees = Employee.objects.filter(is_active=True)
        summaries = []
        
        for employee in employees:
            balances = LeaveBalance.objects.filter(employee=employee, year=timezone.now().year)
            pending_requests = LeaveRequest.objects.filter(employee=employee, status='PENDING').count()
            approved_requests = LeaveRequest.objects.filter(employee=employee, status='APPROVED').count()
            
            total_days_taken = balances.aggregate(total=Sum('used_days'))['total'] or 0
            total_days_available = balances.aggregate(total=Sum('available_days'))['total'] or 0
            
            summaries.append({
                'employee': EmployeeListSerializer(employee).data,
                'leave_balances': LeaveBalanceSerializer(balances, many=True).data,
                'pending_requests': pending_requests,
                'approved_requests': approved_requests,
                'total_days_taken': total_days_taken,
                'total_days_available': total_days_available
            })
        
        return Response(summaries)

    @action(detail=False, methods=['get'])
    def leave_balance_report(self, request):
        """Generate leave balance report."""
        year = request.query_params.get('year', timezone.now().year)
        branch = request.query_params.get('branch')
        
        queryset = LeaveBalance.objects.filter(year=year)
        
        if branch:
            queryset = queryset.filter(employee__branch_id=branch)
        
        # Group by employee
        employee_balances = {}
        for balance in queryset:
            employee_id = balance.employee.id
            if employee_id not in employee_balances:
                employee_balances[employee_id] = {
                    'employee': EmployeeListSerializer(balance.employee).data,
                    'balances': []
                }
            employee_balances[employee_id]['balances'].append(
                LeaveBalanceSerializer(balance).data
            )
        
        return Response(list(employee_balances.values()))
