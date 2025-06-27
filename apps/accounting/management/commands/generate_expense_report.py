from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum
from datetime import timedelta

from ...models import Expense
from apps.base.utils import send_email

class Command(BaseCommand):
    help = 'Generate and send expense reports'

    def add_arguments(self, parser):
        parser.add_argument('--period',choices=['daily', 'weekly', 'monthly'],default='daily',help='Report period (daily, weekly, or monthly)')
        parser.add_argument('--email',action='store_true',help='Send report via email')

    def handle(self, *args, **options):
        period = options['period']

        # Calculate date range based on period
        now = timezone.now()
        if period == 'daily':
            start_date = now.date()
            end_date = now.date()
        elif period == 'weekly':
            start_date = now.date() - timedelta(days=7)
            end_date = now.date()
        else:  # monthly
            start_date = now.replace(day=1).date()
            end_date = now.date()

        # Generate report data
        expenses = Expense.objects.filter(expense_date__range=[start_date, end_date]).select_related('category')
        # Calculate totals by category
        category_totals = expenses.values('category__name').annotate(total_amount=Sum('amount')).order_by('-total_amount')
        # Calculate overall totals
        total_expenses = expenses.count()
        total_amount = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
        # Format report
        report = f"Expense Report ({period.title()} Period)\nDate Range: {start_date} to {end_date}\nTotal Expenses: {total_expenses}\nTotal Amount: {total_amount:.2f}\nCategory Breakdown:\n"

        for category in category_totals:
            report += f"{category['category__name']}: {category['total_amount']:.2f}\n"

        # Print report
        self.stdout.write(report)

        # Send email if requested
        if options['email']:
            subject = f"Expense Report - {period.title()} Period"
            send_email(subject, report, options['email'])
            self.stdout.write("Report sent via email to "+options['email'])
