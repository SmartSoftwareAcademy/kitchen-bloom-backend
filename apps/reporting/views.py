from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from rest_framework import permissions
from django.conf import settings
from .models import ReportSchedule, ReportExecutionLog, Report
from .serializers import ReportScheduleSerializer, ReportExecutionLogSerializer, ReportSerializer, ReportDataSerializer
from .tasks import generate_report_async
from django.utils import timezone
from django.db.models import Q, Avg, Count, Sum
from django.db.models.functions import Coalesce
from apps.reporting.models import ReportType
from apps.sales.models import Order

class ReportViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing reports.
    """
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """Return only active reports that the user has permission to view."""
        return Report.objects.filter(is_active=True)

    @action(detail=True, methods=['post'])
    def generate(self, request, pk: int = None) -> Response:
        """Generate a report on demand."""
        report = self.get_object()
        
        # Create execution log
        execution_log = ReportExecutionLog.objects.create(
            report=report,
            status='pending',
            created_by=request.user
        )
        
        # Trigger async report generation
        generate_report_async.delay(
            report_id=report.id,
            user_id=request.user.id,
            execution_log_id=execution_log.id
        )
        
        return Response(
            {'status': 'Report generation started', 'execution_id': execution_log.id},
            status=status.HTTP_202_ACCEPTED
        )
    
    @action(detail=True, methods=['get'])
    def data(self, request, pk: int = None) -> Response:
        """Get report data directly without generating a file."""
        report = self.get_object()
        
        # Parse and validate date range
        date_range_serializer = ReportDataSerializer(data=request.query_params)
        date_range_serializer.is_valid(raise_exception=True)
        date_range = date_range_serializer.validated_data
        
        # Get report data based on type
        data = self._get_report_data(report, date_range)
        
        return Response(data)
    
    def _get_report_data(self, report, date_range):
        """Generate report data based on the report type and date range."""
        start_date = date_range.get('start_date')
        end_date = date_range.get('end_date') or timezone.now()
        
        if report.report_type == ReportType.SALES_SUMMARY:
            return self._get_sales_summary(start_date, end_date)
        elif report.report_type == ReportType.SALES_BY_CATEGORY:
            return self._get_sales_by_category(start_date, end_date)
        elif report.report_type == ReportType.SALES_BY_ITEM:
            return self._get_sales_by_item(start_date, end_date)
        elif report.report_type == ReportType.PAYMENT_METHODS:
            return self._get_payment_methods(start_date, end_date)
        elif report.report_type == ReportType.INVENTORY_LEVELS:
            return self._get_inventory_levels()
        elif report.report_type == ReportType.INVENTORY_VALUATION:
            return self._get_inventory_valuation()
        elif report.report_type == ReportType.EMPLOYEE_PERFORMANCE:
            return self._get_employee_performance(start_date, end_date)
        elif report.report_type == ReportType.CUSTOMER_ANALYTICS:
            return self._get_customer_analytics(start_date, end_date)
        elif report.report_type == ReportType.TABLE_TURNOVER:
            return self._get_table_turnover(start_date, end_date)
        elif report.report_type == ReportType.KITCHEN_PERFORMANCE:
            return self._get_kitchen_performance(start_date, end_date)
        else:
            return {'error': 'Unsupported report type'}
    
    def _get_sales_summary(self, start_date, end_date):
        """Generate sales summary report data."""
        orders = Order.objects.filter(
            created_at__range=(start_date, end_date),
            status=Order.COMPLETED
        )
        
        # Group by time period
        time_series = self._group_by_time_period(orders, 'created_at')
        
        # Calculate metrics
        total_sales = orders.aggregate(
            total=Coalesce(Sum('total_amount'), 0.0),
            avg_order=Coalesce(Avg('total_amount'), 0.0),
            count=Count('id')
        )
        
        return {
            'report_type': 'sales_summary',
            'time_period': {'start': start_date, 'end': end_date},
            'metrics': total_sales,
            'time_series': time_series
        }

class ReportScheduleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing report schedules.
    """
    queryset = ReportSchedule.objects.all()
    permission_classes = [IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return ReportScheduleViewSet
        return ReportScheduleSerializer
    
    def get_queryset(self):
        """Return only schedules for reports the user has access to."""
        return ReportSchedule.objects.filter(
            Q(report__created_by=self.request.user) | 
            Q(recipients=self.request.user)
        ).distinct()
    
    @action(detail=True, methods=['post'])
    def run_now(self, request, pk: int = None) -> Response:
        """Run a scheduled report immediately."""
        schedule = self.get_object()
        
        # Create execution log
        execution_log = ReportExecutionLog.objects.create(
            report=schedule.report,
            scheduled_run=schedule,
            status='pending',
            created_by=request.user
        )
        
        # Trigger async report generation
        generate_report_async.delay(
            report_id=schedule.report.id,
            user_id=request.user.id,
            schedule_id=schedule.id,
            execution_log_id=execution_log.id
        )
        
        # Update last run time
        schedule.last_run = timezone.now()
        schedule.save(update_fields=['last_run'])
        
        return Response(
            {'status': 'Report generation started', 'execution_id': execution_log.id},
            status=status.HTTP_202_ACCEPTED
        )

class ReportExecutionLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing report execution logs.
    """
    serializer_class = ReportExecutionLogSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return only logs for reports the user has access to."""
        return ReportExecutionLog.objects.filter(
            Q(report__created_by=self.request.user) |
            Q(created_by=self.request.user) |
            Q(scheduled_run__recipients=self.request.user)
        ).distinct()
    
    @action(detail=True, methods=['get'])
    def download(self, request, pk: int = None) -> Response:
        """Download the generated report file."""
        execution_log = self.get_object()
        
        if not execution_log.file_path or not execution_log.file_size:
            return Response(
                {'error': 'Report file not found or not generated yet'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # In a real implementation, serve the file using X-Accel-Redirect or similar
        # This is a simplified example
        file_path = settings.MEDIA_ROOT / execution_log.file_path
        
        if not file_path.exists():
            return Response(
                {'error': 'Report file not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Set appropriate content type based on file extension
        content_type = 'application/octet-stream'
        if execution_log.file_path.endswith('.pdf'):
            content_type = 'application/pdf'
        elif execution_log.file_path.endswith('.xlsx'):
            content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif execution_log.file_path.endswith('.csv'):
            content_type = 'text/csv'
        
        with open(file_path, 'rb') as f:
            response = Response(f.read(), content_type=content_type)
            response['Content-Disposition'] = f'attachment; filename="{execution_log.report.name}_{execution_log.started_at.strftime("%Y%m%d_%H%M%S")}{file_path.suffix}"'
            return response
