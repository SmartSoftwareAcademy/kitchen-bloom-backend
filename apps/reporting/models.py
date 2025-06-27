from django.db import models
from django.utils import timezone
from django.conf import settings

# Use a lazy reference to the User model to avoid circular imports
User = settings.AUTH_USER_MODEL


class ReportType(models.TextChoices):
    SALES_SUMMARY = 'sales_summary', 'Sales Summary'
    SALES_BY_CATEGORY = 'sales_by_category', 'Sales by Category'
    SALES_BY_ITEM = 'sales_by_item', 'Sales by Item'
    PAYMENT_METHODS = 'payment_methods', 'Payment Methods'
    INVENTORY_LEVELS = 'inventory_levels', 'Inventory Levels'
    INVENTORY_VALUATION = 'inventory_valuation', 'Inventory Valuation'
    EMPLOYEE_PERFORMANCE = 'employee_performance', 'Employee Performance'
    CUSTOMER_ANALYTICS = 'customer_analytics', 'Customer Analytics'
    TABLE_TURNOVER = 'table_turnover', 'Table Turnover'
    KITCHEN_PERFORMANCE = 'kitchen_performance', 'Kitchen Performance'
    OTHER = 'other', 'Other'


class ReportFrequency(models.TextChoices):
    DAILY = 'daily', 'Daily'
    WEEKLY = 'weekly', 'Weekly'
    MONTHLY = 'monthly', 'Monthly'
    QUARTERLY = 'quarterly', 'Quarterly'
    YEARLY = 'yearly', 'Yearly'
    ON_DEMAND = 'on_demand', 'On Demand'


class ReportFormat(models.TextChoices):
    PDF = 'pdf', 'PDF'
    EXCEL = 'excel', 'Excel'
    CSV = 'csv', 'CSV'
    JSON = 'json', 'JSON'


class Report(models.Model):
    """Base model for storing report configurations and metadata."""
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    report_type = models.CharField(
        max_length=50,
        choices=ReportType.choices,
        default=ReportType.SALES_SUMMARY
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_reports'
    )

    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['report_type']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name


class ReportSchedule(models.Model):
    """Model for scheduling automated report generation and delivery."""
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='schedules')
    frequency = models.CharField(
        max_length=20,
        choices=ReportFrequency.choices,
        default=ReportFrequency.ON_DEMAND
    )
    format = models.CharField(
        max_length=10,
        choices=ReportFormat.choices,
        default=ReportFormat.PDF
    )
    recipients = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='scheduled_reports')
    last_run = models.DateTimeField(null=True, blank=True)
    next_run = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-next_run', '-is_active']

    def __str__(self):
        return f"{self.report.name} - {self.get_frequency_display()}"

    def update_schedule(self):
        """Update the next run time based on frequency."""
        if self.frequency == ReportFrequency.ON_DEMAND:
            self.next_run = None
        else:
            now = timezone.now()
            if self.frequency == ReportFrequency.DAILY:
                self.next_run = now + timezone.timedelta(days=1)
            elif self.frequency == ReportFrequency.WEEKLY:
                self.next_run = now + timezone.timedelta(weeks=1)
            elif self.frequency == ReportFrequency.MONTHLY:
                # Add one month, handling year rollover
                if now.month == 12:
                    self.next_run = now.replace(year=now.year + 1, month=1, day=1)
                else:
                    self.next_run = now.replace(month=now.month + 1, day=1)
            elif self.frequency == ReportFrequency.QUARTERLY:
                quarter = (now.month - 1) // 3 + 1
                if quarter == 4:
                    self.next_run = now.replace(year=now.year + 1, month=1, day=1)
                else:
                    self.next_run = now.replace(month=quarter * 3 + 1, day=1)
            elif self.frequency == ReportFrequency.YEARLY:
                self.next_run = now.replace(year=now.year + 1, month=1, day=1)
        self.save()


class ReportFilter(models.Model):
    """Model for storing report filter configurations."""
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='filters')
    filter_name = models.CharField(max_length=100)
    filter_value = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['filter_name']

    def __str__(self):
        return f"{self.report.name} - {self.filter_name}"


class ReportExecutionLog(models.Model):
    """Model for tracking report execution history."""
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name='execution_logs')
    scheduled_run = models.ForeignKey(ReportSchedule, on_delete=models.SET_NULL, null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, default='pending')
    error_message = models.TextField(null=True, blank=True)
    file_path = models.CharField(max_length=512, null=True, blank=True)
    file_size = models.PositiveIntegerField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='executed_reports'
    )

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['report', 'started_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"{self.report.name} - {self.started_at}"

    @property
    def duration(self):
        """Calculate the duration of the report execution in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
