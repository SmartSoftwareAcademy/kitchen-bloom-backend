from rest_framework import serializers
from django.utils import timezone
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from .models import Report, ReportSchedule, ReportExecutionLog, ReportFilter

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name']

class ReportFilterSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReportFilter
        fields = ['id', 'filter_name', 'filter_value', 'created_at']
        read_only_fields = ['created_at']


class ReportSerializer(serializers.ModelSerializer):
    """Serializer for the Report model."""
    created_by = UserSerializer(read_only=True)
    filters = ReportFilterSerializer(many=True, read_only=True)
    
    class Meta:
        model = Report
        fields = [
            'id', 'name', 'description', 'report_type', 'is_active',
            'created_at', 'updated_at', 'created_by', 'filters'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by']


class ReportScheduleSerializer(serializers.ModelSerializer):
    """Serializer for the ReportSchedule model."""
    report = ReportSerializer(read_only=True)
    recipients = UserSerializer(many=True, read_only=True)
    next_run = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportSchedule
        fields = [
            'id', 'report', 'frequency', 'format', 'recipients', 'is_active',
            'last_run', 'next_run', 'created_at', 'updated_at'
        ]
        read_only_fields = ['last_run', 'next_run', 'created_at', 'updated_at']
    
    def get_next_run(self, obj) -> Optional[datetime]:
        """Calculate the next run time based on frequency."""
        return obj.next_run


class ReportScheduleCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a ReportSchedule."""
    recipients = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=User.objects.all(),
        required=False,
        default=[]
    )
    
    class Meta:
        model = ReportSchedule
        fields = ['id', 'report', 'frequency', 'format', 'recipients', 'is_active']
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the schedule data."""
        if 'report' in attrs and 'frequency' in attrs:
            report = attrs['report']
            frequency = attrs['frequency']
            
            # Check if a schedule with the same report and frequency already exists
            if ReportSchedule.objects.filter(
                report=report,
                frequency=frequency,
                is_active=True
            ).exists():
                raise serializers.ValidationError(
                    'An active schedule with this report and frequency already exists.'
                )
        
        return attrs
    
    def create(self, validated_data: Dict[str, Any]) -> ReportSchedule:
        """Create a new report schedule."""
        recipients = validated_data.pop('recipients', [])
        schedule = ReportSchedule.objects.create(**validated_data)
        schedule.recipients.set(recipients)
        schedule.update_schedule()
        return schedule


class ReportExecutionLogSerializer(serializers.ModelSerializer):
    """Serializer for the ReportExecutionLog model."""
    report = ReportSerializer(read_only=True)
    scheduled_run = ReportScheduleSerializer(read_only=True)
    created_by = UserSerializer(read_only=True)
    duration = serializers.SerializerMethodField()
    file_size_display = serializers.SerializerMethodField()
    
    class Meta:
        model = ReportExecutionLog
        fields = [
            'id', 'report', 'scheduled_run', 'started_at', 'completed_at',
            'status', 'error_message', 'file_path', 'file_size', 'file_size_display',
            'created_by', 'duration'
        ]
        read_only_fields = fields
    
    def get_duration(self, obj) -> Optional[float]:
        """Calculate the duration of the report execution in seconds."""
        if obj.started_at and obj.completed_at:
            return (obj.completed_at - obj.started_at).total_seconds()
        return None
    
    def get_file_size_display(self, obj) -> str:
        """Format the file size for display."""
        if not obj.file_size:
            return "N/A"
        size_kb = obj.file_size / 1024
        if size_kb < 1024:
            return f"{size_kb:.1f} KB"
        return f"{size_kb/1024:.1f} MB"


class ReportDataSerializer(serializers.Serializer):
    """Serializer for report data filtering."""
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    time_period = serializers.ChoiceField(
        choices=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('this_week', 'This Week'),
            ('last_week', 'Last Week'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
            ('this_quarter', 'This Quarter'),
            ('last_quarter', 'Last Quarter'),
            ('this_year', 'This Year'),
            ('last_year', 'Last Year'),
            ('custom', 'Custom Date Range')
        ],
        default='this_week'
    )
    
    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and set date ranges based on time period."""
        time_period = attrs.get('time_period', 'this_week')
        now = timezone.now()
        
        if time_period == 'today':
            attrs['start_date'] = now.replace(hour=0, minute=0, second=0, microsecond=0)
            attrs['end_date'] = now
        elif time_period == 'yesterday':
            yesterday = now - timedelta(days=1)
            attrs['start_date'] = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            attrs['end_date'] = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif time_period == 'this_week':
            start = now - timedelta(days=now.weekday())
            attrs['start_date'] = start.replace(hour=0, minute=0, second=0, microsecond=0)
            attrs['end_date'] = now
        elif time_period == 'last_week':
            start = now - timedelta(days=now.weekday() + 7)
            end = start + timedelta(days=6)
            attrs['start_date'] = start.replace(hour=0, minute=0, second=0, microsecond=0)
            attrs['end_date'] = end.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif time_period == 'this_month':
            attrs['start_date'] = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            attrs['end_date'] = now
        elif time_period == 'last_month':
            first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            last_month_end = first_day - timedelta(days=1)
            attrs['start_date'] = last_month_end.replace(day=1)
            attrs['end_date'] = last_month_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif time_period == 'this_quarter':
            quarter = (now.month - 1) // 3
            attrs['start_date'] = now.replace(month=quarter * 3 + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
            attrs['end_date'] = now
        elif time_period == 'last_quarter':
            quarter = (now.month - 1) // 3
            if quarter == 0:
                last_quarter_start = now.replace(year=now.year-1, month=10, day=1)
                last_quarter_end = now.replace(year=now.year-1, month=12, day=31)
            else:
                last_quarter_start = now.replace(month=(quarter-1)*3 + 1, day=1)
                last_quarter_end = now.replace(month=quarter*3, day=1) - timedelta(days=1)
            attrs['start_date'] = last_quarter_start.replace(hour=0, minute=0, second=0, microsecond=0)
            attrs['end_date'] = last_quarter_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif time_period == 'this_year':
            attrs['start_date'] = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            attrs['end_date'] = now
        elif time_period == 'last_year':
            attrs['start_date'] = now.replace(year=now.year-1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            attrs['end_date'] = now.replace(year=now.year-1, month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        
        # For custom date range, ensure both dates are provided
        if time_period == 'custom':
            if 'start_date' not in attrs or 'end_date' not in attrs:
                raise serializers.ValidationError(
                    'Both start_date and end_date are required for custom date range.'
                )
        
        # Ensure end_date is not before start_date
        if 'start_date' in attrs and 'end_date' in attrs and attrs['start_date'] > attrs['end_date']:
            raise serializers.ValidationError(
                'end_date must be after start_date.'
            )
        
        return attrs
