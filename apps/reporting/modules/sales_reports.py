from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce, TruncMonth, TruncQuarter, TruncWeek, TruncDay, TruncYear, ExtractHour, ExtractWeekDay
from apps.sales.models import Order
from django.utils import timezone
import polars as pl
from .base_report import BaseReport, TimePeriod
from apps.sales.models import Order, OrderItem
from apps.inventory.models import Product, BranchStock
from apps.employees.models import Employee
from apps.tables.models import Table


class SalesReportGenerator(BaseReport):
    """Generator for sales-related reports."""
    
    def __init__(self, branch: Optional[str] = None):
        """Initialize the report generator with optional branch filter."""
        super().__init__()
        self.branch = branch
        
    def generate(self, *args, **kwargs) -> Dict[str, Any]:
        """
        Generate the sales report data.
        
        Returns:
            Dict containing sales report data
        """
        return {
            'summary': self.generate_sales_summary(),
            'sales_by_category': self.generate_sales_by_category(),
            'sales_by_product': self.generate_sales_by_product(),
            'payment_methods': self.generate_payment_methods_report(),
            'sales_by_employee': self.generate_sales_by_employee(),
            'sales_by_hour': self.generate_sales_by_hour(),
            'sales_by_day': self.generate_sales_by_day()
        }
    
    def get_base_queryset(self, model):
        """Get base queryset with branch filtering."""
        queryset = model.objects.all()
        if self.branch:
            if model == Order:
                queryset = queryset.filter(branch=self.branch)
            elif model == OrderItem:
                queryset = queryset.filter(order__branch=self.branch)
        return queryset
    
    def generate_sales_summary(self, group_by: str = 'day') -> Dict[str, Any]:
        """
        Generate a summary of sales data.
        
        Args:
            group_by: How to group the data (day, week, month, quarter, year)
            
        Returns:
            Dict containing sales summary data
        """
        # Base queryset for completed orders with branch filter
        orders = self.get_base_queryset(Order).filter(status=Order.Status.COMPLETED)
        
        # Apply date range
        orders = self.apply_date_filter(orders, 'created_at')
        
        # Group by time period
        trunc_func = {
            'day': TruncDay('created_at'),
            'week': TruncWeek('created_at'),
            'month': TruncMonth('created_at'),
            'quarter': TruncQuarter('created_at'),
            'year': TruncYear('created_at')
        }.get(group_by, TruncDay('created_at'))
        
        # Calculate metrics
        time_series = orders.annotate(
            period=trunc_func
        ).values('period').annotate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
            order_count=Count('id'),
            avg_order=ExpressionWrapper(
                F('total_sales') / F('order_count'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).order_by('period')
        
        # Convert to Polars DataFrame
        df = pl.DataFrame(list(time_series))

        if df.is_empty():
            return {
                'report_type': 'sales_summary',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'metrics': {
                    'total_sales': 0.0,
                    'order_count': 0,
                    'avg_order': 0.0
                },
                'time_series': []
            }
        
        # Calculate metrics using Polars expressions
        metrics = df.select([
            pl.col('total_sales').sum().alias('total_sales'),
            pl.col('order_count').sum().alias('order_count'),
            (pl.col('total_sales').sum() / pl.col('order_count').sum()).alias('avg_order')
        ])
        
        return {
            'report_type': 'sales_summary',
            'time_period': {'start': self.start_date, 'end': self.end_date},
            'metrics': {
                'total_sales': float(metrics['total_sales'][0]),
                'order_count': int(metrics['order_count'][0]),
                'avg_order': float(metrics['avg_order'][0])
            },
            'time_series': time_series
        }
    
    def generate_sales_by_category(self) -> Dict[str, Any]:
        """
        Generate a report of sales by product category.
        
        Returns:
            Dict containing sales data by category
        """
        # Get order items for completed orders
        order_items = OrderItem.objects.filter(
            order__status=Order.Status.COMPLETED
        ).select_related('product__category')
        
        # Apply date range
        order_items = self.apply_date_filter(order_items, 'order__created_at')
        
        # Group by category
        sales_by_category = order_items.values(
            'product__category__id',
            'product__category__name'
        ).annotate(
            total_quantity=Coalesce(Sum('quantity'), Decimal('0.00')),
            total_sales=Coalesce(Sum(ExpressionWrapper(F('quantity') * F('unit_price'), output_field=DecimalField(max_digits=15, decimal_places=2))), Decimal('0.00')),
            avg_price=ExpressionWrapper(
                F('total_sales') / F('total_quantity'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            ),
            order_count=Count('order_id', distinct=True)
        ).order_by('-total_sales')
        
        # Convert to Polars DataFrame
        df = pl.DataFrame(list(sales_by_category))
        
        if df.is_empty():
            return {
                'report_type': 'sales_by_category',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'categories': [],
                'totals': {
                    'total_sales': 0.0,
                    'order_count': 0,
                    'total_quantity': 0,
                    'avg_price': 0.0
                }
            }
        
        # Calculate category totals using correct Polars group_by
        category_totals = df.group_by('product__category__name').agg([
            pl.col('total_sales').sum().alias('total_sales'),
            pl.col('order_count').sum().alias('order_count'),
            pl.col('total_quantity').sum().alias('total_quantity')
        ])
        total_sales = category_totals['total_sales'].sum() if not category_totals.is_empty() else 0
        if total_sales:
            category_totals = category_totals.with_columns([
                (pl.col('total_sales') / pl.col('total_quantity')).alias('avg_price'),
                ((pl.col('total_sales') / total_sales) * 100).alias('sales_percentage')
            ])
        else:
            category_totals = category_totals.with_columns([
                pl.lit(0).alias('avg_price'),
                pl.lit(0).alias('sales_percentage')
            ])
        top_categories = category_totals.sort('total_sales', descending=True)
        
        return {
            'report_type': 'sales_by_category',
            'time_period': {'start': self.start_date, 'end': self.end_date},
            'categories': top_categories.to_dicts(),
            'totals': {
                'total_sales': float(total_sales),
                'order_count': int(category_totals['order_count'].sum()),
                'total_quantity': int(category_totals['total_quantity'].sum()),
                'avg_price': float(category_totals['avg_price'].mean()) if not category_totals.is_empty() else 0.0
            }
        }
    
    def generate_sales_by_product(self, top_n: int = 10, category_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate a report of top-selling products.
        
        Args:
            top_n: Number of top products to return
            category_id: Optional category ID to filter products
        
        Returns:
            Dict containing top-selling products data
        """
        # Get order items for completed orders with branch filter
        order_items = self.get_base_queryset(OrderItem).filter(
            order__status=Order.Status.COMPLETED
        ).select_related('product__category')
        
        # Apply date range
        order_items = self.apply_date_filter(order_items, 'order__created_at')

        # Filter by category if provided
        if category_id:
            order_items = order_items.filter(product__category_id=category_id)
        
        # Group by product
        top_products = order_items.values(
            'product__id',
            'product__name',
            'product__SKU',
            'product__category__name'
        ).annotate(
            total_quantity=Coalesce(Sum('quantity'), Decimal('0.00')),
            total_sales=Coalesce(Sum(ExpressionWrapper(F('quantity') * F('unit_price'), output_field=DecimalField(max_digits=15, decimal_places=2))), Decimal('0.00')),
            avg_price=ExpressionWrapper(
                F('total_sales') / F('total_quantity'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            ),
            order_count=Count('order_id', distinct=True)
        ).order_by('-total_sales')[:top_n]
        
        # Calculate totals
        totals = order_items.aggregate(
            total_quantity=Coalesce(Sum('quantity'), Decimal('0.00')),
            total_sales=Coalesce(Sum(ExpressionWrapper(F('quantity') * F('unit_price'), output_field=DecimalField(max_digits=15, decimal_places=2))), Decimal('0.00'))
        )
        
        # Format data
        products = []
        for item in top_products:
            products.append({
                'product_id': item['product__id'],
                'product_name': item['product__name'],
                'sku': item['product__SKU'],
                'category': item['product__category__name'],
                'total_quantity': item['total_quantity'],
                'total_sales': float(item['total_sales']),
                'avg_price': float(item['avg_price']) if item['avg_price'] else 0.0,
                'order_count': item['order_count'],
                'sales_percentage': (
                    float((item['total_sales'] / totals['total_sales']) * 100) 
                    if totals['total_sales'] > 0 else 0.0
                )
            })
        
        # Convert to Polars DataFrame
        df = pl.DataFrame(list(top_products))
        
        if df.is_empty():
            return {
                'report_type': 'top_products',
                'time_period': self.get_time_period_display(),
                'start_date': self.start_date,
                'end_date': self.end_date,
                'top_n': top_n,
                'totals': {
                    'total_quantity': totals['total_quantity'],
                    'total_sales': 0.0
                },
                'products': []
            }
        
        return {
            'report_type': 'top_products',
            'time_period': self.get_time_period_display(),
            'start_date': self.start_date,
            'end_date': self.end_date,
            'top_n': top_n,
            'totals': {
                'total_quantity': totals['total_quantity'],
                'total_sales': float(totals['total_sales'])
            },
            'products': products
        }
    
    def generate_payment_methods_report(self) -> Dict[str, Any]:
        """
        Generate a report showing payment method usage and success rates.
        
        Returns:
            Dict containing payment method statistics
        """
        # Get completed orders with branch filter
        orders = self.get_base_queryset(Order).filter(status=Order.Status.COMPLETED)
        
        # Get completed orders with payment data
        orders = self.get_base_queryset(Order).filter(
            status=Order.Status.COMPLETED
        ).select_related('customer')
        
        # Apply date range
        orders = self.apply_date_filter(orders, 'created_at')
        
        # Group by payment method using order data
        payment_data = orders.values(
            'payment_method',
            'payment_status'
        ).annotate(
            total_amount=Coalesce(Sum('total_amount'), Decimal('0.00')),
            transaction_count=Count('id'),
            avg_amount=ExpressionWrapper(
                F('total_amount') / F('transaction_count'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).order_by('-total_amount')
        
        # Calculate totals using order data
        totals = orders.aggregate(
            total_amount=Coalesce(Sum('total_amount'), Decimal('0.00')),
            transaction_count=Count('id')
        )
        
        # Format data
        methods = []
        for item in payment_data:
            methods.append({
                'method_id': item['payment_method__id'],
                'method_name': item['payment_method__name'],
                'total_amount': float(item['total_amount']),
                'transaction_count': item['transaction_count'],
                'avg_amount': float(item['avg_amount']) if item['avg_amount'] else 0.0,
                'percentage': (
                    float((item['total_amount'] / totals['total_amount']) * 100) 
                    if totals['total_amount'] > 0 else 0.0
                )
            })
        
        # Convert to Polars DataFrame
        df = pl.DataFrame(list(payment_data))
        
        if df.is_empty():
            return {
                'report_type': 'payment_methods',
                'time_period': self.get_time_period_display(),
                'start_date': self.start_date,
                'end_date': self.end_date,
                'totals': {
                    'total_amount': 0.0,
                    'transaction_count': 0
                },
                'payment_methods': []
            }
        
        return {
            'report_type': 'payment_methods',
            'time_period': self.get_time_period_display(),
            'start_date': self.start_date,
            'end_date': self.end_date,
            'totals': {
                'total_amount': float(totals['total_amount']),
                'transaction_count': totals['transaction_count']
            },
            'payment_methods': methods
        }
    
    def generate_sales_by_employee(self) -> Dict[str, Any]:
        """
        Generate a report of sales by employee.
        
        Returns:
            Dict containing sales data by employee
        """
        # Get orders with employee information
        orders = Order.objects.filter(
            status=Order.Status.COMPLETED,
            employee__isnull=False
        ).select_related('employee')
        
        # Apply date range
        orders = self.apply_date_filter(orders, 'created_at')
        
        # Group by employee
        sales_by_employee = orders.values(
            'employee__id',
            'employee__first_name',
            'employee__last_name',
            'employee__employee_id'
        ).annotate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
            order_count=Count('id'),
            avg_order=ExpressionWrapper(
                F('total_sales') / F('order_count'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            ),
            avg_items_per_order=ExpressionWrapper(
                Count('items') / F('order_count'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).order_by('-total_sales')
        
        # Calculate totals
        totals = orders.aggregate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
            order_count=Count('id'),
            avg_order=ExpressionWrapper(
                F('total_sales') / F('order_count'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        )
        
        # Format data
        employees = []
        for item in sales_by_employee:
            employees.append({
                'employee_id': item['employee__id'],
                'employee_name': f"{item['employee__first_name']} {item['employee__last_name']}",
                'employee_number': item['employee__employee_id'],
                'total_sales': float(item['total_sales']),
                'order_count': item['order_count'],
                'avg_order': float(item['avg_order']) if item['avg_order'] else 0.0,
                'avg_items_per_order': float(item['avg_items_per_order']) if item['avg_items_per_order'] else 0.0,
                'sales_percentage': (
                    float((item['total_sales'] / totals['total_sales']) * 100) 
                    if totals['total_sales'] > 0 else 0.0
                )
            })
        
        # Convert to Polars DataFrame
        df = pl.DataFrame(list(sales_by_employee))
        
        if df.is_empty():
            return {
                'report_type': 'sales_by_employee',
                'time_period': self.get_time_period_display(),
                'start_date': self.start_date,
                'end_date': self.end_date,
                'totals': {
                    'total_sales': 0.0,
                    'order_count': 0,
                    'avg_order': 0.0
                },
                'employees': []
            }
        
        return {
            'report_type': 'sales_by_employee',
            'time_period': self.get_time_period_display(),
            'start_date': self.start_date,
            'end_date': self.end_date,
            'totals': {
                'total_sales': float(totals['total_sales']),
                'order_count': totals['order_count'],
                'avg_order': float(totals['avg_order']) if totals['avg_order'] else 0.0
            },
            'employees': employees
        }
    
    def generate_sales_by_hour(self) -> Dict[str, Any]:
        """
        Generate a report of sales by hour of the day.
        
        Returns:
            Dict containing sales data by hour
        """
        # Base queryset for completed orders with branch filter
        orders = self.get_base_queryset(Order).filter(status=Order.Status.COMPLETED)
        
        # Apply date range
        orders = self.apply_date_filter(orders, 'created_at')
        
        # Group by hour
        sales_by_hour = orders.annotate(
            hour=ExtractHour('created_at')
        ).values('hour').annotate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
            order_count=Count('id'),
            avg_order=ExpressionWrapper(
                F('total_sales') / F('order_count'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).order_by('hour')
        
        # Convert to Polars DataFrame
        df = pl.DataFrame(list(sales_by_hour))
        
        if df.is_empty():
            return {
                'report_type': 'sales_by_hour',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'hours': [],
                'totals': {
                    'total_sales': 0.0,
                    'order_count': 0,
                    'avg_order': 0.0
                }
            }
        
        # Calculate totals
        totals = df.select([
            pl.col('total_sales').sum().alias('total_sales'),
            pl.col('order_count').sum().alias('order_count'),
            (pl.col('total_sales').sum() / pl.col('order_count').sum()).alias('avg_order')
        ])
        
        # Format hour data
        hours_data = []
        for hour in range(24):
            hour_data = df.filter(pl.col('hour') == hour)
            if not hour_data.is_empty():
                hours_data.append({
                    'hour': hour,
                    'hour_display': f'{hour:02d}:00',
                    'total_sales': float(hour_data['total_sales'][0]),
                    'order_count': int(hour_data['order_count'][0]),
                    'avg_order': float(hour_data['avg_order'][0])
                })
            else:
                hours_data.append({
                    'hour': hour,
                    'hour_display': f'{hour:02d}:00',
                    'total_sales': 0.0,
                    'order_count': 0,
                    'avg_order': 0.0
                })
        
        return {
            'report_type': 'sales_by_hour',
            'time_period': {'start': self.start_date, 'end': self.end_date},
            'hours': hours_data,
            'totals': {
                'total_sales': float(totals['total_sales'][0]),
                'order_count': int(totals['order_count'][0]),
                'avg_order': float(totals['avg_order'][0])
            }
        }
    
    def generate_sales_by_day(self) -> Dict[str, Any]:
        """
        Generate a report of sales by day of the week.
        
        Returns:
            Dict containing sales data by day
        """
        # Base queryset for completed orders with branch filter
        orders = self.get_base_queryset(Order).filter(status=Order.Status.COMPLETED)
        
        # Apply date range
        orders = self.apply_date_filter(orders, 'created_at')
        
        # Group by day of week
        sales_by_day = orders.annotate(
            day_of_week=ExtractWeekDay('created_at')
        ).values('day_of_week').annotate(
            total_sales=Coalesce(Sum('total_amount'), Decimal('0.00')),
            order_count=Count('id'),
            avg_order=ExpressionWrapper(
                F('total_sales') / F('order_count'),
                output_field=DecimalField(max_digits=10, decimal_places=2)
            )
        ).order_by('day_of_week')
        
        # Convert to Polars DataFrame
        df = pl.DataFrame(list(sales_by_day))
        
        if df.is_empty():
            return {
                'report_type': 'sales_by_day',
                'time_period': {'start': self.start_date, 'end': self.end_date},
                'days': [],
                'totals': {
                    'total_sales': 0.0,
                    'order_count': 0,
                    'avg_order': 0.0
                }
            }
        
        # Calculate totals
        totals = df.select([
            pl.col('total_sales').sum().alias('total_sales'),
            pl.col('order_count').sum().alias('order_count'),
            (pl.col('total_sales').sum() / pl.col('order_count').sum()).alias('avg_order')
        ])
        
        # Day names mapping (1=Sunday, 7=Saturday in Django)
        day_names = {
            1: 'Sunday',
            2: 'Monday', 
            3: 'Tuesday',
            4: 'Wednesday',
            5: 'Thursday',
            6: 'Friday',
            7: 'Saturday'
        }
        
        # Format day data
        days_data = []
        for day_num in range(1, 8):
            day_data = df.filter(pl.col('day_of_week') == day_num)
            if not day_data.is_empty():
                days_data.append({
                    'day_number': day_num,
                    'day_name': day_names[day_num],
                    'total_sales': float(day_data['total_sales'][0]),
                    'order_count': int(day_data['order_count'][0]),
                    'avg_order': float(day_data['avg_order'][0])
                })
            else:
                days_data.append({
                    'day_number': day_num,
                    'day_name': day_names[day_num],
                    'total_sales': 0.0,
                    'order_count': 0,
                    'avg_order': 0.0
                })
        
        return {
            'report_type': 'sales_by_day',
            'time_period': {'start': self.start_date, 'end': self.end_date},
            'days': days_data,
            'totals': {
                'total_sales': float(totals['total_sales'][0]),
                'order_count': int(totals['order_count'][0]),
                'avg_order': float(totals['avg_order'][0])
            }
        }
