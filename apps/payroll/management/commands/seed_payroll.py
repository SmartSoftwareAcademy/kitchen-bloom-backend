import random
from datetime import timedelta
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth import get_user_model
from apps.employees.models import Employee
from apps.payroll.models import (
    PayrollPeriod, EmployeePayroll, PayrollItem
)
from apps.accounting.models import Expense, ExpenseCategory, ExpenseAccount
from apps.branches.models import Branch
from apps.accounting.utils import generate_number

User = get_user_model()

class Command(BaseCommand):
    help = 'Robustly seed payroll data for development and testing.'

    def add_arguments(self, parser):
        parser.add_argument('--months', type=int, default=3, help='Number of past months to generate payroll for (default: 3)')
        parser.add_argument('--admin-email', type=str, default='admin@example.com', help='Email of admin user to associate with created periods')

    def handle(self, *args, **options):
        months = options['months']
        admin_email = options['admin_email']
        now = timezone.now().date()

        # Purge all payroll and related expense data
        self.stdout.write(self.style.WARNING('Deleting all payroll, payroll item, and related expense data...'))
        EmployeePayroll.objects.all().delete()
        PayrollPeriod.objects.all().delete()
        PayrollItem.objects.all().delete()
        Expense.objects.filter(expense_type='payroll').delete()
        self.stdout.write(self.style.SUCCESS('All payroll and related expense data deleted.'))

        # Ensure admin user and employee profile
        try:
            admin = User.objects.get(email=admin_email)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f"Admin user with email {admin_email} not found. Please create one."))
            return
        if not hasattr(admin, 'employee_profile'):
            base_id = 'ADMIN001'
            employee_id = base_id
            counter = 1
            while Employee.objects.filter(employee_id=employee_id).exists():
                counter += 1
                employee_id = f'{base_id}{counter}'
            Employee.objects.create(user=admin, employee_id=employee_id, is_active=True)
            self.stdout.write(self.style.WARNING(f"Created missing Employee profile for admin user {admin.email} (employee_id={employee_id})"))
        admin_emp = admin.employee_profile

        # Ensure at least one active employee
        employees = Employee.objects.exclude(user__is_superuser=True)
        if not employees:
            self.stdout.write(self.style.ERROR('No active employees found. Please seed employees first.'))
            return

        # Create or get payroll expense account and category
        expense_account, _ = ExpenseAccount.objects.get_or_create(
            code='PAYROLL',
            defaults={
                'name': 'Payroll Expenses',
                'account_type': 'operating',
                'description': 'Payroll and salary related expenses',
                'is_active': True
            }
        )
        expense_category, _ = ExpenseCategory.objects.get_or_create(
            name='Payroll',
            defaults={
                'description': 'Payroll and salary expenses',
                'is_active': True,
                'default_account': expense_account
            }
        )
        if not expense_category.default_account:
            expense_category.default_account = expense_account
            expense_category.save()

        # Fetch default branch or first branch
        default_branch = Branch.objects.filter(is_default=True).first() or Branch.objects.first()
        if not default_branch:
            self.stdout.write(self.style.ERROR('No branches found. Please seed branches first.'))
            return

        # Seed payroll periods with status 'approved'
        periods = []
        for i in range(months):
            period_date = now.replace(day=1) - timedelta(days=30 * i)
            period_start = period_date.replace(day=1)
            if period_start.month == 12:
                period_end = period_start.replace(year=period_start.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                period_end = period_start.replace(month=period_start.month + 1, day=1) - timedelta(days=1)
            period, created = PayrollPeriod.objects.get_or_create(
                start_date=period_start,
                end_date=period_end,
                defaults={
                    'status': 'approved',
                    'created_by': admin_emp,
                    'last_modified_by': admin_emp
                }
            )
            if not created:
                period.status = 'approved'
                period.save()
            periods.append(period)
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created payroll period: {period}'))

        # Seed payroll items for each employee (basic salary only)
        for emp in employees:
            # Create a basic salary payroll item if not exists
            basic_item, _ = PayrollItem.objects.get_or_create(
                name='Basic Salary',
                item_type='salary',
                defaults={
                    'amount': emp.salary or 0,
                    'is_percentage': False,
                    'is_tax_deductible': False,
                    'created_by': admin_emp,
                    'last_modified_by': admin_emp
                }
            )

        # Seed employee payrolls for each period and employee, with status 'paid', and link an Expense
        for period in periods:
            for emp in employees:
                try:
                    basic_salary = emp.salary or 0
                    gross_pay = basic_salary
                    total_deductions = Decimal('0.00')
                    net_pay = gross_pay - total_deductions
                    payment_date = period.end_date
                    payment_method = 'bank_transfer'
                    payment_reference = f'PAY-{emp.employee_id}-{period.start_date}'
                    # Create expense
                    expense = Expense(
                        expense_date=payment_date,
                        payment_date=payment_date,
                        amount=net_pay,
                        currency='KES',
                        description=f"Salary payment for {emp} ({period})",
                        payment_method=payment_method,
                        payment_reference=payment_reference,
                        status='paid',
                        category=expense_category,
                        expense_type='payroll',
                        employee=emp,
                        branch=default_branch,
                        created_by=admin,
                        last_modified_by=admin,
                    )
                    expense.expense_number = generate_number('EX')
                    expense.save()
                    emp_payroll, created = EmployeePayroll.objects.get_or_create(
                        employee=emp,
                        payroll_period=period,
                        defaults={
                            'basic_salary': basic_salary,
                            'gross_pay': gross_pay,
                            'total_deductions': total_deductions,
                            'net_pay': net_pay,
                            'status': 'paid',
                            'payment_date': payment_date,
                            'payment_method': payment_method,
                            'payment_reference': payment_reference,
                            'created_by': admin_emp,
                            'last_modified_by': admin_emp,
                            'expense': expense
                        }
                    )
                    if not created:
                        emp_payroll.basic_salary = basic_salary
                        emp_payroll.gross_pay = gross_pay
                        emp_payroll.total_deductions = total_deductions
                        emp_payroll.net_pay = net_pay
                        emp_payroll.status = 'paid'
                        emp_payroll.payment_date = payment_date
                        emp_payroll.payment_method = payment_method
                        emp_payroll.payment_reference = payment_reference
                        emp_payroll.expense = expense
                        emp_payroll.save()
                    self.stdout.write(self.style.SUCCESS(f'Created payroll and expense for {emp} - {period}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'Error creating payroll for {emp} - {period}: {str(e)}'))

        self.stdout.write(self.style.SUCCESS('Payroll seeding complete.'))
