from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta

from ...models import Expense
from apps.employees.models import Employee
from apps.branches.models import Branch


class Command(BaseCommand):
    help = 'Generate monthly payroll expenses'

    def add_arguments(self, parser):
        parser.add_argument('--month', type=int, default=None, help='Month number (1-12)')
        parser.add_argument('--year', type=int, default=None, help='Year')
        parser.add_argument('--branch', type=int, default=None, help='Branch ID')

    def handle(self, *args, **options):
        month = options['month'] or timezone.now().month
        year = options['year'] or timezone.now().year
        branch_id = options['branch']

        # Calculate date range for the month
        start_date = date(year, month, 1)
        end_date = (start_date.replace(day=28) + timedelta(days=4))
        end_date = end_date - timedelta(days=end_date.day)

        # Get all employees
        employees = Employee.objects.all()
        if branch_id:
            employees = employees.filter(branch_id=branch_id)

        # Create payroll expenses
        for employee in employees:
            # Skip if employee has no salary
            if not employee.salary:
                continue

            # Create expense
            expense = Expense.objects.create(
                expense_date=end_date,
                amount=employee.salary,
                currency='KES',
                description=f'Salary Payment for {employee.name} ({employee.position})',
                expense_type='payroll',
                category_id=1,  # TODO: Create or get payroll category
                payment_method='bank_transfer',
                branch=employee.branch,
                employee=employee,
                status='approved',  # Payroll is auto-approved
                approved_by=employee.branch.manager,  # TODO: Get branch manager
                approved_at=timezone.now()
            )

            self.stdout.write(f"Created salary payment expense for {employee.name}: {employee.salary}")

        self.stdout.write("Salary Payment generation complete")
