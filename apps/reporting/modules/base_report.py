from abc import ABC, abstractmethod
from datetime import datetime, date, timedelta
from typing import Dict, List, Any, Optional, Union
from enum import Enum
from django.db.models import QuerySet, Sum, Count, F, Value, Case, When, Q
from django.db.models.functions import Coalesce, TruncDate, TruncDay, TruncWeek, TruncMonth, TruncQuarter, TruncYear
from django.utils import timezone


class TimePeriod(Enum):
    TODAY = 'today'
    YESTERDAY = 'yesterday'
    LAST_7_DAYS = 'last_7_days'
    LAST_30_DAYS = 'last_30_days'
    THIS_MONTH = 'this_month'
    LAST_MONTH = 'last_month'
    THIS_QUARTER = 'this_quarter'
    LAST_QUARTER = 'last_quarter'
    THIS_YEAR = 'this_year'
    LAST_YEAR = 'last_year'
    CUSTOM = 'custom'


class BaseReport(ABC):
    """Base class for all report generators."""
    
    def __init__(self, start_date: Optional[datetime] = None, end_date: Optional[datetime] = None):
        """Initialize the report with optional date range."""
        self.start_date = start_date
        self.end_date = end_date or timezone.now()
        self.time_period = None
    
    def set_time_period(self, period: str, custom_start: Optional[datetime] = None, 
                        custom_end: Optional[datetime] = None) -> None:
        """Set the time period for the report."""
        self.time_period = TimePeriod(period.lower())
        now = timezone.now()
        
        if self.time_period == TimePeriod.TODAY:
            self.start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self.end_date = now
        elif self.time_period == TimePeriod.YESTERDAY:
            yesterday = now - timedelta(days=1)
            self.start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            self.end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif self.time_period == TimePeriod.LAST_7_DAYS:
            self.start_date = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
            self.end_date = now
        elif self.time_period == TimePeriod.LAST_30_DAYS:
            self.start_date = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
            self.end_date = now
        elif self.time_period == TimePeriod.THIS_MONTH:
            self.start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            self.end_date = now
        elif self.time_period == TimePeriod.LAST_MONTH:
            first_day = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            self.end_date = first_day - timedelta(days=1)
            self.start_date = self.end_date.replace(day=1)
        elif self.time_period == TimePeriod.THIS_QUARTER:
            quarter = (now.month - 1) // 3
            self.start_date = now.replace(month=quarter*3+1, day=1, hour=0, minute=0, second=0, microsecond=0)
            self.end_date = now
        elif self.time_period == TimePeriod.LAST_QUARTER:
            quarter = (now.month - 1) // 3
            if quarter == 0:
                self.start_date = now.replace(year=now.year-1, month=10, day=1, hour=0, minute=0, second=0, microsecond=0)
                self.end_date = now.replace(year=now.year-1, month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
            else:
                self.start_date = now.replace(month=(quarter-1)*3+1, day=1, hour=0, minute=0, second=0, microsecond=0)
                self.end_date = (now.replace(month=quarter*3+1, day=1) - timedelta(days=1)).replace(hour=23, minute=59, second=59, microsecond=999999)
        elif self.time_period == TimePeriod.THIS_YEAR:
            self.start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            self.end_date = now
        elif self.time_period == TimePeriod.LAST_YEAR:
            self.start_date = now.replace(year=now.year-1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
            self.end_date = now.replace(year=now.year-1, month=12, day=31, hour=23, minute=59, second=59, microsecond=999999)
        elif self.time_period == TimePeriod.CUSTOM and custom_start and custom_end:
            self.start_date = custom_start
            self.end_date = custom_end
        else:
            raise ValueError("Invalid time period or missing custom date range")
    
    def apply_date_filter(self, queryset, date_field: str) -> QuerySet:
        """Apply date range filter to a queryset."""
        if self.start_date and self.end_date:
            filter_kwargs = {
                f"{date_field}__gte": self.start_date,
                f"{date_field}__lte": self.end_date
            }
            return queryset.filter(**filter_kwargs)
        return queryset
    
    @abstractmethod
    def generate(self, *args, **kwargs) -> Dict[str, Any]:
        """Generate the report data. Must be implemented by subclasses."""
        pass
    
    def get_time_period_display(self) -> str:
        """Get a human-readable description of the time period."""
        if not self.time_period:
            return "Custom period"
        
        period_map = {
            TimePeriod.TODAY: "Today",
            TimePeriod.YESTERDAY: "Yesterday",
            TimePeriod.LAST_7_DAYS: "Last 7 Days",
            TimePeriod.LAST_30_DAYS: "Last 30 Days",
            TimePeriod.THIS_MONTH: "This Month",
            TimePeriod.LAST_MONTH: "Last Month",
            TimePeriod.THIS_QUARTER: "This Quarter",
            TimePeriod.LAST_QUARTER: "Last Quarter",
            TimePeriod.THIS_YEAR: "This Year",
            TimePeriod.LAST_YEAR: "Last Year",
            TimePeriod.CUSTOM: "Custom Period"
        }
        return period_map.get(self.time_period, "Custom Period")
