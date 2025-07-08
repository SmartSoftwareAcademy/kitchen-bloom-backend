from datetime import timedelta
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F, Sum, Q, Count
from django.utils import timezone
from rest_framework.views import APIView

from .models import (
    Category, Product, Supplier, InventoryTransaction, InventoryAdjustment,
    UnitOfMeasure, BranchStock, Batch, BatchStock, ProductImage,
    Menu, MenuItem, Recipe, RecipeIngredient, Allergy, Modifier, ModifierOption, MenuItemModifier,
    StockCount, PurchaseOrder, StockTransfer
)
from .serializers import (
    CategorySerializer, ProductSerializer, ProductCreateSerializer, SupplierSerializer, 
    InventoryTransactionSerializer, InventoryAdjustmentSerializer,
    UnitOfMeasureSerializer, BranchStockSerializer, BatchSerializer,
    ProductImageSerializer, MenuSerializer, MenuItemSerializer, MenuItemCreateSerializer,
    RecipeSerializer, RecipeIngredientSerializer, AllergySerializer,
    ModifierSerializer, ModifierOptionSerializer, MenuItemModifierSerializer,
    StockCountSerializer, PurchaseOrderSerializer, StockTransferSerializer, InventoryItemCreateSerializer,
    MinimalCatalogProductSerializer, MinimalCatalogMenuItemSerializer
)
from apps.base.utils import get_request_branch_id


class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing product categories.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_active', 'parent', 'is_menu_category', 'is_ingredient_category']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']


class SupplierViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing suppliers.
    """
    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'contact_person', 'email', 'phone']
    ordering_fields = ['name', 'created_at']


class UnitOfMeasureViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing units of measure.
    """
    queryset = UnitOfMeasure.objects.all()
    serializer_class = UnitOfMeasureSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'code', 'symbol']
    ordering_fields = ['name', 'code']


class AllergyViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing allergies.
    """
    queryset = Allergy.objects.all()
    serializer_class = AllergySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['severity']
    search_fields = ['name', 'description', 'common_in']
    ordering_fields = ['name', 'severity', 'created_at']


class ProductViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing products.
    """
    queryset = Product.objects.select_related('category', 'supplier', 'unit_of_measure')
    serializer_class = ProductSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'category': ['exact', 'isnull'],
        'supplier': ['exact', 'isnull'],
        'is_active': ['exact'],
        'product_type': ['exact'],
        'is_available_for_sale': ['exact'],
        'is_available_for_recipes': ['exact'],
        'cost_price': ['gte', 'lte'],
        'selling_price': ['gte', 'lte'],
        'branch_stock__branch': ['exact'],
    }
    search_fields = ['name', 'SKU', 'barcode', 'description']
    ordering_fields = ['name', 'cost_price', 'selling_price', 'created_at']
    
    def get_serializer_class(self):
        """Use ProductCreateSerializer for creation."""
        if self.action == 'create':
            return ProductCreateSerializer
        return ProductSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(branch_stock__branch_id=branch_id).distinct()
        
        # Filter by stock level if specified
        stock_level = self.request.query_params.get('stock_level')
        if stock_level == 'low':
            queryset = queryset.filter(
                branch_stock__current_stock__lte=F('branch_stock__reorder_level'),
                branch_stock__is_active=True
            ).distinct()
        
        # Filter by product type
        product_type = self.request.query_params.get('product_type')
        if product_type:
            queryset = queryset.filter(product_type=product_type)
        
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=True, methods=['post'])
    def adjust_stock(self, request, pk=None):
        """
        Adjust product stock by a specific amount.
        """
        product = self.get_object()
        quantity = request.data.get('quantity')
        notes = request.data.get('notes', '')
        branch_id = request.data.get('branch_id')
        
        if quantity is None:
            return Response(
                {'detail': 'Quantity is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'Quantity must be an integer'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get or create branch stock
        if branch_id:
            try:
                branch_stock = BranchStock.objects.get(product=product, branch_id=branch_id)
            except BranchStock.DoesNotExist:
                return Response(
                    {'detail': 'Product not available at this branch'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Use the first available branch stock
            branch_stock = product.branch_stock.first()
            if not branch_stock:
                return Response(
                    {'detail': 'Product not available at any branch'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Create inventory transaction
        transaction = InventoryTransaction.objects.create(
            product=product,
            branch=branch_stock.branch,
            branch_stock=branch_stock,
            transaction_type='adjustment',
            quantity=quantity,
            notes=notes,
            created_by=request.user
        )
        
        # Update branch stock
        branch_stock.current_stock += quantity
        branch_stock.save()
        
        return Response(
            InventoryTransactionSerializer(transaction).data,
            status=status.HTTP_200_OK
        )

    @action(detail=False, methods=['get'])
    def ingredients(self, request):
        """Get all ingredients (products available for recipes)."""
        ingredients = self.get_queryset().filter(
            product_type='ingredient',
            is_available_for_recipes=True,
            is_active=True
        )
        serializer = self.get_serializer(ingredients, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def beverages(self, request):
        """Get all beverages."""
        beverages = self.get_queryset().filter(
            product_type='beverage',
            is_active=True
        )
        serializer = self.get_serializer(beverages, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def finished_products(self, request):
        """Get all finished products."""
        finished_products = self.get_queryset().filter(
            product_type='finished_product',
            is_active=True
        )
        serializer = self.get_serializer(finished_products, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def related_recipes(self, request, pk=None):
        """Get recipes that use this ingredient."""
        product = self.get_object()
        recipes = product.get_related_recipes()
        serializer = RecipeSerializer(recipes, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def usage_in_recipes(self, request, pk=None):
        """Get how this ingredient is used in recipes."""
        product = self.get_object()
        usage = product.get_usage_in_recipes()
        serializer = RecipeIngredientSerializer(usage, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def test(self, request):
        """Test endpoint to verify the viewset is working."""
        return Response({
            'message': 'ProductViewSet is working',
            'timestamp': timezone.now().isoformat()
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get inventory statistics."""
        try:
            from django.db.models import Sum, F, Q
            from datetime import datetime, timedelta
            from django.utils import timezone
            
            branch_id = get_request_branch_id(request)
            
            # Base queryset for products
            products = Product.objects.filter(is_active=True)
            branch_stocks = BranchStock.objects.filter(is_active=True, product__is_active=True)
            
            # Apply branch filter if specified
            if branch_id:
                products = products.filter(branch_stock__branch_id=branch_id).distinct()
                branch_stocks = branch_stocks.filter(branch_id=branch_id)
            
            # Calculate total items
            total_items = products.count()
            
            # Calculate low stock items (current stock <= reorder level * 1.5)
            low_stock_items = branch_stocks.filter(
                current_stock__gt=0,
                reorder_level__gt=0,
                current_stock__lte=F('reorder_level') * 1.5
            ).count()
            
            # Calculate out of stock items
            out_of_stock_items = branch_stocks.filter(current_stock__lte=0).count()
            
            # Calculate inventory value
            inventory_value = branch_stocks.aggregate(
                total_value=Sum(F('current_stock') * F('product__cost_price'))
            )['total_value'] or 0
            
            # Calculate percentages
            low_stock_percentage = round((low_stock_items / total_items * 100) if total_items > 0 else 0, 1)
            out_of_stock_percentage = round((out_of_stock_items / total_items * 100) if total_items > 0 else 0, 1)
            
            # Calculate change from last month (mock data for now)
            # In a real implementation, you would compare with historical data
            items_change = 2.5  # Mock percentage change
            value_change = 1.8   # Mock percentage change
            
            data = {
                'total_items': total_items,
                'items_change': items_change,
                'low_stock_items': low_stock_items,
                'low_stock_percentage': low_stock_percentage,
                'out_of_stock_items': out_of_stock_items,
                'out_of_stock_percentage': out_of_stock_percentage,
                'inventory_value': float(inventory_value),
                'value_change': value_change,
                'branch_id': branch_id  # Add branch_id to response for debugging
            }
            
            return Response(data)
        except Exception as e:
            import logging
            import traceback
            logger = logging.getLogger(__name__)
            logger.error(f"Error in inventory stats endpoint: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return Response(
                {'error': 'Internal server error', 'detail': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class InventoryTransactionViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing inventory transactions.
    """
    serializer_class = InventoryTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'product': ['exact'],
        'branch': ['exact'],
        'branch_stock': ['exact'],
        'transaction_type': ['exact'],
        'created_by': ['exact'],
        'created_at': ['date__gte', 'date__lte', 'date__range'],
    }
    search_fields = ['reference', 'notes', 'product__name', 'product__SKU']
    ordering_fields = ['created_at', 'quantity']

    def get_queryset(self):
        queryset = InventoryTransaction.objects.select_related(
            'product', 'created_by', 'branch', 'branch_stock'
        ).order_by('-created_at')
        
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
            
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class BatchViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing product batches/lots.
    """
    serializer_class = BatchSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'product': ['exact'],
        'is_active': ['exact'],
        'manufactured_date': ['date__gte', 'date__lte', 'date__range'],
        'expiry_date': ['date__gte', 'date__lte', 'date__range', 'isnull'],
    }
    search_fields = ['batch_number', 'notes', 'product__name', 'product__SKU']
    ordering_fields = ['batch_number', 'manufactured_date', 'expiry_date', 'created_at']
    
    def get_queryset(self):
        queryset = Batch.objects.select_related('product')
        
        # Filter by expiry status if provided
        expiry_status = self.request.query_params.get('expiry_status')
        today = timezone.now().date()
        
        if expiry_status == 'expired':
            queryset = queryset.filter(expiry_date__lt=today)
        elif expiry_status == 'expiring_soon':
            threshold = today + timedelta(days=30)  # Next 30 days
            queryset = queryset.filter(
                expiry_date__gte=today,
                expiry_date__lte=threshold
            )
        elif expiry_status == 'active':
            queryset = queryset.filter(
                Q(expiry_date__isnull=True) | Q(expiry_date__gte=today),
                is_active=True
            )
            
        return queryset
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return serializers.BatchDetailSerializer
        return self.serializer_class
    
    def perform_destroy(self, instance):
        """Prevent deletion if batch has stock or transactions."""
        if instance.branch_stock.exists():
            raise serializers.ValidationError(
                'Cannot delete a batch that has stock entries.'
            )
        instance.delete()


class BatchStockViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing batch stock levels.
    Provides endpoints for viewing and managing stock levels of product batches.
    """
    serializer_class = BranchStockSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'branch': ['exact'],
        'batch__product': ['exact'],
        'quantity': ['gt', 'lt', 'gte', 'lte'],
        'last_checked': ['date__gte', 'date__lte', 'date__range'],
    }
    search_fields = ['batch__batch_number', 'batch__product__name', 'batch__product__SKU']
    ordering_fields = ['batch__expiry_date', 'quantity', 'last_checked']
    
    def get_queryset(self):
        """
        Get queryset with optional filtering for low stock and expiry status.
        """
        queryset = BranchStock.objects.select_related('batch', 'batch__product', 'branch')
        
        # Filter by low stock - remove reference to non-existent reorder_level
        low_stock = self.request.query_params.get('low_stock', '').lower()
        if low_stock in ['true', '1', 'yes']:
            queryset = queryset.filter(quantity__lte=0)  # Consider 0 as low stock
        
        # Filter by expiry status
        expiry_status = self.request.query_params.get('expiry_status')
        today = timezone.now().date()
        
        if expiry_status == 'expired':
            queryset = queryset.filter(batch__expiry_date__lt=today)
        elif expiry_status == 'expiring_soon':
            threshold = today + timedelta(days=30)  # Next 30 days
            queryset = queryset.filter(
                batch__expiry_date__gte=today,
                batch__expiry_date__lte=threshold
            )
            
        return queryset
    
    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return serializers.BranchStockUpdateSerializer
        return self.serializer_class
    
    @action(detail=False, methods=['get'])
    def expiring_soon(self, request):
        """
        Get batches that are expiring soon (within the next 30 days).
        """
        today = timezone.now().date()
        threshold = today + timedelta(days=30)
        
        queryset = self.get_queryset().filter(
            batch__expiry_date__isnull=False,
            batch__expiry_date__gte=today,
            batch__expiry_date__lte=threshold
        ).order_by('batch__expiry_date')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        """
        Get batches that are below their reorder level.
        """
        queryset = self.get_queryset().filter(
            quantity__lte=0  # Consider 0 as low stock
        ).order_by('quantity')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def expired(self, request):
        """
        Get batches that have expired.
        """
        today = timezone.now().date()
        queryset = self.get_queryset().filter(
            batch__expiry_date__lt=today
        ).order_by('batch__expiry_date')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class InventoryAdjustmentViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing inventory adjustments.
    """
    serializer_class = InventoryAdjustmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'product': ['exact'],
        'branch': ['exact'],
        'branch_stock': ['exact'],
        'status': ['exact'],
        'requested_by': ['exact'],
        'reviewed_by': ['exact', 'isnull'],
        'created_at': ['date__gte', 'date__lte', 'date__range'],
    }
    search_fields = ['reason', 'review_notes', 'product__name', 'product__SKU']
    ordering_fields = ['created_at', 'reviewed_at', 'status']

    def get_queryset(self):
        queryset = InventoryAdjustment.objects.select_related(
            'product', 'requested_by', 'reviewed_by', 'branch', 'branch_stock'
        ).order_by('-created_at')
        
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
            
        # Filter by status if specified
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
            
        return queryset
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['request'] = self.request
        return context
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approve an inventory adjustment.
        """
        adjustment = self.get_object()
        
        if adjustment.status != 'pending':
            return Response(
                {'detail': 'Only pending adjustments can be approved'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Update the adjustment status
        adjustment.status = 'approved'
        adjustment.reviewed_by = request.user
        adjustment.reviewed_at = timezone.now()
        
        # Update branch stock instead of product stock
        if adjustment.branch_stock:
            adjustment.branch_stock.current_stock = adjustment.quantity_after
            adjustment.branch_stock.save()
        
        # Create inventory transaction
        InventoryTransaction.objects.create(
            product=adjustment.product,
            branch=adjustment.branch,
            branch_stock=adjustment.branch_stock,
            transaction_type='adjustment',
            quantity=adjustment.quantity_after - adjustment.quantity_before,
            reference=f"Adjustment #{adjustment.id}",
            notes=adjustment.reason,
            created_by=adjustment.requested_by
        )
        
        adjustment.save()
        
        return Response(
            self.get_serializer(adjustment).data,
            status=status.HTTP_200_OK
        )
    
    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """
        Reject an inventory adjustment.
        """
        adjustment = self.get_object()
        
        if adjustment.status != 'pending':
            return Response(
                {'detail': 'Only pending adjustments can be rejected'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        adjustment.status = 'rejected'
        adjustment.reviewed_by = request.user
        adjustment.reviewed_at = timezone.now()
        adjustment.review_notes = request.data.get('review_notes', '')
        adjustment.save()
        
        return Response(
            self.get_serializer(adjustment).data,
            status=status.HTTP_200_OK
        )


class MenuViewSet(viewsets.ModelViewSet):
    """ViewSet for managing menus."""
    queryset = Menu.objects.select_related('branch', 'created_by')
    serializer_class = MenuSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['branch', 'is_active', 'is_default']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'is_default']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def set_as_default(self, request, pk=None):
        """Set this menu as the default for its branch."""
        menu = self.get_object()
        Menu.objects.filter(branch=menu.branch, is_default=True).update(is_default=False)
        menu.is_default = True
        menu.save()
        return Response({'message': 'Menu set as default'})
    
    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """Get all items in this menu."""
        menu = self.get_object()
        items = menu.items.filter(is_active=True).order_by('display_order', 'name')
        serializer = MenuItemSerializer(items, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get menu statistics."""
        branch_id = get_request_branch_id(request)
        queryset = self.get_queryset()
        
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Calculate stats
        total_items = MenuItem.objects.filter(menu__in=queryset).count()
        categories = Category.objects.filter(
            menu_items__menu__in=queryset,
            is_menu_category=True
        ).distinct().count()
        
        # Calculate items change (mock data for now)
        items_change = 2.5  # This would be calculated from historical data
        
        # Get best sellers (items with most orders)
        from apps.sales.models import OrderItem
        best_sellers = OrderItem.objects.filter(
            item_type='menu_item',
            order__status='completed'
        ).values('menu_item').annotate(
            sales_count=Count('id')
        ).order_by('-sales_count')[:5].count()
        
        # Get low stock items
        low_stock_items = MenuItem.objects.filter(
            menu__in=queryset,
            is_available=True
        ).count()  # This would check actual stock levels
        
        low_stock_percentage = round((low_stock_items / total_items * 100) if total_items > 0 else 0, 1)
        
        data = {
            'totalItems': total_items,
            'itemsChange': items_change,
            'categories': categories,
            'bestSellers': best_sellers,
            'lowStockItems': low_stock_items,
            'lowStockPercentage': low_stock_percentage
        }
        
        return Response(data)

    @action(detail=False, methods=['get'])
    def activity(self, request):
        """Get recent menu activity."""
        branch_id = get_request_branch_id(request)
        queryset = self.get_queryset()
        
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Get recent menu and menu item changes
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.admin.models import LogEntry
        
        menu_ct = ContentType.objects.get_for_model(Menu)
        menu_item_ct = ContentType.objects.get_for_model(MenuItem)
        
        # Get recent log entries for menus and menu items
        log_entries = LogEntry.objects.filter(
            content_type__in=[menu_ct, menu_item_ct],
            action_time__gte=timezone.now() - timezone.timedelta(days=7)
        ).select_related('user', 'content_type').order_by('-action_time')[:10]
        
        activities = []
        for entry in log_entries:
            if entry.content_type == menu_ct:
                try:
                    menu = Menu.objects.get(id=entry.object_id)
                    activities.append({
                        'id': entry.id,
                        'type': 'update' if entry.action_flag == 2 else 'create' if entry.action_flag == 1 else 'delete',
                        'title': f"Menu {entry.get_action_flag_display().title()}",
                        'description': f"{entry.get_action_flag_display().title()} menu '{menu.name}'",
                        'timestamp': entry.action_time,
                        'user': entry.user.get_full_name() if entry.user else 'System'
                    })
                except Menu.DoesNotExist:
                    continue
            elif entry.content_type == menu_item_ct:
                try:
                    menu_item = MenuItem.objects.get(id=entry.object_id)
                    activities.append({
                        'id': entry.id,
                        'type': 'update' if entry.action_flag == 2 else 'create' if entry.action_flag == 1 else 'delete',
                        'title': f"Menu Item {entry.get_action_flag_display().title()}",
                        'description': f"{entry.get_action_flag_display().title()} '{menu_item.name}'",
                        'timestamp': entry.action_time,
                        'user': entry.user.get_full_name() if entry.user else 'System'
                    })
                except MenuItem.DoesNotExist:
                    continue
        
        return Response(activities)


class MenuItemViewSet(viewsets.ModelViewSet):
    """ViewSet for managing menu items."""
    queryset = MenuItem.objects.select_related('menu', 'category', 'created_by')
    serializer_class = MenuItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['menu', 'category', 'is_available', 'is_featured']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'selling_price', 'display_order', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        menu_id = self.request.query_params.get('menu_id')
        if menu_id:
            queryset = queryset.filter(menu_id=menu_id)
        return queryset.filter(is_available=True)
    
    def get_serializer_class(self):
        """Use MenuItemCreateSerializer for creation."""
        if self.action == 'create':
            return MenuItemCreateSerializer
        return MenuItemSerializer
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def update_cost_price(self, request, pk=None):
        """Update the cost price based on current ingredient costs."""
        menu_item = self.get_object()
        menu_item.update_cost_price()
        return Response({'message': 'Cost price updated'})
    
    @action(detail=True, methods=['get'])
    def check_availability(self, request, pk=None):
        """Check ingredient availability for this menu item."""
        menu_item = self.get_object()
        branch_id = request.query_params.get('branch_id')
        if branch_id:
            from apps.branches.models import Branch
            try:
                branch = Branch.objects.get(id=branch_id)
                unavailable = menu_item.check_ingredient_availability(branch)
                return Response({
                    'available': len(unavailable) == 0,
                    'unavailable_ingredients': unavailable
                })
            except Branch.DoesNotExist:
                return Response({'error': 'Branch not found'}, status=400)
        return Response({'error': 'Branch ID required'}, status=400)

    @action(detail=False, methods=['get'])
    def popular(self, request):
        """Get popular menu items based on sales."""
        from apps.sales.models import OrderItem
        
        # Get popular items based on order count
        popular_items = OrderItem.objects.filter(
            item_type='menu_item',
            order__status='completed'
        ).values('menu_item').annotate(
            sales_count=Count('id')
        ).order_by('-sales_count')[:10]
        
        # Get the actual menu items
        menu_item_ids = [item['menu_item'] for item in popular_items]
        menu_items = MenuItem.objects.filter(id__in=menu_item_ids)
        
        # Create a mapping of sales count
        sales_count_map = {item['menu_item']: item['sales_count'] for item in popular_items}
        
        # Serialize with sales count
        serializer = self.get_serializer(menu_items, many=True)
        data = serializer.data
        
        # Add sales count to each item
        for item in data:
            item['sales_count'] = sales_count_map.get(item['id'], 0)
        
        return Response(data)


class RecipeViewSet(viewsets.ModelViewSet):
    """ViewSet for managing recipes."""
    queryset = Recipe.objects.select_related('menu_item', 'created_by')
    serializer_class = RecipeSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['menu_item', 'difficulty_level']
    search_fields = ['menu_item__name', 'instructions']
    ordering_fields = ['cooking_time', 'difficulty_level', 'created_at']
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def ingredients(self, request, pk=None):
        """Get all ingredients for this recipe."""
        recipe = self.get_object()
        ingredients = recipe.ingredients.all()
        serializer = RecipeIngredientSerializer(ingredients, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_ingredient(self, request, pk=None):
        """Add an ingredient to this recipe."""
        recipe = self.get_object()
        serializer = RecipeIngredientSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(recipe=recipe)
            return Response(serializer.data, status=201)
        return Response(serializer.errors, status=400)


class CatalogView(APIView):
    permission_classes=[permissions.IsAuthenticated]
    
    def get(self, request):
        """Get catalog of products and menu items for a specific branch, grouped by category, with pagination and filtering."""
        branch_id = get_request_branch_id(request)
        if not branch_id:
            return Response(
                {'detail': 'Branch ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Query params
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 6))
        category_filter = request.query_params.get('category')
        is_available = request.query_params.get('is_available')
        search = request.query_params.get('search')

        # --- PRODUCTS ---
        products_qs = Product.objects.filter(
            branch_stock__branch_id=branch_id,
            branch_stock__is_active=True,
            is_active=True
        ).select_related('category', 'unit_of_measure').prefetch_related('images')
        # Filtering
        if category_filter:
            products_qs = products_qs.filter(category__name=category_filter)
        if is_available is not None:
            if is_available.lower() == 'true':
                products_qs = products_qs.filter(is_available_for_sale=True)
            elif is_available.lower() == 'false':
                products_qs = products_qs.filter(is_available_for_sale=False)
        if search:
            products_qs = products_qs.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        # --- MENU ITEMS ---
        menu_items_qs = MenuItem.objects.filter(
            menu__branch_id=branch_id,
            is_available=True
        ).select_related('category', 'menu', 'created_by')
        if category_filter:
            menu_items_qs = menu_items_qs.filter(category__name=category_filter)
        if is_available is not None:
            if is_available.lower() == 'true':
                menu_items_qs = menu_items_qs.filter(is_available=True)
            elif is_available.lower() == 'false':
                menu_items_qs = menu_items_qs.filter(is_available=False)
        if search:
            menu_items_qs = menu_items_qs.filter(
                Q(name__icontains=search) | Q(description__icontains=search)
            )
        # Serialize
        products_data = MinimalCatalogProductSerializer(products_qs, many=True, context={'request': request}).data
        menu_items_data = MinimalCatalogMenuItemSerializer(menu_items_qs, many=True, context={'request': request}).data
        # Combine and group by category
        all_items = products_data + menu_items_data
        # Group by category_name
        grouped = {}
        for item in all_items:
            cat = item.get('category_name') or 'Uncategorized'
            grouped.setdefault(cat, []).append(item)
        # Pagination (flatten, then slice, then regroup)
        flat_items = [item for sublist in grouped.values() for item in sublist]
        total_count = len(flat_items)
        start = (page - 1) * page_size
        end = start + page_size
        paginated_items = flat_items[start:end]
        # Regroup paginated items
        paginated_grouped = {}
        for item in paginated_items:
            cat = item.get('category_name') or 'Uncategorized'
            paginated_grouped.setdefault(cat, []).append(item)
        return Response({
            'results': paginated_grouped,
            'count': total_count,
            'page': page,
            'page_size': page_size
        })


class ModifierViewSet(viewsets.ModelViewSet):
    """ViewSet for managing menu modifiers."""
    queryset = Modifier.objects.select_related('branch', 'created_by').prefetch_related('options', 'menu_items')
    serializer_class = ModifierSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['branch', 'modifier_type', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'display_order', 'price', 'created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def menu_items(self, request, pk=None):
        """Get menu items that use this modifier."""
        modifier = self.get_object()
        menu_items = modifier.menu_items.all()
        serializer = MenuItemSerializer(menu_items, many=True)
        return Response(serializer.data)


class ModifierOptionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing modifier options."""
    queryset = ModifierOption.objects.select_related('modifier').prefetch_related('allergens')
    serializer_class = ModifierOptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['modifier', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'display_order', 'price_adjustment', 'created_at']


class MenuItemModifierViewSet(viewsets.ModelViewSet):
    """ViewSet for managing menu item modifiers."""
    queryset = MenuItemModifier.objects.select_related('menu_item', 'modifier')
    serializer_class = MenuItemModifierSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['menu_item', 'modifier', 'is_required']
    ordering_fields = ['display_order', 'created_at']


class StockCountViewSet(viewsets.ModelViewSet):
    """API endpoint for managing stock counts."""
    queryset = StockCount.objects.select_related('product', 'branch', 'user')
    serializer_class = StockCountSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        'product': ['exact'],
        'branch': ['exact'],
        'user': ['exact'],
        'date': ['exact', 'gte', 'lte', 'range'],
    }
    search_fields = ['product__name', 'branch__name', 'notes']
    ordering_fields = ['date', 'product__name']
    ordering = ['-date']

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    queryset = PurchaseOrder.objects.all().prefetch_related('items', 'supplier')
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['supplier', 'status', 'expected_delivery']
    search_fields = ['notes', 'supplier__name']
    ordering_fields = ['created_at', 'expected_delivery', 'status']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class StockTransferViewSet(viewsets.ModelViewSet):
    queryset = StockTransfer.objects.all().select_related('source_branch', 'target_branch', 'product')
    serializer_class = StockTransferSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['source_branch', 'target_branch', 'product', 'status']
    search_fields = ['notes', 'product__name']
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class ProductImageViewSet(viewsets.ModelViewSet):
    """ViewSet for managing product images."""
    queryset = ProductImage.objects.select_related('product')
    serializer_class = ProductImageSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['product', 'is_default', 'is_active']
    search_fields = ['product__name']
    ordering_fields = ['created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        product_id = self.request.query_params.get('product_id')
        if product_id:
            queryset = queryset.filter(product_id=product_id)
        return queryset
    
    def perform_create(self, serializer):
        # If this image is being set as default, unset other defaults for this product
        if serializer.validated_data.get('is_default', False):
            product = serializer.validated_data['product']
            ProductImage.objects.filter(
                product=product,
                is_default=True
            ).update(is_default=False)
        
        serializer.save()
    
    def perform_update(self, serializer):
        # If this image is being set as default, unset other defaults for this product
        if serializer.validated_data.get('is_default', False):
            product = serializer.instance.product
            ProductImage.objects.filter(
                product=product,
                is_default=True
            ).exclude(pk=serializer.instance.pk).update(is_default=False)
        
        serializer.save()


class InventoryItemCreateAPIView(APIView):
    """API endpoint for creating either a Product or MenuItem from a unified form."""
    def post(self, request, *args, **kwargs):
        serializer = InventoryItemCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)