from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import date, timedelta
from apps.accounting.models import Expense, GiftCard, ExpenseCategory
from apps.employees.models import Employee
from apps.branches.models import Branch
from apps.crm.models import Customer
from django.contrib.auth import get_user_model
from django.db.models import Sum
import decimal

User = get_user_model()

class Command(BaseCommand):
    help = 'Unified accounting seeder and management command.'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear all accounting data before seeding')
        parser.add_argument('--payroll', action='store_true', help='Seed payroll expenses')
        parser.add_argument('--expense-report', action='store_true', help='Generate expense report')
        parser.add_argument('--update-expenses', action='store_true', help='Update expense statuses')
        parser.add_argument('--gift-cards', type=int, default=0, help='Number of gift cards to generate')
        parser.add_argument('--gift-value', type=decimal.Decimal, default=1000, help='Value for each gift card')
        parser.add_argument('--gift-currency', type=str, default='KES', help='Currency for gift cards')
        parser.add_argument('--gift-expires-in', type=int, default=365, help='Days until gift card expires')

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing all accounting data...'))
            Expense.objects.all().delete()
            GiftCard.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Accounting data cleared.'))

        if options['payroll']:
            self.stdout.write(self.style.WARNING('Seeding payroll expenses...'))
            month = timezone.now().month
            year = timezone.now().year
            start_date = date(year, month, 1)
            end_date = (start_date.replace(day=28) + timedelta(days=4))
            end_date = end_date - timedelta(days=end_date.day)
            employees = Employee.objects.all()
            payroll_category, _ = ExpenseCategory.objects.get_or_create(name='Payroll', defaults={'description': 'Payroll Expenses'})
            for employee in employees:
                if not getattr(employee, 'salary', None):
                    continue
                expense = Expense.objects.create(
                    expense_date=end_date,
                    amount=employee.salary,
                    currency='KES',
                    description=f'Salary Payment for {employee}',
                    expense_type='payroll',
                    category=payroll_category,
                    payment_method='bank_transfer',
                    branch=employee.branch,
                    employee=employee,
                    status='approved',
                    approved_by=getattr(employee.branch, 'manager', None),
                    approved_at=timezone.now()
                )
                self.stdout.write(f"Created salary payment expense for {employee}: {employee.salary}")
            self.stdout.write(self.style.SUCCESS('Payroll seeding complete.'))

        if options['expense_report']:
            self.stdout.write(self.style.WARNING('Generating expense report...'))
            now = timezone.now()
            start_date = now.replace(day=1).date()
            end_date = now.date()
            expenses = Expense.objects.filter(expense_date__range=[start_date, end_date]).select_related('category')
            category_totals = expenses.values('category__name').annotate(total_amount=Sum('amount')).order_by('-total_amount')
            total_expenses = expenses.count()
            total_amount = expenses.aggregate(Sum('amount'))['amount__sum'] or 0
            report = f"Expense Report (Monthly)\nDate Range: {start_date} to {end_date}\nTotal Expenses: {total_expenses}\nTotal Amount: {total_amount:.2f}\nCategory Breakdown:\n"
            for category in category_totals:
                report += f"{category['category__name']}: {category['total_amount']:.2f}\n"
            self.stdout.write(report)

        if options['update_expenses']:
            self.stdout.write(self.style.WARNING('Updating expense statuses...'))
            from datetime import timedelta
            expenses = Expense.objects.filter(status__in=['draft', 'submitted', 'approved']).select_related('branch')
            today = timezone.now().date()
            updates = 0
            for expense in expenses:
                if expense.status == 'submitted' and expense.expense_date <= today - timedelta(days=7):
                    expense.status = 'approved'
                    expense.approved_by = getattr(expense.branch, 'manager', None)
                    expense.approved_at = timezone.now()
                    expense.save()
                    self.stdout.write(f"Auto-approved expense {expense.expense_number}")
                    updates += 1
                elif expense.status == 'submitted' and expense.expense_date <= today - timedelta(days=30):
                    expense.status = 'rejected'
                    expense.notes = 'Auto-rejected due to lack of approval'
                    expense.save()
                    self.stdout.write(f"Auto-rejected expense {expense.expense_number}")
                    updates += 1
            self.stdout.write(self.style.SUCCESS(f'Total updates: {updates}'))

        if options['gift_cards'] > 0:
            self.stdout.write(self.style.WARNING(f'Generating {options["gift_cards"]} gift cards...'))
            staff_user = User.objects.filter(is_staff=True).first()
            if not staff_user:
                raise CommandError('No staff users found. Please create a staff user first.')
            for i in range(options['gift_cards']):
                from apps.accounting.models import GiftCard
                import random, string
                length = 8
                prefix = 'GC'
                while True:
                    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
                    code = f"{prefix}{random_part}"
                    if not GiftCard.objects.filter(code=code).exists():
                        break
                expiry_date = timezone.now() + timedelta(days=options['gift_expires_in']) if options['gift_expires_in'] > 0 else None
                gift_card = GiftCard.objects.create(
                    code=code,
                    initial_value=options['gift_value'],
                    current_balance=options['gift_value'],
                    currency=options['gift_currency'],
                    status='active',
                    issued_by=staff_user,
                    expiry_date=expiry_date,
                    notes=f'Generated by unified seeder on {timezone.now().strftime("%Y-%m-%d %H:%M:%S")}'
                )
                self.stdout.write(self.style.SUCCESS(f'Created gift card {code}: {options["gift_currency"]} {options["gift_value"]:.2f} (Expires: {expiry_date.strftime("%Y-%m-%d") if expiry_date else "Never"})'))
            self.stdout.write(self.style.SUCCESS(f'Successfully created {options["gift_cards"]} gift cards')) 