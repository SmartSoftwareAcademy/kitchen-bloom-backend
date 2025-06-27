from typing import Dict, Any, Optional, override
from decimal import Decimal
import polars as pl
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce
from .base_report import BaseReport
from apps.accounting.models import Expense, Revenue, GiftCard
from apps.payroll.models import EmployeePayroll
from apps.sales.models import Order, OrderItem, Payment
from apps.inventory.models import Product, BranchStock
from apps.branches.models import Branch
from apps.crm.models import Customer
from django.utils import timezone
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

class FinancialReportGenerator(BaseReport):
    """Generator for financial reports including expenses and profits."""

    @override
    def generate(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Generate the inventory report data.
        
        Returns:
            Dict containing inventory report data
        """
        return {
            'expense_report': self.generate_expense_report(),
            'payrol_report': self.generate_payroll_report(),
            'profit_report': self.generate_profit_report(),
            'cashflow_statement': self.generate_cashflow_statement(),
            'trial_balance': self.generate_trial_balance(),
            'balance_sheet': self.generate_balance_sheet(),
            'revenue_report': self.generate_revenue_report(),
            'todays_profit_summary': self.generate_todays_profit_summary()
        }
    
    def generate_expense_report(self, category_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a report of expenses.
        
        Args:
            category_id: Optional category ID to filter by
            
        Returns:
            Dict containing expense data
        """
        try:
            # Base queryset for expenses - include approved and paid expenses
            expenses = Expense.objects.filter(
                status__in=['approved', 'paid']
            ).select_related('category', 'approved_by')
            
            # Apply date range
            expenses = self.apply_date_filter(expenses, 'expense_date')
            
            # Apply category filter if provided
            if category_id:
                expenses = expenses.filter(category_id=category_id)
            
            # Calculate totals
            totals = expenses.aggregate(
                total_expenses=Coalesce(Sum('amount'), Decimal('0.00')),
                expense_count=Count('id')
            )
            
            # Calculate average expense
            avg_expense = (
                totals['total_expenses'] / totals['expense_count']
                if totals['expense_count'] > 0 else Decimal('0.00')
            )
            
            # Get expenses by category
            categories = expenses.values('category__name').annotate(
                total_amount=Sum('amount'),
                transaction_count=Count('id')
            ).order_by('-total_amount')
            
            return {
                'report_type': 'expense_report',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'categories': list(categories),
                'total_expenses': float(totals['total_expenses']),
                'expense_count': totals['expense_count'],
                'average_transaction': float(avg_expense)
            }
        except Exception as e:
            logger.error(f"Error generating expense report: {str(e)}")
            return {
                'report_type': 'expense_report',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'categories': [],
                'total_expenses': 0.0,
                'expense_count': 0,
                'average_transaction': 0.0,
                'error': str(e)
            }
    
    def generate_payroll_report(self, status: str = 'all', department_id: Optional[int] = None, employee_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a payroll report.
        
        Args:
            status: Payroll status filter (all, pending, approved, paid)
            department_id: Optional department ID to filter by
            employee_id: Optional employee ID to filter by
            
        Returns:
            Dict containing payroll data
        """
        try:
            # Base queryset for payrolls
            payrolls = EmployeePayroll.objects.select_related('approved_by', 'employee').prefetch_related('items')
            
            # Apply date range
            payrolls = self.apply_date_filter(payrolls, 'period_start')
            
            # Apply status filter
            if status.lower() != 'all':
                payrolls = payrolls.filter(status=status.upper())
            
            # Apply department filter
            if department_id:
                payrolls = payrolls.filter(employee__department_id=department_id)
            
            # Apply employee filter
            if employee_id:
                payrolls = payrolls.filter(employee_id=employee_id)
            
            # Convert to Polars DataFrame
            payroll_data = list(payrolls.values(
                'id', 'employee__first_name', 'employee__last_name', 
                'period_start', 'period_end', 'net_pay', 'status', 'employee_id'
            ))
            
            if not payroll_data:
                return {
                    'report_type': 'payroll_report',
                    'time_period': {'start': self.start_date, 'end': self.end_date},
                    'payrolls': [],
                    'totals': {
                        'total_amount': 0.0,
                        'payroll_count': 0,
                        'employee_count': 0,
                        'avg_pay': 0.0
                    }
                }
            
            df = pl.DataFrame(payroll_data)
            
            # Calculate totals using Polars expressions
            metrics = df.select([
                pl.col('net_pay').sum().alias('total_amount'),
                pl.count().alias('payroll_count'),
                pl.col('employee_id').n_unique().alias('employee_count'),
                (pl.col('net_pay').sum() / pl.count()).alias('avg_pay')
            ])
            
            # Format data
            formatted_payrolls = df.select([
                pl.concat_str(['employee__first_name', 'employee__last_name'], separator=' ').alias('employee'),
                pl.col('period_end').dt.strftime('%Y-%m-%d').alias('period'),
                pl.col('net_pay'),
                pl.col('status')
            ]).to_dicts()
            
            return {
                'report_type': 'payroll_report',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'payrolls': formatted_payrolls,
                'totals': {
                    'total_amount': float(metrics['total_amount'][0]),
                    'payroll_count': int(metrics['payroll_count'][0]),
                    'employee_count': int(metrics['employee_count'][0]),
                    'avg_pay': float(metrics['avg_pay'][0])
                }
            }
        except Exception as e:
            logger.error(f"Error generating payroll report: {str(e)}")
            return {
                'report_type': 'payroll_report',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'payrolls': [],
                'totals': {
                    'total_amount': 0.0,
                    'payroll_count': 0,
                    'employee_count': 0,
                    'avg_pay': 0.0
                },
                'error': str(e)
            }
    
    def generate_profit_report(self) -> Dict[str, Any]:
        """
        Generate a profit report (Sales - COGS - Expenses).
        
        Returns:
            Dict containing profit data
        """
        try:
            # Get sales data
            sales_data = self._get_sales_data()
            
            # Get COGS (Cost of Goods Sold)
            cogs_data = self._get_cogs_data()
            
            # Get expenses data
            expenses_data = self._get_expenses_data()
            
            # Calculate profit
            gross_profit = sales_data['total_sales'] - cogs_data['total_cogs']
            net_profit = gross_profit - expenses_data['total_expenses']
            
            # Calculate profit margins
            gross_margin = (gross_profit / sales_data['total_sales']) * 100 if sales_data['total_sales'] > 0 else 0
            net_margin = (net_profit / sales_data['total_sales']) * 100 if sales_data['total_sales'] > 0 else 0
            
            # Format data
            return {
                'report_type': 'profit_report',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'sales': {
                    'total_sales': float(sales_data['total_sales']),
                    'order_count': sales_data['order_count'],
                    'avg_order': float(sales_data['avg_order']) if sales_data['avg_order'] else 0.0
                },
                'cogs': {
                    'total_cogs': float(cogs_data['total_cogs']),
                    'cogs_percentage': (
                        float((cogs_data['total_cogs'] / sales_data['total_sales']) * 100) 
                        if sales_data['total_sales'] > 0 else 0.0
                    )
                },
                'gross_profit': {
                    'amount': float(gross_profit),
                    'margin': float(gross_margin)
                },
                'expenses': {
                    'total_expenses': float(expenses_data['total_expenses']),
                    'expense_categories': expenses_data['categories']
                },
                'net_profit': {
                    'amount': float(net_profit),
                    'margin': float(net_margin)
                }
            }
        except Exception as e:
            logger.error(f"Error generating profit report: {str(e)}")
            return {
                'report_type': 'profit_report',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'error': str(e)
            }
    
    def _get_sales_data(self) -> Dict[str, Any]:
        """Get sales data for the profit report."""
        # Get completed orders
        orders = Order.objects.filter(status=Order.Status.COMPLETED)
        
        # Apply date range
        orders = self.apply_date_filter(orders, 'created_at')
        
        # Calculate sales metrics
        sales_data = orders.aggregate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
            order_count=Count('id')
        )
        
        # Calculate average order value
        avg_order = (
            sales_data['total_sales'] / sales_data['order_count']
            if sales_data['order_count'] > 0 else Decimal('0.00')
        )
        
        return {
            'total_sales': sales_data['total_sales'],
            'order_count': sales_data['order_count'],
            'avg_order': avg_order
        }
    
    def _get_cogs_data(self) -> Dict[str, Any]:
        """Get Cost of Goods Sold data."""
        # Get completed order items with their costs
        order_items = OrderItem.objects.filter(
            order__status=Order.Status.COMPLETED
        ).select_related('order', 'menu_item', 'product')
        
        # Apply date range
        order_items = self.apply_date_filter(order_items, 'order__created_at')
        
        # Calculate total COGS
        total_cogs = Decimal('0.00')
        for item in order_items:
            if item.menu_item:
                # For menu items, calculate cost from ingredients
                cost = item.menu_item.cost_price * item.quantity
            elif item.product:
                # For products, use product cost
                cost = item.product.cost_price * item.quantity
            else:
                # Fallback to unit price if no cost available
                cost = item.unit_price * Decimal('0.6') * item.quantity  # Assume 60% cost ratio
            
            total_cogs += cost
        
        return {
            'total_cogs': total_cogs
        }
    
    def _get_expenses_data(self) -> Dict[str, Any]:
        """Get expenses data for the profit report."""
        # Get approved and paid expenses
        expenses = Expense.objects.filter(
            status__in=['approved', 'paid']
        ).select_related('category')
        
        # Apply date range
        expenses = self.apply_date_filter(expenses, 'expense_date')
        
        # Calculate total expenses
        total_expenses = expenses.aggregate(
            total=Coalesce(Sum('amount'), Decimal('0.00'))
        )['total']
        
        # Get expenses by category
        categories = expenses.values('category__name').annotate(
            total_amount=Sum('amount'),
            transaction_count=Count('id')
        ).order_by('-total_amount')
        
        return {
            'total_expenses': total_expenses,
            'categories': list(categories)
        }
    
    def generate_cashflow_statement(self) -> Dict[str, Any]:
        """
        Generate a cash flow statement showing operating, investing, and financing activities.
        
        Returns:
            Dict containing cash flow data
        """
        try:
            # Operating Activities
            operating_activities = self._get_operating_cash_flows()
            
            # Investing Activities (simplified - mainly inventory purchases)
            investing_activities = self._get_investing_cash_flows()
            
            # Financing Activities (simplified - mainly payroll)
            financing_activities = self._get_financing_cash_flows()
            
            # Calculate net cash flow
            net_cash_flow = (
                operating_activities['net_cash_flow'] +
                investing_activities['net_cash_flow'] +
                financing_activities['net_cash_flow']
            )
            
            return {
                'report_type': 'cashflow_statement',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'operating_activities': operating_activities,
                'investing_activities': investing_activities,
                'financing_activities': financing_activities,
                'net_cash_flow': float(net_cash_flow),
                'cash_flow_summary': {
                    'operating_cash_flow': float(operating_activities['net_cash_flow']),
                    'investing_cash_flow': float(investing_activities['net_cash_flow']),
                    'financing_cash_flow': float(financing_activities['net_cash_flow']),
                    'net_cash_flow': float(net_cash_flow)
                }
            }
        except Exception as e:
            logger.error(f"Error generating cashflow statement: {str(e)}")
            return {
                'report_type': 'cashflow_statement',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'error': str(e)
            }
    
    def generate_trial_balance(self) -> Dict[str, Any]:
        """
        Generate a trial balance showing all account balances.
        
        Returns:
            Dict containing trial balance data
        """
        try:
            # Get all revenue accounts and their balances
            revenue_accounts = self._get_revenue_account_balances()
            
            # Get all expense accounts and their balances
            expense_accounts = self._get_expense_account_balances()
            
            # Calculate totals
            total_debits = sum(account['balance'] for account in expense_accounts)
            total_credits = sum(account['balance'] for account in revenue_accounts)
            
            return {
                'report_type': 'trial_balance',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'revenue_accounts': revenue_accounts,
                'expense_accounts': expense_accounts,
                'totals': {
                    'total_debits': float(total_debits),
                    'total_credits': float(total_credits),
                    'difference': float(total_credits - total_debits)
                }
            }
        except Exception as e:
            logger.error(f"Error generating trial balance: {str(e)}")
            return {
                'report_type': 'trial_balance',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'error': str(e)
            }
    
    def generate_balance_sheet(self) -> Dict[str, Any]:
        """
        Generate a balance sheet showing assets, liabilities, and equity.
        
        Returns:
            Dict containing balance sheet data
        """
        try:
            # Assets
            current_assets = self._get_current_assets()
            fixed_assets = self._get_fixed_assets()
            total_assets = current_assets['total'] + fixed_assets['total']
            
            # Liabilities
            current_liabilities = self._get_current_liabilities()
            long_term_liabilities = self._get_long_term_liabilities()
            total_liabilities = current_liabilities['total'] + long_term_liabilities['total']
            
            # Equity
            equity = self._get_equity()
            
            return {
                'report_type': 'balance_sheet',
                'as_of_date': self.end_date,
                'assets': {
                    'current_assets': current_assets,
                    'fixed_assets': fixed_assets,
                    'total_assets': float(total_assets)
                },
                'liabilities': {
                    'current_liabilities': current_liabilities,
                    'long_term_liabilities': long_term_liabilities,
                    'total_liabilities': float(total_liabilities)
                },
                'equity': equity,
                'total_liabilities_and_equity': float(total_liabilities + equity['total_equity'])
            }
        except Exception as e:
            logger.error(f"Error generating balance sheet: {str(e)}")
            return {
                'report_type': 'balance_sheet',
                'as_of_date': self.end_date,
                'error': str(e)
            }
    
    def generate_revenue_report(self, category_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a detailed revenue report.
        
        Args:
            category_id: Optional category ID to filter by
            
        Returns:
            Dict containing revenue data
        """
        try:
            # Base queryset for revenues
            revenues = Revenue.objects.select_related('category', 'customer', 'branch')
            
            # Apply date range
            revenues = self.apply_date_filter(revenues, 'revenue_date')
            
            # Apply category filter if provided
            if category_id:
                revenues = revenues.filter(category_id=category_id)
            
            # Convert to Polars DataFrame
            data = list(revenues.values(
                'id', 'amount', 'category__name', 'revenue_type', 
                'payment_method', 'status', 'currency'
            ))
            
            if not data:
                return {
                    'report_type': 'revenue_report',
                    'time_period': {'start': self.start_date, 'end': self.end_date},
                    'categories': [],
                    'payment_methods': [],
                    'totals': {
                        'total_revenue': 0.0,
                        'revenue_count': 0,
                        'avg_revenue': 0.0
                    }
                }
            
            df = pl.DataFrame(data)
            
            # Calculate totals
            metrics = df.select([
                pl.col('amount').sum().alias('total_revenue'),
                pl.count().alias('revenue_count'),
                (pl.col('amount').sum() / pl.count()).alias('avg_revenue')
            ])
            
            # Calculate category totals
            category_totals = df.group_by('category__name').agg([
                pl.col('amount').sum().alias('total_amount'),
                pl.count().alias('transaction_count')
            ])
            
            # Calculate payment method totals
            payment_totals = df.group_by('payment_method').agg([
                pl.col('amount').sum().alias('total_amount'),
                pl.count().alias('transaction_count')
            ])
            
            return {
                'report_type': 'revenue_report',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'categories': category_totals.to_dicts(),
                'payment_methods': payment_totals.to_dicts(),
                'totals': {
                    'total_revenue': float(metrics['total_revenue'][0]),
                    'revenue_count': int(metrics['revenue_count'][0]),
                    'avg_revenue': float(metrics['avg_revenue'][0])
                }
            }
        except Exception as e:
            logger.error(f"Error generating revenue report: {str(e)}")
            return {
                'report_type': 'revenue_report',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'error': str(e)
            }
    
    def generate_todays_profit_summary(self) -> Dict[str, Any]:
        """
        Generate today's profit summary for quick dashboard view.
        
        Returns:
            Dict containing today's profit data
        """
        try:
            today = timezone.now().date()
            
            # Set the time period to today
            original_start = self.start_date
            original_end = self.end_date
            self.start_date = today
            self.end_date = today
            
            # Get sales data for today
            sales_data = self._get_sales_data()
            
            # Get COGS data for today
            cogs_data = self._get_cogs_data()
            
            # Get expenses data for today
            expenses_data = self._get_expenses_data()
            
            # Calculate profits
            gross_profit = sales_data['total_sales'] - cogs_data['total_cogs']
            net_profit = gross_profit - expenses_data['total_expenses']
            
            # Calculate margins
            gross_margin = (gross_profit / sales_data['total_sales']) * 100 if sales_data['total_sales'] > 0 else 0
            net_margin = (net_profit / sales_data['total_sales']) * 100 if sales_data['total_sales'] > 0 else 0
            
            # Restore original time period
            self.start_date = original_start
            self.end_date = original_end
            
            return {
                'report_type': 'todays_profit_summary',
                'date': today.isoformat(),
                'sales': {
                    'total_sales': float(sales_data['total_sales']),
                    'order_count': sales_data['order_count'],
                    'avg_order': float(sales_data['avg_order']) if sales_data['avg_order'] else 0.0
                },
                'cogs': {
                    'total_cogs': float(cogs_data['total_cogs']),
                    'cogs_percentage': (
                        float((cogs_data['total_cogs'] / sales_data['total_sales']) * 100) 
                        if sales_data['total_sales'] > 0 else 0.0
                    )
                },
                'expenses': {
                    'total_expenses': float(expenses_data['total_expenses'])
                },
                'gross_profit': {
                    'amount': float(gross_profit),
                    'margin': float(gross_margin)
                },
                'net_profit': {
                    'amount': float(net_profit),
                    'margin': float(net_margin)
                }
            }
        except Exception as e:
            logger.error(f"Error generating today's profit summary: {str(e)}")
            return {
                'report_type': 'todays_profit_summary',
                'date': timezone.now().date().isoformat(),
                'error': str(e)
            }

    # Helper methods for cash flow statement
    def _get_operating_cash_flows(self) -> Dict[str, Any]:
        """Get operating cash flows."""
        try:
            # Cash receipts from customers
            cash_receipts = Payment.objects.filter(
                payment_date__range=(self.start_date, self.end_date)
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            # Cash payments for expenses
            cash_payments = Expense.objects.filter(
                expense_date__range=(self.start_date, self.end_date),
                status='paid'
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            net_operating_cash_flow = cash_receipts - cash_payments
            
            return {
                'cash_receipts': float(cash_receipts),
                'cash_payments': float(cash_payments),
                'net_cash_flow': float(net_operating_cash_flow)
            }
        except Exception as e:
            logger.error(f"Error getting operating cash flows: {str(e)}")
            return {
                'cash_receipts': 0.0,
                'cash_payments': 0.0,
                'net_cash_flow': 0.0
            }
    
    def _get_investing_cash_flows(self) -> Dict[str, Any]:
        """Get investing cash flows (simplified)."""
        try:
            # For now, we'll consider inventory purchases as investing activities
            inventory_purchases = Expense.objects.filter(
                expense_date__range=(self.start_date, self.end_date),
                expense_type='inventory'
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            return {
                'inventory_purchases': float(inventory_purchases),
                'net_cash_flow': float(-inventory_purchases)  # Negative as it's cash outflow
            }
        except Exception as e:
            logger.error(f"Error getting investing cash flows: {str(e)}")
            return {
                'inventory_purchases': 0.0,
                'net_cash_flow': 0.0
            }
    
    def _get_financing_cash_flows(self) -> Dict[str, Any]:
        """Get financing cash flows (simplified)."""
        try:
            # Payroll payments
            payroll_payments = Expense.objects.filter(
                expense_date__range=(self.start_date, self.end_date),
                expense_type='payroll'
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            return {
                'payroll_payments': float(payroll_payments),
                'net_cash_flow': float(-payroll_payments)  # Negative as it's cash outflow
            }
        except Exception as e:
            logger.error(f"Error getting financing cash flows: {str(e)}")
            return {
                'payroll_payments': 0.0,
                'net_cash_flow': 0.0
            }
    
    # Helper methods for trial balance
    def _get_revenue_account_balances(self) -> list:
        """Get revenue account balances."""
        try:
            revenues = Revenue.objects.filter(
                revenue_date__range=(self.start_date, self.end_date)
            ).values('category__name').annotate(
                balance=Coalesce(Sum('amount'), Decimal('0.00'))
            )
            
            return [
                {
                    'account_name': item['category__name'] or 'Uncategorized',
                    'balance': float(item['balance']),
                    'account_type': 'revenue'
                }
                for item in revenues
            ]
        except Exception as e:
            logger.error(f"Error getting revenue account balances: {str(e)}")
            return []
    
    def _get_expense_account_balances(self) -> list:
        """Get expense account balances."""
        try:
            expenses = Expense.objects.filter(
                expense_date__range=(self.start_date, self.end_date)
            ).values('category__name').annotate(
                balance=Coalesce(Sum('amount'), Decimal('0.00'))
            )
            
            return [
                {
                    'account_name': item['category__name'] or 'Uncategorized',
                    'balance': float(item['balance']),
                    'account_type': 'expense'
                }
                for item in expenses
            ]
        except Exception as e:
            logger.error(f"Error getting expense account balances: {str(e)}")
            return []
    
    # Helper methods for balance sheet
    def _get_current_assets(self) -> Dict[str, Any]:
        """Get current assets."""
        try:
            # Cash and cash equivalents (simplified)
            cash_balance = Payment.objects.filter(
                payment_date__lte=self.end_date
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            # Inventory value
            inventory_value = BranchStock.objects.aggregate(
                total=Coalesce(Sum(F('quantity') * F('product__cost_price')), Decimal('0.00'))
            )['total']
            
            # Accounts receivable (unpaid revenues)
            accounts_receivable = Revenue.objects.filter(
                revenue_date__lte=self.end_date,
                status__in=['draft', 'submitted', 'approved']
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            total_current_assets = cash_balance + inventory_value + accounts_receivable
            
            return {
                'cash_and_equivalents': float(cash_balance),
                'inventory': float(inventory_value),
                'accounts_receivable': float(accounts_receivable),
                'total': float(total_current_assets)
            }
        except Exception as e:
            logger.error(f"Error getting current assets: {str(e)}")
            return {
                'cash_and_equivalents': 0.0,
                'inventory': 0.0,
                'accounts_receivable': 0.0,
                'total': 0.0
            }
    
    def _get_fixed_assets(self) -> Dict[str, Any]:
        """Get fixed assets (simplified)."""
        try:
            # For now, we'll consider equipment and furniture as fixed assets
            # This would typically come from a separate fixed assets module
            equipment_value = Decimal('0.00')  # Placeholder
            
            return {
                'equipment': float(equipment_value),
                'total': float(equipment_value)
            }
        except Exception as e:
            logger.error(f"Error getting fixed assets: {str(e)}")
            return {
                'equipment': 0.0,
                'total': 0.0
            }
    
    def _get_current_liabilities(self) -> Dict[str, Any]:
        """Get current liabilities."""
        try:
            # Accounts payable (unpaid expenses)
            accounts_payable = Expense.objects.filter(
                expense_date__lte=self.end_date,
                status__in=['draft', 'submitted', 'approved']
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            return {
                'accounts_payable': float(accounts_payable),
                'total': float(accounts_payable)
            }
        except Exception as e:
            logger.error(f"Error getting current liabilities: {str(e)}")
            return {
                'accounts_payable': 0.0,
                'total': 0.0
            }
    
    def _get_long_term_liabilities(self) -> Dict[str, Any]:
        """Get long-term liabilities (simplified)."""
        try:
            # Placeholder for long-term debt, loans, etc.
            return {
                'long_term_debt': 0.0,
                'total': 0.0
            }
        except Exception as e:
            logger.error(f"Error getting long-term liabilities: {str(e)}")
            return {
                'long_term_debt': 0.0,
                'total': 0.0
            }
    
    def _get_equity(self) -> Dict[str, Any]:
        """Get equity."""
        try:
            # Calculate retained earnings (simplified)
            total_revenues = Revenue.objects.filter(
                revenue_date__lte=self.end_date
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            total_expenses = Expense.objects.filter(
                expense_date__lte=self.end_date
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            retained_earnings = total_revenues - total_expenses
            
            return {
                'retained_earnings': float(retained_earnings),
                'total_equity': float(retained_earnings)
            }
        except Exception as e:
            logger.error(f"Error getting equity: {str(e)}")
            return {
                'retained_earnings': 0.0,
                'total_equity': 0.0
            }
