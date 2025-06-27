from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime

from ...models import Expense
from apps.branches.models import Branch


class Command(BaseCommand):
    help = 'Update expense statuses based on due dates and payment status'

    def add_arguments(self, parser):
        parser.add_argument(
            '--branch',
            type=int,
            default=None,
            help='Branch ID to process (optional)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without making any changes'
        )

    def handle(self, *args, **options):
        branch_id = options['branch']
        dry_run = options['dry_run']

        # Get all pending expenses
        expenses = Expense.objects.filter(
            status__in=['draft', 'submitted', 'approved']
        ).select_related('branch')

        if branch_id:
            expenses = expenses.filter(branch_id=branch_id)

        updates = 0
        today = timezone.now().date()

        for expense in expenses:
            # Auto-approve expenses after 7 days if not already approved
            if expense.status == 'submitted' and expense.expense_date <= today - timedelta(days=7):
                if not dry_run:
                    expense.status = 'approved'
                    expense.approved_by = expense.branch.manager  # TODO: Get branch manager
                    expense.approved_at = timezone.now()
                    expense.save()
                self.stdout.write(f"Auto-approved expense {expense.expense_number}")
                updates += 1

            # Auto-reject expenses after 30 days if not approved
            elif expense.status == 'submitted' and expense.expense_date <= today - timedelta(days=30):
                if not dry_run:
                    expense.status = 'rejected'
                    expense.notes = 'Auto-rejected due to lack of approval'
                    expense.save()
                self.stdout.write(f"Auto-rejected expense {expense.expense_number}")
                updates += 1

        self.stdout.write(f"Total updates: {updates}")
        if dry_run:
            self.stdout.write("This was a dry run - no changes were made")
