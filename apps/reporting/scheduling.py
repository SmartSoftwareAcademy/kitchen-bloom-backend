from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import pytz
from django.conf import settings
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.utils import timezone
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule
from .models import Report, ReportSchedule, ReportExecutionLog
from .tasks import generate_report_async


class ReportScheduler:
    """Class for managing report scheduling and automation."""
    
    def create_schedule(self, report: Report, frequency: str, interval: int,
                       time: Optional[str] = None, recipients: Optional[List[str]] = None) -> ReportSchedule:
        """
        Create a new report schedule.
        
        Args:
            report: The report to schedule
            frequency: Frequency type (daily, weekly, monthly, etc.)
            interval: Interval value
            time: Time of day to run (HH:MM)
            recipients: List of email recipients
            
        Returns:
            The created ReportSchedule instance
        """
        # Create the schedule in Django Celery Beat
        if frequency == 'daily':
            schedule, _ = CrontabSchedule.objects.get_or_create(
                hour=int(time.split(':')[0]),
                minute=int(time.split(':')[1]),
                timezone=settings.TIME_ZONE
            )
        elif frequency == 'weekly':
            schedule, _ = CrontabSchedule.objects.get_or_create(
                day_of_week=0,  # Monday
                hour=int(time.split(':')[0]),
                minute=int(time.split(':')[1]),
                timezone=settings.TIME_ZONE
            )
        elif frequency == 'monthly':
            schedule, _ = CrontabSchedule.objects.get_or_create(
                day_of_month=1,
                hour=int(time.split(':')[0]),
                minute=int(time.split(':')[1]),
                timezone=settings.TIME_ZONE
            )
        else:
            raise ValueError(f"Unsupported frequency: {frequency}")
        
        # Create periodic task
        task_name = f"report_{report.id}_schedule_{frequency}"
        periodic_task = PeriodicTask.objects.create(
            name=task_name,
            task='reporting.tasks.generate_scheduled_report',
            crontab=schedule,
            args=[report.id],
            enabled=True
        )
        
        # Create report schedule
        report_schedule = ReportSchedule.objects.create(
            report=report,
            frequency=frequency,
            interval=interval,
            time=time,
            periodic_task=periodic_task,
            recipients=recipients or []
        )
        
        return report_schedule
    
    def update_schedule(self, schedule_id: int, **kwargs) -> ReportSchedule:
        """
        Update an existing report schedule.
        
        Args:
            schedule_id: ID of the schedule to update
            kwargs: Fields to update
            
        Returns:
            The updated ReportSchedule instance
        """
        schedule = ReportSchedule.objects.get(id=schedule_id)
        
        # Update periodic task if time or frequency changed
        if 'frequency' in kwargs or 'time' in kwargs:
            frequency = kwargs.get('frequency', schedule.frequency)
            time = kwargs.get('time', schedule.time)
            
            # Create new crontab schedule
            if frequency == 'daily':
                new_schedule, _ = CrontabSchedule.objects.get_or_create(
                    hour=int(time.split(':')[0]),
                    minute=int(time.split(':')[1]),
                    timezone=settings.TIME_ZONE
                )
            elif frequency == 'weekly':
                new_schedule, _ = CrontabSchedule.objects.get_or_create(
                    day_of_week=0,
                    hour=int(time.split(':')[0]),
                    minute=int(time.split(':')[1]),
                    timezone=settings.TIME_ZONE
                )
            elif frequency == 'monthly':
                new_schedule, _ = CrontabSchedule.objects.get_or_create(
                    day_of_month=1,
                    hour=int(time.split(':')[0]),
                    minute=int(time.split(':')[1]),
                    timezone=settings.TIME_ZONE
                )
            
            # Update periodic task
            schedule.periodic_task.crontab = new_schedule
            schedule.periodic_task.save()
            
        # Update schedule fields
        for field, value in kwargs.items():
            setattr(schedule, field, value)
        
        schedule.save()
        return schedule
    
    def delete_schedule(self, schedule_id: int) -> None:
        """
        Delete a report schedule and its associated periodic task.
        
        Args:
            schedule_id: ID of the schedule to delete
        """
        schedule = ReportSchedule.objects.get(id=schedule_id)
        
        # Delete periodic task
        if schedule.periodic_task:
            schedule.periodic_task.delete()
        
        # Delete schedule
        schedule.delete()
    
    def run_scheduled_report(self, report_id: int, schedule_id: int) -> None:
        """
        Run a scheduled report and handle delivery.
        
        Args:
            report_id: ID of the report to generate
            schedule_id: ID of the schedule that triggered this run
        """
        try:
            report = Report.objects.get(id=report_id)
            schedule = ReportSchedule.objects.get(id=schedule_id)
            
            # Create execution log
            execution_log = ReportExecutionLog.objects.create(
                report=report,
                schedule=schedule,
                status='processing',
                created_by=schedule.created_by
            )
            
            # Generate the report
            generate_report_async.delay(
                report_id=report_id,
                user_id=schedule.created_by_id,
                execution_log_id=execution_log.id,
                schedule_id=schedule_id
            )
            
        except Exception as e:
            # Log error and notify admins
            self._notify_admins(
                f"Failed to run scheduled report {report_id}",
                str(e)
            )
    
    def _notify_admins(self, subject: str, message: str) -> None:
        """Send notification to system administrators."""
        admins = settings.ADMINS
        if not admins:
            return
            
        email = EmailMessage(
            subject=f"[Reporting System] {subject}",
            body=message,
            to=[admin[1] for admin in admins]
        )
        email.send()
    
    def _send_report_email(self, report: Report, execution_log: ReportExecutionLog,
                         recipients: List[str]) -> None:
        """Send report via email to recipients."""
        if not recipients:
            return
            
        # Get report file path
        file_path = execution_log.file_path
        if not file_path:
            return
            
        # Create email
        subject = f"{report.name} Report - {execution_log.created_at.strftime('%Y-%m-%d')}"
        context = {
            'report_name': report.name,
            'report_type': report.report_type,
            'execution_date': execution_log.created_at,
            'status': execution_log.status
        }
        
        # Render email template
        body = render_to_string('reporting/email/report_notification.html', context)
        
        email = EmailMessage(
            subject=subject,
            body=body,
            to=recipients
        )
        
        # Attach report file
        with open(file_path, 'rb') as f:
            email.attach(
                f"{report.name}_{execution_log.created_at.strftime('%Y%m%d')}.{report.format.lower()}",
                f.read(),
                'application/octet-stream'
            )
        
        email.send()
    
    def _generate_report_delivery(self, execution_log: ReportExecutionLog) -> None:
        """Generate report delivery based on schedule preferences."""
        if not execution_log.schedule:
            return
            
        # Get delivery preferences
        schedule = execution_log.schedule
        delivery_methods = schedule.delivery_methods or []
        
        # Handle email delivery
        if 'email' in delivery_methods and schedule.recipients:
            self._send_report_email(
                report=schedule.report,
                execution_log=execution_log,
                recipients=schedule.recipients
            )
            
        # Add other delivery methods here (e.g., Slack, Teams, etc.)
        
        # Update execution log with delivery status
        execution_log.delivery_status = 'completed'
        execution_log.save(update_fields=['delivery_status'])
