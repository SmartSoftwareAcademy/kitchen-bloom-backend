from django.utils import timezone
from django.db.models import Sum, Q
from .models import Revenue, Expense


class RevenueReportGenerator:
    """Generator for various revenue reports."""

    def __init__(self, start_date=None, end_date=None):
        """Initialize report generator with date range."""
        self.start_date = start_date or timezone.now().date()
        self.end_date = end_date or timezone.now().date()

    def get_daily_revenue_report(self):
        """Generate daily revenue report."""
        revenues = Revenue.objects.filter(revenue_date__gte=self.start_date,revenue_date__lte=self.end_date).order_by('revenue_date')

        daily_totals = revenues.values('revenue_date').annotate(total_amount=Sum('amount'),paid_amount=Sum('amount', filter=Q(status='paid')))

        return {'daily_totals': daily_totals,'total_revenue': revenues.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}

    def get_category_revenue_report(self):
        """Generate revenue report by category."""
        revenues = Revenue.objects.filter(revenue_date__gte=self.start_date,revenue_date__lte=self.end_date)

        category_totals = revenues.values('category__name', 'category__description').annotate(total_amount=Sum('amount'),paid_amount=Sum('amount', filter=Q(status='paid'))).order_by('-total_amount')

        return {'category_totals': category_totals,'total_revenue': revenues.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}

    def get_account_revenue_report(self):
        """Generate revenue report by account."""
        revenues = Revenue.objects.filter(revenue_date__gte=self.start_date,revenue_date__lte=self.end_date)

        account_totals = revenues.values('account__code', 'account__name', 'account__account_type').annotate(total_amount=Sum('amount'),paid_amount=Sum('amount', filter=Q(status='paid'))).order_by('-total_amount')

        return {'account_totals': account_totals,'total_revenue': revenues.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}

    def get_monthly_revenue_trend(self):
        """Generate monthly revenue trend report."""
        revenues = Revenue.objects.filter(revenue_date__gte=self.start_date,revenue_date__lte=self.end_date)

        monthly_totals = revenues.extra({'month': "EXTRACT(month FROM revenue_date)",'year': "EXTRACT(year FROM revenue_date)"}).values('month', 'year').annotate(total_amount=Sum('amount'),paid_amount=Sum('amount', filter=Q(status='paid'))).order_by('year', 'month')

        return {'monthly_totals': monthly_totals,'total_revenue': revenues.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}

    def get_payment_method_report(self):
        """Generate revenue report by payment method."""
        revenues = Revenue.objects.filter(revenue_date__gte=self.start_date,revenue_date__lte=self.end_date)

        payment_method_totals = revenues.values('payment_method').annotate(total_amount=Sum('amount'),paid_count=Sum('amount', filter=Q(status='paid'))).order_by('-total_amount')

        return {'payment_method_totals': payment_method_totals,'total_revenue': revenues.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}

    def get_customer_revenue_report(self):
        """Generate revenue report by customer."""
        revenues = Revenue.objects.filter(revenue_date__gte=self.start_date,revenue_date__lte=self.end_date)
        customer_totals = revenues.values('customer__name', 'customer__email').annotate(total_amount=Sum('amount'),paid_amount=Sum('amount', filter=Q(status='paid'))).order_by('-total_amount')

        return {'customer_totals': customer_totals,'total_revenue': revenues.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}

class ExpenseReportGenerator:
    """Generator for various expense reports."""

    def __init__(self, start_date=None, end_date=None):
        """Initialize report generator with date range."""
        self.start_date = start_date or timezone.now().date()
        self.end_date = end_date or timezone.now().date()
        
    def get_daily_expense_report(self):
        """Generate daily expense report."""
        expenses = Expense.objects.filter(expense_date__gte=self.start_date,expense_date__lte=self.end_date).order_by('expense_date')
        daily_totals = expenses.values('expense_date').annotate(total_amount=Sum('amount'),paid_amount=Sum('amount', filter=Q(status='paid')))
        return {'daily_totals': daily_totals,'total_expense': expenses.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}

    def get_category_expense_report(self):
        """Generate expense report by category."""
        expenses = Expense.objects.filter(expense_date__gte=self.start_date,expense_date__lte=self.end_date)
        category_totals = expenses.values('category__name', 'category__description').annotate(total_amount=Sum('amount'),paid_amount=Sum('amount', filter=Q(status='paid'))).order_by('-total_amount')
        return {'category_totals': category_totals,'total_expense': expenses.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}

    def get_account_expense_report(self):
        """Generate expense report by account."""
        expenses = Expense.objects.filter(expense_date__gte=self.start_date,expense_date__lte=self.end_date)
        account_totals = expenses.values('account__code', 'account__name', 'account__account_type').annotate(total_amount=Sum('amount'),paid_amount=Sum('amount', filter=Q(status='paid'))).order_by('-total_amount')
        return {'account_totals': account_totals,'total_expense': expenses.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}

    def get_monthly_expense_trend(self):
        """Generate monthly expense trend report."""
        expenses = Expense.objects.filter(expense_date__gte=self.start_date,expense_date__lte=self.end_date)
        monthly_totals = expenses.extra({'month': "EXTRACT(month FROM expense_date)",'year': "EXTRACT(year FROM expense_date)"}).values('month', 'year').annotate(total_amount=Sum('amount'),paid_amount=Sum('amount', filter=Q(status='paid'))).order_by('year', 'month')
        return {'monthly_totals': monthly_totals,'total_expense': expenses.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}

    def get_payment_method_report(self):
        """Generate expense report by payment method."""
        expenses = Expense.objects.filter(expense_date__gte=self.start_date,expense_date__lte=self.end_date)
        payment_method_totals = expenses.values('payment_method').annotate(total_amount=Sum('amount'),paid_count=Sum('amount', filter=Q(status='paid'))).order_by('-total_amount')
        return {'payment_method_totals': payment_method_totals,'total_expense': expenses.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}

    def get_customer_expense_report(self):
        """Generate expense report by customer."""
        expenses = Expense.objects.filter(expense_date__gte=self.start_date,expense_date__lte=self.end_date)
        customer_totals = expenses.values('customer__name', 'customer__email').annotate(total_amount=Sum('amount'),paid_amount=Sum('amount', filter=Q(status='paid'))).order_by('-total_amount')
        return {'customer_totals': customer_totals,'total_expense': expenses.aggregate(total=Sum('amount'),paid=Sum('amount', filter=Q(status='paid')))}