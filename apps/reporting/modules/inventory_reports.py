from typing import Dict, Any, Optional, override
from datetime import datetime
from django.db.models import Sum, F, Q, Subquery, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.db import models
import polars as pl

from .base_report import BaseReport
from apps.inventory.models import Product, Category, InventoryTransaction, InventoryAdjustment, BranchStock


class InventoryReportGenerator(BaseReport):
    """Generator for inventory-related reports."""
    @override
    def generate(self, *args, **kwargs) -> Dict[str, Any]:
        return {
            "stock_alerts":self.generate_stock_alerts(),
            "stock_adustments":self.generate_stock_adjustment(),
            "stock_movement":self.generate_stock_movement()
        }

    def generate_stock_alerts(self, threshold_percentage: float = 20.0) -> Dict[str, Any]:
        """
        Generate stock alerts for low and out-of-stock items.
        
        Args:
            threshold_percentage: Percentage of stock level to consider as low stock
            
        Returns:
            Dict containing out-of-stock and low-stock items
        """
        # Get all active branch stock records with product and branch info
        branch_stocks = BranchStock.objects.filter(is_active=True, product__is_active=True)

        out_of_stock = []
        low_stock = []

        for bs in branch_stocks.select_related('product', 'branch', 'product__category'):
            product = bs.product
            branch = bs.branch
            current_stock = bs.current_stock or 0
            reorder_level = bs.reorder_level or 0
            if current_stock <= 0:
                out_of_stock.append({
                    'id': product.id,
                    'name': product.name,
                    'sku': product.SKU,
                    'current_stock': 0,
                    'reorder_level': reorder_level,
                    'unit': getattr(product.unit_of_measure, 'name', None),
                    'category': product.category.name if product.category else None,
                    'branch': branch.name,
                    'branch_id': branch.id,
                    'alert_type': 'out_of_stock'
                })
            elif reorder_level > 0:
                stock_percentage = (current_stock / reorder_level) * 100 if reorder_level else 100
                if stock_percentage <= threshold_percentage:
                    low_stock.append({
                        'id': product.id,
                        'name': product.name,
                        'sku': product.SKU,
                        'current_stock': current_stock,
                        'reorder_level': reorder_level,
                        'stock_percentage': round(stock_percentage, 1),
                        'unit': getattr(product.unit_of_measure, 'name', None),
                        'category': product.category.name if product.category else None,
                        'branch': branch.name,
                        'branch_id': branch.id,
                        'alert_type': 'low_stock'
                    })

        return {
            'report_type': 'stock_alerts',
            'generated_at': datetime.now(),
            'out_of_stock': out_of_stock,
            'low_stock': low_stock,
            'out_of_stock_count': len(out_of_stock),
            'low_stock_count': len(low_stock),
            'threshold_percentage': threshold_percentage
        }
    
    def generate_stock_taking(self, category_id: Optional[int] = None, 
                             include_zero_stock: bool = False) -> Dict[str, Any]:
        """
        Generate a stock taking report.
        
        Args:
            category_id: Optional category ID to filter by
            include_zero_stock: Whether to include items with zero stock
            
        Returns:
            Dict containing stock taking data
        """
        # Base queryset for products
        from apps.inventory.models import BranchStock
        
        # Return empty result if no products exist
        if not Product.objects.exists():
            return self._empty_stock_taking_response(category_id, include_zero_stock)
            
        products = Product.objects.filter(is_active=True)
        
        # Get stock quantities from BranchStock with proper output field type
        stock_subquery = BranchStock.objects.filter(
            product=models.OuterRef('pk')
        ).values('product').annotate(
            total=Sum('current_stock', output_field=models.DecimalField())
        ).values('total')
        
        # Annotate with total stock using proper output field type
        products = products.annotate(
            total_stock=Coalesce(
                Subquery(stock_subquery, output_field=models.DecimalField(max_digits=10, decimal_places=3)),
                0,
                output_field=models.DecimalField(max_digits=10, decimal_places=3)
            )
        )
        
        # Apply filters
        if category_id:
            products = products.filter(category_id=category_id)
            
        if not include_zero_stock:
            # Filter out zero stock items using a more direct approach
            products = products.annotate(
                has_stock=ExpressionWrapper(
                    Q(total_stock__gt=0),
                    output_field=models.BooleanField()
                )
            ).filter(has_stock=True)
        
        # Get stock movement data for the period if dates are set
        movement_filters = Q()
        if self.start_date and self.end_date:
            movement_filters &= Q(created_at__range=(self.start_date, self.end_date))
        
        # Define decimal field with consistent precision
        decimal_field = models.DecimalField(max_digits=10, decimal_places=3)
        
        # Add movement data with consistent decimal types
        products = products.annotate(
            items_sold=Coalesce(
                Sum(
                    'order_items__quantity',
                    filter=Q(order_items__order__created_at__range=(self.start_date, self.end_date)) if self.start_date and self.end_date else Q(),
                    output_field=decimal_field
                ),
                0,
                output_field=decimal_field
            ),
            items_received=Coalesce(
                Sum(
                    'inventory_transactions__quantity',
                    filter=movement_filters & Q(inventory_transactions__transaction_type__in=['purchase', 'return']),
                    output_field=decimal_field
                ),
                0,
                output_field=decimal_field
            ),
            items_adjusted=Coalesce(
                Sum(
                    'inventory_transactions__quantity',
                    filter=movement_filters & Q(inventory_transactions__transaction_type='adjustment'),
                    output_field=decimal_field
                ),
                0,
                output_field=decimal_field
            ),
            items_wasted=Coalesce(
                Sum(
                    'inventory_transactions__quantity',
                    filter=movement_filters & Q(inventory_transactions__transaction_type='waste'),
                    output_field=decimal_field
                ),
                0,
                output_field=decimal_field
            )
        )
        
        # Prepare report data
        report_data = []
        categories = {}
        
        for product in products:
            # Get category name
            category_name = str(product.category) if product.category else 'Uncategorized'
            
            # Initialize category totals if not exists
            if category_name not in categories:
                categories[category_name] = {
                    'total_products': 0,
                    'total_quantity': 0,
                    'total_value': 0,
                    'items': []
                }
            
            # Add to category totals
            categories[category_name]['total_products'] += 1
            categories[category_name]['total_quantity'] += product.total_stock
            categories[category_name]['total_value'] += product.total_stock * (product.cost_price or 0)
            
            # Add product to report
            report_data.append({
                'id': product.id,
                'name': product.name,
                'SKU': product.SKU,
                'category': category_name,
                'current_stock': float(product.total_stock),  # Convert to float for JSON serialization
                'unit': str(product.unit_of_measure) if product.unit_of_measure else 'pcs',
                'cost_price': float(product.cost_price) if product.cost_price else 0.0,
                'selling_price': float(product.selling_price) if product.selling_price else 0.0,
                'total_value': float(product.total_stock * (product.cost_price or 0)),
                'items_sold': float(product.items_sold or 0),
                'items_received': float(product.items_received or 0),
                'items_adjusted': float(product.items_adjusted or 0),
                'items_wasted': float(product.items_wasted or 0)
            })
        
        # Calculate summary
        total_products = len(report_data)
        total_quantity = sum(item['current_stock'] for item in report_data)
        total_value = sum(item['total_value'] for item in report_data)
        
        # Sort report data by category and product name
        report_data.sort(key=lambda x: (x['category'], x['name']))
        
        return {
            'report_type': 'stock_taking',
            'generated_at': datetime.now(),
            'start_date': self.start_date,
            'end_date': self.end_date,
            'category_filter': Category.objects.get(id=category_id).name if category_id else None,
            'include_zero_stock': include_zero_stock,
            'total_products': total_products,
            'total_quantity': total_quantity,
            'total_value': total_value,
            'categories': categories,
            'items': report_data
        }
    
    def _empty_stock_taking_response(self, category_id: Optional[int], include_zero_stock: bool) -> Dict[str, Any]:
        """Return an empty response for stock taking report."""
        return {
            'report_type': 'stock_taking',
            'generated_at': datetime.now(),
            'start_date': self.start_date,
            'end_date': self.end_date,
            'category_filter': Category.objects.get(id=category_id).name if category_id else None,
            'include_zero_stock': include_zero_stock,
            'total_products': 0,
            'total_quantity': 0.0,
            'total_value': 0.0,
            'categories': {},
            'items': []
        }
        
    def _empty_stock_movement_response(self, product_id: Optional[int], movement_type: Optional[str]) -> Dict[str, Any]:
        """Return an empty response for stock movement report."""
        return {
            'report_type': 'stock_movement',
            'generated_at': datetime.now(),
            'start_date': self.start_date,
            'end_date': self.end_date,
            'product_filter': Product.objects.get(id=product_id).name if product_id else None,
            'movement_type_filter': movement_type,
            'summary': {
                'total_items_moved': 0,
                'total_value_moved': 0.0
            },
            'movements': []
        }
        
    def generate_stock_movement(self, product_id: Optional[int] = None, 
                              movement_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a stock movement report.
        
        Args:
            product_id: Optional product ID to filter by
            movement_type: Optional movement type to filter by
            
        Returns:
            Dict containing stock movement data
        """
        # Return empty result if no transactions exist
        if not InventoryTransaction.objects.exists():
            return self._empty_stock_movement_response(product_id, movement_type)
            
        movements = InventoryTransaction.objects.select_related('product', 'created_by', 'branch').all()
        
        # Apply filters
        if product_id:
            movements = movements.filter(product_id=product_id)
        
        if movement_type:
            movements = movements.filter(transaction_type=movement_type)  # Changed from movement_type to transaction_type
        
        # Apply date range if set
        movements = self.apply_date_filter(movements, 'created_at')
        
        # Group by product and movement type
        movement_data = movements.values(
            'product__id', 
            'product__name', 
            'product__SKU', 
            'transaction_type', 
            'branch__name'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_value=Sum(F('quantity') * F('product__cost_price'))
        ).order_by('product__name', 'transaction_type')
        
        df = pl.DataFrame(list(movement_data))
        if df.is_empty():
            return {
                'report_type': 'stock_movement',
                'generated_at': datetime.now(),
                'start_date': self.start_date,
                'end_date': self.end_date,
                'product_filter': Product.objects.get(id=product_id).name if product_id else None,
                'movement_type_filter': movement_type,
                'summary': {
                    'total_items_moved': 0,
                    'total_value_moved': 0
                },
                'movements': []
            }
        
        # Calculate summary
        summary = df.select([
            Sum('total_quantity'),
            Sum('total_value')
        ]).to_dict()
        
        return {
            'report_type': 'stock_movement',
            'generated_at': datetime.now(),
            'start_date': self.start_date,
            'end_date': self.end_date,
            'product_filter': Product.objects.get(id=product_id).name if product_id else None,
            'movement_type_filter': movement_type,
            'summary': summary,
            'movements': list(movement_data)
        }
    
    def _empty_stock_adjustment_response(self, product_id: Optional[int], 
                                      adjustment_type: Optional[str],
                                      status: Optional[str]) -> Dict[str, Any]:
        """Return an empty response for stock adjustment report."""
        try:
            product_name = Product.objects.get(id=product_id).name if product_id else None
        except Product.DoesNotExist:
            product_name = None
            
        return {
            'report_type': 'stock_adjustment',
            'generated_at': datetime.now(),
            'start_date': self.start_date,
            'end_date': self.end_date,
            'product_filter': product_name,
            'adjustment_type_filter': adjustment_type,
            'status_filter': status,
            'adjustments': [],
            'summary': {
                'total_adjustments': 0,
                'total_quantity': 0.0,
                'total_value': 0.0
            }
        }
        
    def generate_stock_adjustment(self, product_id: Optional[int] = None, 
                                adjustment_type: Optional[str] = None,
                                status: Optional[str] = None) -> Dict[str, Any]:
        """
        Generate a stock adjustment report.
        
        Args:
            product_id: Optional product ID to filter by
            adjustment_type: Optional adjustment type to filter by
            status: Optional status to filter by (pending, approved, rejected)
            
        Returns:
            Dict containing stock adjustment data
        """
        # Return empty result if no adjustments exist
        if not InventoryAdjustment.objects.exists():
            return self._empty_stock_adjustment_response(product_id, adjustment_type, status)
            
        adjustments = InventoryAdjustment.objects.select_related(
            'product', 'branch', 'requested_by', 'reviewed_by'
        )
        
        # Apply filters
        if product_id:
            adjustments = adjustments.filter(product_id=product_id)
            
        if adjustment_type:
            adjustments = adjustments.filter(transaction_type=adjustment_type)
            
        if status:
            adjustments = adjustments.filter(status=status)
            
        if self.start_date and self.end_date:
            adjustments = adjustments.filter(created_at__range=(self.start_date, self.end_date))
            
        # Get adjustment data with aggregated values
        adjustment_data = adjustments.values(
            'product__id',
            'product__name',
            'product__SKU',
            'branch__name',
            'status'
        ).annotate(
            total_quantity=Sum('quantity_after'),
            total_value=Sum(F('quantity_after') * F('product__cost_price'))
        ).order_by('product__name', 'branch__name')
        
        # Prepare report data
        data = list(adjustment_data)
        
        # Calculate summary
        summary = {
            'total_adjustments': len(data),
            'total_quantity': sum(float(item['total_quantity'] or 0) for item in data),
            'total_value': sum(float(item.get('total_value', 0) or 0) for item in data)
        }
        
        # Convert to DataFrame and check if empty
        df = pl.DataFrame(data) if data else pl.DataFrame()
        if df.is_empty() or not data:
            return {
                'report_type': 'stock_adjustment',
                'generated_at': datetime.now(),
                'start_date': self.start_date,
                'end_date': self.end_date,
                'product_filter': Product.objects.get(id=product_id).name if product_id else None,
                'status_filter': status,
                'adjustments': [],
                'summary': summary
            }
        
        return {
            'report_type': 'stock_adjustment',
            'generated_at': datetime.now(),
            'start_date': self.start_date,
            'end_date': self.end_date,
            'product_filter': Product.objects.get(id=product_id).name if product_id else None,
            'status_filter': status,
            'adjustments': data,
            'summary': summary
        }