"""Utility functions for the reporting app."""
from typing import Dict, Any
from django.contrib.auth import get_user_model
from apps.reporting.models import Report

User = get_user_model()

def get_report_data(report: Report, user) -> Dict[str, Any]:
    """
    Get report data based on the report configuration.
    
    Args:
        report: The report to generate data for
        user: The user requesting the report
        
    Returns:
        Dict containing the report data
    """
    # Implement your report data generation logic here
    # This is a placeholder - replace with actual implementation
    return {
        'report_id': report.id,
        'report_name': report.name,
        'generated_at': str(report.created_at),
        'data': []
    }
