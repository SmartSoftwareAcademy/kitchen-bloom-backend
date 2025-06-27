import logging
from datetime import datetime
from typing import Any, Dict

from django.db.models import Sum, Count, Q, F
from django.utils import timezone
from rest_framework import status, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.request import Request
from rest_framework.response import Response
from django.http import FileResponse
import os

from apps.reporting.models import Report, ReportExecutionLog, ReportType
from apps.reporting.serializers import (
    ReportSerializer,
    ReportDataSerializer,
)
from apps.reporting.modules.inventory_reports import InventoryReportGenerator
from apps.reporting.modules.sales_reports import SalesReportGenerator
from apps.reporting.modules.financial_reports import FinancialReportGenerator
from apps.sales.models import Order, OrderItem
from apps.inventory.models import Product, Category
from apps.accounting.models import Expense, ExpenseCategory
from apps.employees.models import Employee
from apps.payroll.models import EmployeePayroll
from apps.reporting.export import ReportExporter

logger = logging.getLogger(__name__)


class StockReportViewSet(viewsets.ViewSet):
    """
    ViewSet for stock/inventory reports.
    Provides standardized endpoints for stock management reports.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request: Request) -> Response:
        """
        List available stock report types.
        """
        return Response({
            'available_reports': [
                'alerts', 'stock-taking', 'movement', 'valuation'
            ],
            'description': 'Use /stock/{report_type}/export/ to get specific reports'
        })

    def retrieve(self, request: Request, pk: str = None) -> Response:
        """
        Generate stock management reports.
        
        Supported report types (pk):
        - 'alerts': Stock alerts (out of stock and low stock)
        - 'stock-taking': Current stock levels
        - 'movement': Stock movement history
        - 'valuation': Inventory valuation report
        """
        try:
            report_type = pk
            # Get query parameters
            threshold = float(request.query_params.get('threshold', 20.0))
            include_supplier = request.query_params.get('include_supplier', 'true').lower() == 'true'
            category_id = request.query_params.get('category_id')
            location_id = request.query_params.get('location_id')
            as_of = request.query_params.get('as_of')

            # Initialize report generator
            report_generator = InventoryReportGenerator()

            # Generate the requested report
            if report_type == 'alerts':
                result = report_generator.generate_stock_alerts(
                    threshold_percentage=threshold
                )
            elif report_type == 'stock-taking':
                # Only pass supported parameters to generate_stock_taking
                result = report_generator.generate_stock_taking(
                    category_id=category_id,
                    include_zero_stock=request.query_params.get('include_zero_stock', 'false').lower() == 'true'
                )
            elif report_type == 'movement':
                # Only pass supported parameters to generate_stock_movement
                result = report_generator.generate_stock_movement(
                    product_id=request.query_params.get('product_id'),
                    movement_type=request.query_params.get('movement_type')
                )
            elif report_type == 'valuation':
                # Use generate_stock_adjustment as the closest match for valuation
                result = report_generator.generate_stock_adjustment(
                    product_id=request.query_params.get('product_id'),
                    adjustment_type=request.query_params.get('adjustment_type')
                )
            else:
                return Response(
                    {'error': f'Unknown report type: {report_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response({
                'status': 'success',
                'data': result,
                'metadata': {
                    'generated_at': timezone.now().isoformat(),
                    'report_type': report_type,
                    'filters': {
                        'threshold': threshold if report_type == 'alerts' else None,
                        'include_supplier': include_supplier if report_type == 'alerts' else None,
                        'category_id': category_id,
                        'location_id': location_id,
                        'as_of': as_of if report_type == 'stock-taking' else None
                    }
                }
            })

        except ValueError as e:
            return Response(
                {'error': f'Invalid parameter value: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f'Error generating {report_type} report')
            return Response(
                {'error': f'Failed to generate {report_type} report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def export(self, request: Request, pk: str = None) -> Response:
        """
        Export stock reports as CSV or PDF.
        Query param: format=csv|pdf (default: csv)
        """
        try:
            report_type = pk
            format_ = request.query_params.get('format', 'csv').lower()
            threshold = float(request.query_params.get('threshold', 20.0))
            category_id = request.query_params.get('category_id')
            location_id = request.query_params.get('location_id')
            as_of = request.query_params.get('as_of')
            
            report_generator = InventoryReportGenerator()
            
            # Generate report data
            if report_type == 'alerts':
                data = report_generator.generate_stock_alerts(threshold_percentage=threshold)
                template = 'stock_alerts'
            elif report_type == 'stock-taking':
                data = report_generator.generate_stock_taking(
                    category_id=category_id,
                    include_zero_stock=request.query_params.get('include_zero_stock', 'false').lower() == 'true'
                )
                template = 'stock_taking'
            elif report_type == 'movement':
                data = report_generator.generate_stock_movement(
                    product_id=request.query_params.get('product_id'),
                    movement_type=request.query_params.get('movement_type')
                )
                template = 'stock_movement'
            elif report_type == 'valuation':
                data = report_generator.generate_stock_adjustment(
                    product_id=request.query_params.get('product_id'),
                    adjustment_type=request.query_params.get('adjustment_type')
                )
                template = 'inventory_valuation'
            else:
                return Response({'error': 'Unsupported report type for export'}, status=400)
            
            exporter = ReportExporter()
            filename = f"stock_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if format_ == 'pdf':
                file_path = exporter.export_to_pdf('stock', data, template, filename, request=request)
                content_type = 'application/pdf'
            else:
                file_path = exporter.export_to_csv('stock', data, filename)
                content_type = 'text/csv'
            
            if not os.path.exists(file_path):
                return Response({'error': 'Failed to generate export file'}, status=500)
            
            response = FileResponse(
                open(file_path, 'rb'),
                content_type=content_type
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}.{format_}"'
            return response
            
        except Exception as e:
            logger.exception(f'Error exporting stock report: {str(e)}')
            return Response({'error': 'Failed to export report'}, status=500)


class SalesReportViewSet(viewsets.ViewSet):
    """
    ViewSet for sales reports.
    Provides standardized endpoints for sales analytics and reporting.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request: Request) -> Response:
        """
        List available sales report types.
        """
        return Response({
            'available_reports': [
                'summary', 'by-product', 'by-category', 'by-employee',
                'by-hour', 'by-day', 'grand-total', 'trends', 'recent'
            ],
            'description': 'Use /sales/{report_type}/export/ to get specific reports'
        })

    def retrieve(self, request: Request, pk: str = None) -> Response:
        """
        Generate sales reports.
        
        Supported report types (pk):
        - 'summary': Sales summary with totals and trends
        - 'by-product': Sales breakdown by product
        - 'by-category': Sales breakdown by category
        - 'by-employee': Sales performance by employee
        - 'by-hour': Sales distribution by hour of day
        - 'by-day': Sales distribution by day of week
        - 'grand-total': Grand total report with all metrics
        - 'trends': Sales trends (time series)
        - 'recent': Recent completed orders
        """
        try:
            report_type = pk
            period = request.query_params.get('period', 'today')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            group_by = request.query_params.get('group_by', 'day')
            branch_id = request.query_params.get('branch_id')
            payment_method = request.query_params.get('payment_method')
            employee_id = request.query_params.get('employee_id')
            category_id = request.query_params.get('category_id')

            report_generator = SalesReportGenerator(branch=branch_id)
            report_generator.set_time_period(
                period=period,
                custom_start=start_date,
                custom_end=end_date
            )

            if report_type == 'summary':
                result = report_generator.generate_sales_summary(group_by=group_by)
            elif report_type == 'by-product':
                top_n = int(request.query_params.get('limit', 10))
                result = report_generator.generate_sales_by_product(
                    category_id=category_id,
                    top_n=top_n
                )
            elif report_type == 'by-category':
                result = report_generator.generate_sales_by_category()
            elif report_type == 'by-employee':
                result = report_generator.generate_sales_by_employee(
                    employee_id=employee_id,
                    group_by=group_by
                )
            elif report_type == 'by-hour':
                result = report_generator.generate_sales_by_hour()
            elif report_type == 'by-day':
                result = report_generator.generate_sales_by_day()
            elif report_type == 'grand-total':
                result = self._generate_grand_total_report(report_generator, period)
            elif report_type == 'trends':
                summary = report_generator.generate_sales_summary(group_by='day')
                result = {
                    'report_type': 'trends',
                    'time_series': summary.get('time_series', []),
                    'metrics': summary.get('metrics', {}),
                    'time_period': summary.get('time_period', {})
                }
            elif report_type == 'recent':
                orders = report_generator.get_base_queryset(Order).filter(status=Order.Status.COMPLETED).order_by('-created_at')[:10]
                result = {
                    'report_type': 'recent',
                    'orders': [
                        {
                            'id': o.id,
                            'order_number': o.order_number,
                            'created_at': o.created_at,
                            'total_amount': o.total_amount,
                            'customers': [
                                {
                                    'full_name': getattr(c, 'full_name', str(c)),
                                    'customer_code': getattr(c, 'customer_code', None),
                                    'customer_type': getattr(c, 'customer_type', None),
                                    'primary_contact': getattr(c, 'primary_contact', None),
                                    'loyalty_tier': getattr(c, 'loyalty_tier', None),
                                } for c in o.customers.all()
                            ],
                            'branch': getattr(o.branch, 'name', None),
                            'status': o.status
                        } for o in orders
                    ]
                }
            else:
                return Response(
                    {'error': f'Unknown report type: {report_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response({
                'status': 'success',
                'data': result,
                'metadata': {
                    'generated_at': timezone.now().isoformat(),
                    'report_type': f'sales_{report_type.replace("-", "_")}',
                    'filters': {
                        'period': period,
                        'start_date': report_generator.start_date.isoformat() if report_generator.start_date else None,
                        'end_date': report_generator.end_date.isoformat() if report_generator.end_date else None,
                        'group_by': group_by,
                        'branch_id': branch_id,
                        'payment_method': payment_method,
                        'employee_id': employee_id,
                        'category_id': category_id
                    }
                }
            })

        except ValueError as e:
            return Response(
                {'error': f'Invalid parameter value: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f'Error generating sales report: {str(e)}')
            return Response(
                {'error': 'Failed to generate sales report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def export(self, request: Request, pk: str = None) -> Response:
        """
        Export sales reports as CSV or PDF.
        Query param: format=csv|pdf (default: csv)
        """
        try:
            report_type = pk
            format_ = request.query_params.get('format', 'csv').lower()
            period = request.query_params.get('period', 'today')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            group_by = request.query_params.get('group_by', 'day')
            branch_id = request.query_params.get('branch_id')
            category_id = request.query_params.get('category_id')
            
            report_generator = SalesReportGenerator(branch=branch_id)
            report_generator.set_time_period(period=period, custom_start=start_date, custom_end=end_date)
            
            if report_type == 'summary':
                data = report_generator.generate_sales_summary(group_by=group_by)
                template = 'sales_summary'
            elif report_type == 'by-category':
                data = report_generator.generate_sales_by_category()
                template = 'sales_by_category'
            elif report_type == 'by-product':
                top_n = int(request.query_params.get('limit', 10))
                data = report_generator.generate_sales_by_product(
                    category_id=category_id,
                    top_n=top_n
                )
                template = 'sales_by_product'
            else:
                return Response({'error': 'Unsupported report type for export'}, status=400)
            
            exporter = ReportExporter()
            filename = f"sales_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if format_ == 'pdf':
                file_path = exporter.export_to_pdf('sales', data, template, filename, request=request)
                content_type = 'application/pdf'
            else:
                file_path = exporter.export_to_csv('sales', data, filename)
                content_type = 'text/csv'
            
            if not os.path.exists(file_path):
                return Response({'error': 'Failed to generate export file'}, status=500)
            
            response = FileResponse(
                open(file_path, 'rb'),
                content_type=content_type
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}.{format_}"'
            return response
            
        except Exception as e:
            logger.exception(f'Error exporting sales report: {str(e)}')
            return Response({'error': 'Failed to export report'}, status=500)

    def _generate_grand_total_report(self, report_generator, period):
        """Generate grand total sales report."""
        summary = report_generator.generate_sales_summary(group_by='day')
        by_category = report_generator.generate_sales_by_category()
        by_product = report_generator.generate_sales_by_product(top_n=10)
        
        return {
            'report_type': 'grand_total',
            'summary': summary,
            'by_category': by_category,
            'top_products': by_product,
            'period': period
        }


class FinancialReportViewSet(viewsets.ViewSet):
    """
    ViewSet for financial reports.
    Provides standardized endpoints for financial analytics and reporting.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request: Request) -> Response:
        """
        List available financial report types.
        """
        return Response({
            'available_reports': [
                'expenses', 'profit', 'payroll', 'cashflow', 'trial-balance', 
                'balance-sheet', 'revenue', 'todays-profit-summary', 'grand-total'
            ],
            'description': 'Use /financial/{report_type}/export/ to get specific reports'
        })

    def retrieve(self, request: Request, pk: str = None) -> Response:
        """
        Generate financial reports.
        
        Supported report types (pk):
        - 'expenses': Detailed expense report with category breakdown
        - 'profit': Profit analysis with revenue, cost of goods sold, and expenses
        - 'payroll': Payroll summary and analysis
        - 'cashflow': Cash flow statement
        - 'trial-balance': Trial balance showing all account balances
        - 'balance-sheet': Balance sheet showing assets, liabilities, and equity
        - 'revenue': Detailed revenue report with category breakdown
        - 'todays-profit-summary': Today's profit summary for quick dashboard view
        - 'grand-total': Grand total financial report
        """
        try:
            report_type = pk
            period = request.query_params.get('period', 'today')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            category_id = request.query_params.get('category_id')
            department_id = request.query_params.get('department_id')
            employee_id = request.query_params.get('employee_id')
            include_taxes = request.query_params.get('include_taxes', 'true').lower() == 'true'
            include_payroll = request.query_params.get('include_payroll', 'true').lower() == 'true'

            report_generator = FinancialReportGenerator()
            report_generator.set_time_period(
                period=period,
                custom_start=start_date,
                custom_end=end_date
            )

            if report_type == 'expenses':
                result = report_generator.generate_expense_report(
                    category_id=category_id
                )
            elif report_type == 'profit':
                result = report_generator.generate_profit_report()
            elif report_type == 'payroll':
                result = report_generator.generate_payroll_report(
                    department_id=department_id,
                    employee_id=employee_id
                )
            elif report_type == 'cashflow':
                result = report_generator.generate_cashflow_statement()
            elif report_type == 'trial-balance':
                result = report_generator.generate_trial_balance()
            elif report_type == 'balance-sheet':
                result = report_generator.generate_balance_sheet()
            elif report_type == 'revenue':
                result = report_generator.generate_revenue_report(
                    category_id=category_id
                )
            elif report_type == 'todays-profit-summary':
                result = report_generator.generate_todays_profit_summary()
            elif report_type == 'grand-total':
                result = self._generate_grand_total_financial_report(report_generator, period)
            else:
                return Response(
                    {'error': f'Unknown report type: {report_type}'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            return Response({
                'status': 'success',
                'data': result,
                'metadata': {
                    'generated_at': timezone.now().isoformat(),
                    'report_type': f'financial_{report_type}',
                    'filters': {
                        'period': period,
                        'start_date': report_generator.start_date.isoformat() if report_generator.start_date else None,
                        'end_date': report_generator.end_date.isoformat() if report_generator.end_date else None,
                        'category_id': category_id,
                        'department_id': department_id,
                        'employee_id': employee_id,
                        'include_taxes': include_taxes,
                        'include_payroll': include_payroll
                    }
                }
            })

        except ValueError as e:
            return Response(
                {'error': f'Invalid parameter value: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.exception(f'Error generating financial report: {str(e)}')
            return Response(
                {'error': 'Failed to generate financial report'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def export(self, request: Request, pk: str = None) -> Response:
        """
        Export financial reports as CSV or PDF.
        Query param: format=csv|pdf (default: csv)
        """
        try:
            report_type = pk
            format_ = request.query_params.get('format', 'csv').lower()
            period = request.query_params.get('period', 'today')
            start_date = request.query_params.get('start_date')
            end_date = request.query_params.get('end_date')
            category_id = request.query_params.get('category_id')
            
            report_generator = FinancialReportGenerator()
            report_generator.set_time_period(period=period, custom_start=start_date, custom_end=end_date)
            
            if report_type == 'expenses':
                data = report_generator.generate_expense_report(category_id=category_id)
                template = 'expenses_report'
            elif report_type == 'profit':
                data = report_generator.generate_profit_report()
                template = 'profit_report'
            elif report_type == 'payroll':
                data = report_generator.generate_payroll_report(department_id=department_id, employee_id=employee_id)
                template = 'payroll_report'
            elif report_type == 'cashflow':
                data = report_generator.generate_cashflow_statement()
                template = 'cashflow_statement'
            elif report_type == 'trial-balance':
                data = report_generator.generate_trial_balance()
                template = 'trial_balance'
            elif report_type == 'balance-sheet':
                data = report_generator.generate_balance_sheet()
                template = 'balance_sheet'
            elif report_type == 'revenue':
                data = report_generator.generate_revenue_report(category_id=category_id)
                template = 'revenue_report'
            elif report_type == 'todays-profit-summary':
                data = report_generator.generate_todays_profit_summary()
                template = 'todays_profit_summary'
            else:
                return Response({'error': 'Unsupported report type for export'}, status=400)
            
            exporter = ReportExporter()
            filename = f"financial_{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            if format_ == 'pdf':
                file_path = exporter.export_to_pdf('financial', data, template, filename, request=request)
                content_type = 'application/pdf'
            else:
                file_path = exporter.export_to_csv('financial', data, filename)
                content_type = 'text/csv'
            
            if not os.path.exists(file_path):
                return Response({'error': 'Failed to generate export file'}, status=500)
            
            response = FileResponse(
                open(file_path, 'rb'),
                content_type=content_type
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}.{format_}"'
            return response
            
        except Exception as e:
            logger.exception(f'Error exporting financial report: {str(e)}')
            return Response({'error': 'Failed to export report'}, status=500)

    def _generate_grand_total_financial_report(self, report_generator, period):
        """Generate grand total financial report."""
        expenses = report_generator.generate_expense_report()
        profit = report_generator.generate_profit_report()
        payroll = report_generator.generate_payroll_report()
        
        return {
            'report_type': 'grand_total_financial',
            'expenses': expenses,
            'profit': profit,
            'payroll': payroll,
            'period': period
        }


class DashboardReportViewSet(viewsets.ViewSet):
    """
    ViewSet for dashboard reports.
    Provides standardized endpoints for dashboard overview and analytics.
    """
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request: Request) -> Response:
        """
        List available dashboard report types.
        """
        return Response({
            'available_reports': ['overview'],
            'description': 'Use /dashboard/overview/ to get dashboard data'
        })

    @action(detail=False, methods=['get'])
    def overview(self, request: Request) -> Response:
        """
        Generate dashboard overview data.
        Provides a comprehensive snapshot of business performance.
        """
        try:
            period = request.query_params.get('period', 'today')
            branch_id = request.query_params.get('branch_id')
            sales_generator = SalesReportGenerator(branch=branch_id)
            inventory_generator = InventoryReportGenerator()
            financial_generator = FinancialReportGenerator()
            sales_generator.set_time_period(period=period)
            inventory_generator.set_time_period(period=period)
            financial_generator.set_time_period(period=period)
            sales_summary = sales_generator.generate_sales_summary(group_by='day')
            top_products = sales_generator.generate_sales_by_product(top_n=5)
            top_profitable_products = self._get_top_profitable_products(sales_generator)
            sales_by_category = sales_generator.generate_sales_by_category()
            stock_alerts = inventory_generator.generate_stock_alerts(threshold_percentage=20.0)
            profit_data = financial_generator.generate_profit_report()
            expense_data = financial_generator.generate_expense_report()
            # Add recent orders
            recent_orders_qs = Order.objects.select_related('branch').prefetch_related('customers').order_by('-created_at')[:5]
            recent_orders = []
            for order in recent_orders_qs:
                customer_name = None
                customers = list(order.customers.all())
                if customers:
                    customer_name = getattr(customers[0], 'name', None) or str(customers[0])
                recent_orders.append({
                    'order_number': order.order_number,
                    'created_at': order.created_at,
                    'total_amount': float(order.total_amount),
                    'status': order.status,
                    'customer': customer_name
                })
            dashboard_data = {
                'report_type': 'dashboard_overview',
                'time_period': {
                    'period': period,
                    'start_date': sales_generator.start_date.isoformat() if sales_generator.start_date else None,
                    'end_date': sales_generator.end_date.isoformat() if sales_generator.end_date else None
                },
                'sales': {
                    'summary': sales_summary,
                    'top_products': top_products,
                    'top_profitable_products': top_profitable_products,
                    'by_category': sales_by_category
                },
                'inventory': {
                    'stock_alerts': stock_alerts
                },
                'financial': {
                    'profit': profit_data,
                    'expenses': expense_data
                },
                'recent_orders': recent_orders
            }
            return Response({
                'status': 'success',
                'data': dashboard_data,
                'metadata': {
                    'generated_at': timezone.now().isoformat(),
                    'report_type': 'dashboard_overview',
                    'filters': {
                        'period': period,
                        'branch_id': branch_id
                    }
                }
            })
        except Exception as e:
            logger.exception(f'Error generating dashboard overview: {str(e)}')
            return Response(
                {'error': 'Failed to generate dashboard overview'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def export(self, request: Request) -> Response:
        """
        Export dashboard overview as CSV or PDF.
        Query param: format=csv|pdf (default: csv)
        """
        try:
            format_ = request.query_params.get('format', 'csv').lower()
            period = request.query_params.get('period', 'today')
            branch_id = request.query_params.get('branch_id')
            sales_generator = SalesReportGenerator(branch=branch_id)
            inventory_generator = InventoryReportGenerator()
            financial_generator = FinancialReportGenerator()
            sales_generator.set_time_period(period=period)
            inventory_generator.set_time_period(period=period)
            financial_generator.set_time_period(period=period)
            data = {
                'sales_summary': sales_generator.generate_sales_summary(group_by='day'),
                'top_products': sales_generator.generate_sales_by_product(top_n=5),
                'stock_alerts': inventory_generator.generate_stock_alerts(threshold_percentage=20.0),
                'profit_data': financial_generator.generate_profit_report(),
                'expense_data': financial_generator.generate_expense_report()
            }
            exporter = ReportExporter()
            filename = f"dashboard_overview_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            if format_ == 'pdf':
                file_path = exporter.export_to_pdf('dashboard', data, 'dashboard_overview', filename, request=request)
                content_type = 'application/pdf'
            else:
                file_path = exporter.export_dashboard_to_csv(data, filename)
                content_type = 'text/csv'
            if not os.path.exists(file_path):
                return Response({'error': 'Failed to generate export file'}, status=500)
            response = FileResponse(
                open(file_path, 'rb'),
                content_type=content_type
            )
            response['Content-Disposition'] = f'attachment; filename="{filename}.{format_}"'
            return response
        except Exception as e:
            logger.exception(f'Error exporting dashboard: {str(e)}')
            return Response({'error': 'Failed to export dashboard'}, status=500)

    def _get_top_profitable_products(self, sales_generator):
        """Get top profitable products for dashboard."""
        try:
            return []
        except Exception as e:
            logger.warning(f'Could not get top profitable products: {e}')
            return []

    @action(detail=False, methods=['get'])
    def test(self, request: Request) -> Response:
        """
        Test action to verify action registration is working.
        """
        return Response({'message': 'Test action works!'}) 