from typing import Dict, List, Any, Optional, Tuple, override
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db.models import (
    Sum, Count, F, Value, Case, When, Q, DecimalField, ExpressionWrapper,
    IntegerField, DateField, DateTimeField, Max, Min, Avg
)
from django.db.models.functions import (
    Coalesce, TruncDate, TruncDay, TruncWeek, TruncMonth, TruncQuarter, TruncYear
)
import polars as pl

from .base_report import BaseReport, TimePeriod
from apps.sales.models import Order, OrderItem, Payment
from apps.inventory.models import Product, Category, BranchStock, InventoryTransaction
from apps.accounting.models import Expense, ExpenseCategory
from apps.employees.models import Employee, Attendance
from apps.tables.models import Table, TableReservation


class DashboardReportGenerator(BaseReport):
    """Generator for dashboard data and overview reports."""
    @override
    def generate(self, *args, **kwargs) -> Dict[str, Any]:
        return self.generate_dashboard_overview()

    def generate_dashboard_overview(self) -> Dict[str, Any]:
        """
        Generate comprehensive data for the main dashboard overview.
        
        Returns:
            Dict containing all necessary data for the dashboard
        """
        # Get current date and time
        now = timezone.now()
        today = now.date()
        yesterday = today - timedelta(days=1)
        
        # Get date ranges for comparison
        current_month_start = today.replace(day=1)
        last_month_end = current_month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        
        # Get sales data
        sales_data = self._get_sales_data(today, yesterday, current_month_start, last_month_start, last_month_end)
        
        # Get inventory data
        inventory_data = self._get_inventory_data()
        
        # Get table occupancy data
        table_data = self._get_table_data()
        
        # Get employee performance data
        employee_data = self._get_employee_data(today)
        
        # Get expense data
        expense_data = self._get_expense_data(current_month_start, last_month_start, last_month_end)
        
        # Get profit data
        profit_data = self._get_profit_data(sales_data, expense_data)
        
        return {
            'report_type': 'dashboard_overview',
            'timestamp': now,
            'sales': sales_data,
            'inventory': inventory_data,
            'tables': table_data,
            'employees': employee_data,
            'expenses': expense_data,
            'profit': profit_data
        }
    
    def _get_sales_data(self, today: datetime.date, yesterday: datetime.date,
                        current_month_start: datetime.date, last_month_start: datetime.date,
                        last_month_end: datetime.date) -> Dict[str, Any]:
        """Get sales metrics for the dashboard."""
        # Today's sales
        today_sales = Order.objects.filter(
            status=Order.Status.COMPLETED,
            created_at__date=today
        ).aggregate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
            order_count=Count('id')
        )
        today_avg_order = float(today_sales['total_sales']) / today_sales['order_count'] if today_sales['order_count'] else 0.0
        # Yesterday's sales
        yesterday_sales = Order.objects.filter(
            status=Order.Status.COMPLETED,
            created_at__date=yesterday
        ).aggregate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0.00'))
        )
        # This month's sales
        this_month_sales = Order.objects.filter(
            status=Order.Status.COMPLETED,
            created_at__date__gte=current_month_start
        ).aggregate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
            order_count=Count('id')
        )
        this_month_avg_order = float(this_month_sales['total_sales']) / this_month_sales['order_count'] if this_month_sales['order_count'] else 0.0
        # Last month's sales
        last_month_sales = Order.objects.filter(
            status=Order.Status.COMPLETED,
            created_at__date__range=(last_month_start, last_month_end)
        ).aggregate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
            order_count=Count('id')
        )
        # Get sales trend (last 30 days)
        sales_trend = Order.objects.filter(
            status=Order.Status.COMPLETED,
            created_at__date__gte=today - timedelta(days=29)
        ).annotate(
            date=TruncDate('created_at')
        ).values('date').annotate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
            order_count=Count('id')
        ).order_by('date')
        # Format sales trend data
        formatted_trend = []
        for i in range(30):
            date = today - timedelta(days=29-i)
            daily_sales = next(
                (item for item in sales_trend if item['date'].date() == date), 
                {'total_sales': Decimal('0.00'), 'order_count': 0}
            )
            formatted_trend.append({
                'date': date,
                'total_sales': float(daily_sales['total_sales']),
                'order_count': daily_sales['order_count'],
                'day_name': date.strftime('%a')
            })
        # Calculate sales changes
        day_change = self._calculate_percentage_change(
            yesterday_sales['total_sales'], 
            today_sales['total_sales']
        )
        month_change = self._calculate_percentage_change(
            last_month_sales['total_sales'], 
            this_month_sales['total_sales']
        )
        return {
            'today': {
                'total_sales': float(today_sales['total_sales']),
                'order_count': today_sales['order_count'],
                'avg_order': today_avg_order,
                'day_change': day_change
            },
            'this_month': {
                'total_sales': float(this_month_sales['total_sales']),
                'order_count': this_month_sales['order_count'],
                'avg_order': this_month_avg_order,
                'month_change': month_change
            },
            'last_month': {
                'total_sales': float(last_month_sales['total_sales']),
                'order_count': last_month_sales['order_count']
            },
            'sales_trend': formatted_trend
        }
    
    def _get_inventory_data(self) -> Dict[str, Any]:
        """Get inventory metrics for the dashboard."""
        # Get low stock and out of stock items using BranchStock
        low_stock = BranchStock.objects.filter(
            is_active=True,
            product__is_active=True,
            current_stock__gt=0,
            reorder_level__gt=0,
            current_stock__lte=F('reorder_level') * 1.5
        ).select_related('product', 'branch').order_by('current_stock')
        out_of_stock = BranchStock.objects.filter(
            is_active=True,
            product__is_active=True,
            current_stock__lte=0
        ).select_related('product', 'branch').order_by('product__name')
        # Get recent inventory transactions
        recent_movements = InventoryTransaction.objects.select_related(
            'product', 'created_by', 'related_order'
        ).order_by('-created_at')[:10]
        # Format data
        return {
            'low_stock_count': low_stock.count(),
            'out_of_stock_count': out_of_stock.count(),
            'low_stock_items': [
                {
                    'id': item.product.id,
                    'name': item.product.name,
                    'sku': item.product.SKU,
                    'current_stock': item.current_stock,
                    'reorder_level': item.reorder_level,
                    'unit': getattr(item.product.unit_of_measure, 'name', None),
                    'category': item.product.category.name if item.product.category else None,
                    'branch': item.branch.name,
                    'branch_id': item.branch.id,
                    'alert_type': 'low_stock'
                }
                for item in low_stock
            ],
            'out_of_stock_items': [
                {
                    'id': item.product.id,
                    'name': item.product.name,
                    'sku': item.product.SKU,
                    'current_stock': 0,
                    'reorder_level': item.reorder_level,
                    'unit': getattr(item.product.unit_of_measure, 'name', None),
                    'category': item.product.category.name if item.product.category else None,
                    'branch': item.branch.name,
                    'branch_id': item.branch.id,
                    'alert_type': 'out_of_stock'
                }
                for item in out_of_stock
            ],
            'recent_movements': [
                {
                    'id': movement.id,
                    'product_name': getattr(movement.product, 'name', None),
                    'quantity': float(getattr(movement, 'quantity', 0)),
                    'type': getattr(movement, 'transaction_type', None),
                    'type_display': movement.get_transaction_type_display() if hasattr(movement, 'get_transaction_type_display') else None,
                    'created_at': movement.created_at,
                    'created_by': getattr(movement.created_by, 'get_full_name', lambda: None)(),
                    'reference_order': (
                        getattr(movement.related_order, 'order_number', None)
                        if getattr(movement, 'related_order', None) else None
                    )
                }
                for movement in recent_movements
            ]
        }
    
    def _get_table_data(self) -> Dict[str, Any]:
        """Get table occupancy data for the dashboard."""
        # Get all tables with their current status
        tables = Table.objects.all()
        
        # Get active reservations
        now = timezone.now()
        active_reservations = TableReservation.objects.filter(
            expected_arrival_time__lte=now,
            departure_time__gte=now,
            status__in=['confirmed', 'seated']
        ).select_related('table', 'customer')
        
        # Create a lookup for table status
        table_status = {}
        for reservation in active_reservations:
            if reservation.table_id not in table_status:
                table_status[reservation.table_id] = {
                    'status': 'occupied',
                    'reservation_id': reservation.id,
                    'customer_name': reservation.customer.get_full_name() if reservation.customer and hasattr(reservation.customer, 'get_full_name') else (getattr(reservation.customer, 'name', None) if reservation.customer else None),
                    'party_size': reservation.covers,
                    'start_time': reservation.expected_arrival_time,
                    'end_time': reservation.departure_time
                }
        
        # Get tables with active orders
        active_orders = Order.objects.filter(
            status__in=[Order.Status.CONFIRMED, Order.Status.PROCESSING, Order.Status.READY],
            tables__isnull=False
        ).prefetch_related('tables', 'customers')
        
        # Update table status with active orders
        for order in active_orders:
            for table in order.tables.all():
                if table.id not in table_status:
                    customer_names = ', '.join([c.get_full_name() for c in order.customers.all()])
                    table_status[table.id] = {
                        'status': 'occupied',
                        'order_id': order.id,
                        'customer_name': customer_names or 'Walk-in',
                        'start_time': order.created_at,
                        'duration': (now - order.created_at).total_seconds() / 60  # in minutes
                    }
        
        # Format data
        return {
            'total_tables': tables.count(),
            'available': tables.filter(status='available').count(),
            'occupied': tables.filter(status='occupied').count(),
            'reserved': tables.filter(status='reserved').count(),
            'tables': [
                {
                    'id': table.id,
                    'name': table.number,
                    'capacity': table.capacity,
                    'status': table_status.get(table.id, {}).get('status', getattr(table, 'status', '').lower()),
                    'details': table_status.get(table.id)
                }
                for table in tables.order_by('number')
            ]
        }
    
    def _get_employee_data(self, today: datetime.date) -> Dict[str, Any]:
        """Get employee performance data for the dashboard."""
        # Get active employees
        employees = Employee.objects.filter(is_active=True).select_related('user', 'role', 'department')
        
        # Get today's attendance
        attendance_today = Attendance.objects.filter(
            date=today
        ).select_related('employee')
        
        # Create attendance lookup
        attendance_lookup = {
            att.employee_id: {
                'status': att.status,
                'check_in': getattr(att, 'check_in', None),
                'check_out': getattr(att, 'check_out', None)
            }
            for att in attendance_today
        }
        
        # Format employee data
        return {
            'total_employees': employees.count(),
            'present_today': len([e for e in employees if e.id in attendance_lookup]),
            'employees': [
                {
                    'id': employee.id,
                    'name': employee.user.get_full_name(),
                    'position': employee.user.role.name if hasattr(employee.user, 'role') and employee.user.role else None,
                    'department': employee.department.name if employee.department else None,
                    'attendance': attendance_lookup.get(employee.id, {
                        'status': 'absent',
                        'check_in': None,
                        'check_out': None
                    })
                }
                for employee in employees.order_by('department__name', 'user__last_name', 'user__first_name')
            ]
        }
    
    def _get_expense_data(self, current_month_start: datetime.date,
                         last_month_start: datetime.date,
                         last_month_end: datetime.date) -> Dict[str, Any]:
        """Get expense metrics for the dashboard."""
        # Get current month's expenses
        current_expenses = Expense.objects.filter(
            expense_date__gte=current_month_start
        ).select_related('category')
        
        # Get last month's expenses
        last_expenses = Expense.objects.filter(
            expense_date__range=(last_month_start, last_month_end)
        ).select_related('category')
        
        # Calculate totals
        current_totals = current_expenses.aggregate(
            total_amount=Coalesce(Sum('amount'), Decimal('0.00')),
            expense_count=Count('id')
        )
        
        last_totals = last_expenses.aggregate(
            total_amount=Coalesce(Sum('amount'), Decimal('0.00')),
            expense_count=Count('id')
        )
        
        # Get expense categories
        categories = ExpenseCategory.objects.all()
        
        # Calculate category breakdown
        category_breakdown = []
        for category in categories:
            current_category = current_expenses.filter(category=category)
            last_category = last_expenses.filter(category=category)
            
            current_total = current_category.aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            last_total = last_category.aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            category_breakdown.append({
                'id': category.id,
                'name': category.name,
                'current': float(current_total),
                'last': float(last_total),
                'change': self._calculate_percentage_change(last_total, current_total),
                'percentage': (
                    float((current_total / current_totals['total_amount']) * 100) 
                    if current_totals['total_amount'] > 0 else 0.0
                )
            })
        
        # Get recent expenses
        recent_expenses = current_expenses.order_by('-expense_date')[:10]
        
        return {
            'current_month': {
                'total_amount': float(current_totals['total_amount']),
                'expense_count': current_totals['expense_count'],
                'avg_expense': (
                    float(current_totals['total_amount'] / current_totals['expense_count']) 
                    if current_totals['expense_count'] > 0 else 0.0
                )
            },
            'last_month': {
                'total_amount': float(last_totals['total_amount']),
                'expense_count': last_totals['expense_count']
            },
            'category_breakdown': category_breakdown,
            'recent_expenses': [
                {
                    'id': expense.id,
                    'date': expense.expense_date,
                    'amount': float(expense.amount),
                    'category': expense.category.name,
                    'description': expense.description,
                    'payment_method': expense.payment_method,
                    'approved_by': getattr(expense.approved_by, 'get_full_name', lambda: None)() if expense.approved_by else None
                }
                for expense in recent_expenses
            ]
        }
    
    def _get_profit_data(self, sales_data: Dict[str, Any], expense_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate profit metrics for the dashboard."""
        # Calculate gross profit (sales - COGS)
        current_cogs = self._calculate_cogs()
        gross_profit = sales_data['this_month']['total_sales'] - current_cogs
        
        # Calculate net profit (gross profit - expenses)
        net_profit = gross_profit - expense_data['current_month']['total_amount']
        
        # Calculate profit margins
        gross_margin = (gross_profit / sales_data['this_month']['total_sales']) * 100 if sales_data['this_month']['total_sales'] > 0 else 0
        net_margin = (net_profit / sales_data['this_month']['total_sales']) * 100 if sales_data['this_month']['total_sales'] > 0 else 0
        
        return {
            'gross_profit': {
                'amount': float(gross_profit),
                'margin': float(gross_margin)
            },
            'net_profit': {
                'amount': float(net_profit),
                'margin': float(net_margin)
            },
            'cogs': {
                'amount': float(current_cogs),
                'percentage': (
                    float((current_cogs / sales_data['this_month']['total_sales']) * 100) 
                    if sales_data['this_month']['total_sales'] > 0 else 0.0
                )
            }
        }
    
    def _calculate_cogs(self) -> Decimal:
        """Calculate Cost of Goods Sold for the current month."""
        now = timezone.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # Get COGS from completed orders
        cogs = OrderItem.objects.filter(
            order__status=Order.Status.COMPLETED,
            order__created_at__gte=current_month_start
        ).annotate(
            item_cogs=ExpressionWrapper(
                F('quantity') * F('product__cost_price'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).aggregate(
            total_cogs=Coalesce(Sum('item_cogs'), Decimal('0.00'))
        )['total_cogs']
        
        return cogs
    
    def _calculate_percentage_change(self, previous: Decimal, current: Decimal) -> float:
        """Calculate percentage change between two values."""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return float(((current - previous) / abs(previous)) * 100)
