"""Utility functions for the payroll app."""
from datetime import date, timedelta
from django.utils import timezone
from django.db.models import Q

from .models import PayrollPeriod

def get_or_create_payroll_period(start_date, end_date, branch=None, created_by=None):
    """
    Find an existing payroll period for the given date range and branch,
    or create a new one if none exists.
    
    Args:
        start_date (date): Start date of the period
        end_date (date): End date of the period
        branch (Branch, optional): Branch for the period. Defaults to None (company-wide).
        created_by (Employee, optional): Employee creating the period. Defaults to None.
    
    Returns:
        PayrollPeriod: The found or created payroll period
    """
    # Try to find an existing period that matches the criteria
    period = PayrollPeriod.objects.filter(
        start_date=start_date,
        end_date=end_date,
        branch=branch
    ).first()
    
    # If no period exists, create a new one
    if not period:
        period = PayrollPeriod.objects.create(
            start_date=start_date,
            end_date=end_date,
            branch=branch,
            status='draft',
            created_by=created_by
        )
    
    return period

def get_current_payroll_period(branch=None):
    """
    Get the current payroll period based on today's date.
    
    Args:
        branch (Branch, optional): Branch to filter by. Defaults to None.
    
    Returns:
        PayrollPeriod or None: The current payroll period if found, else None
    """
    today = timezone.now().date()
    
    # Look for a period that includes today's date
    period = PayrollPeriod.objects.filter(
        start_date__lte=today,
        end_date__gte=today,
        branch=branch
    ).first()
    
    return period

def get_last_payroll_period(branch=None):
    """
    Get the most recent payroll period that has ended.
    
    Args:
        branch (Branch, optional): Branch to filter by. Defaults to None.
    
    Returns:
        PayrollPeriod or None: The most recent payroll period if found, else None
    """
    today = timezone.now().date()
    
    period = PayrollPeriod.objects.filter(
        end_date__lt=today,
        branch=branch
    ).order_by('-end_date').first()
    
    return period

def get_next_payroll_period(branch=None):
    """
    Get the next upcoming payroll period.
    
    Args:
        branch (Branch, optional): Branch to filter by. Defaults to None.
    
    Returns:
        PayrollPeriod or None: The next payroll period if found, else None
    """
    today = timezone.now().date()
    
    period = PayrollPeriod.objects.filter(
        start_date__gt=today,
        branch=branch
    ).order_by('start_date').first()
    
    return period

def create_next_payroll_period(branch=None, created_by=None):
    """
    Create the next payroll period based on the last period's end date.
    
    Args:
        branch (Branch, optional): Branch for the period. Defaults to None.
        created_by (Employee, optional): Employee creating the period. Defaults to None.
    
    Returns:
        PayrollPeriod: The newly created payroll period
    """
    # Get the most recent period
    last_period = PayrollPeriod.objects.filter(
        branch=branch
    ).order_by('-end_date').first()
    
    if last_period:
        # Calculate next period (1 day after last period ends)
        start_date = last_period.end_date + timedelta(days=1)
        # Default to 2 weeks (can be adjusted as needed)
        end_date = start_date + timedelta(weeks=2) - timedelta(days=1)
    else:
        # No periods exist yet, create first period
        today = timezone.now().date()
        start_date = today.replace(day=1)  # Start of current month
        # End of current month
        if start_date.month == 12:
            end_date = start_date.replace(year=start_date.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            end_date = start_date.replace(month=start_date.month + 1, day=1) - timedelta(days=1)
    
    # Create the new period
    period = PayrollPeriod.objects.create(
        start_date=start_date,
        end_date=end_date,
        branch=branch,
        status='draft',
        created_by=created_by
    )
    
    return period
