from django.urls import path, include
from rest_framework.routers import DefaultRouter, SimpleRouter
from . import views
from .views import CatalogView, StockCountViewSet, InventoryItemCreateAPIView

# Create a router for our viewsets
router = DefaultRouter()
router.register(r'categories', views.CategoryViewSet, basename='category')
router.register(r'suppliers', views.SupplierViewSet, basename='supplier')
router.register(r'units', views.UnitOfMeasureViewSet, basename='units')
router.register(r'products', views.ProductViewSet, basename='product')
router.register(r'transactions', views.InventoryTransactionViewSet, basename='transaction')
router.register(r'adjustments', views.InventoryAdjustmentViewSet, basename='adjustment')
router.register(r'batches', views.BatchViewSet, basename='batch')
router.register(r'batch-stock', views.BatchStockViewSet, basename='batch-stock')
router.register(r'stock-counts', StockCountViewSet, basename='stockcount')
router.register(r'purchase-orders', views.PurchaseOrderViewSet, basename='purchaseorder')
router.register(r'stock-transfers', views.StockTransferViewSet, basename='stocktransfer')
router.register(r'allergies', views.AllergyViewSet, basename='allergy')

# Restaurant-specific routers
router.register(r'menus', views.MenuViewSet, basename='menu')
router.register(r'menu-items', views.MenuItemViewSet, basename='menu-item')
router.register(r'recipes', views.RecipeViewSet, basename='recipe')
router.register(r'modifiers', views.ModifierViewSet, basename='modifier')
router.register(r'modifier-options', views.ModifierOptionViewSet, basename='modifier-option')
router.register(r'menu-item-modifiers', views.MenuItemModifierViewSet, basename='menu-item-modifier')

# Nested router for batch stock under batches
batch_router = SimpleRouter()
batch_router.register(
    r'batches/(?P<batch_pk>[^/.]+)/stock',
    views.BatchStockViewSet,
    basename='batch-stock-nested'
)

# API endpoints
urlpatterns = [
    path('', include(router.urls)),
    path('', include(batch_router.urls)),
    path('catalog/', CatalogView.as_view(), name='catalog'),
    
    # Product endpoints
    path('products/<int:pk>/adjust-stock/', 
         views.ProductViewSet.as_view({'post': 'adjust_stock'}), 
         name='product-adjust-stock'),
    path('products/ingredients/',
         views.ProductViewSet.as_view({'get': 'ingredients'}),
         name='product-ingredients'),
    path('products/beverages/',
         views.ProductViewSet.as_view({'get': 'beverages'}),
         name='product-beverages'),
    path('products/finished-products/',
         views.ProductViewSet.as_view({'get': 'finished_products'}),
         name='product-finished-products'),
    path('products/<int:pk>/related-recipes/',
         views.ProductViewSet.as_view({'get': 'related_recipes'}),
         name='product-related-recipes'),
    path('products/<int:pk>/usage-in-recipes/',
         views.ProductViewSet.as_view({'get': 'usage_in_recipes'}),
         name='product-usage-in-recipes'),
    
    # Menu endpoints
    path('menus/<int:pk>/set-as-default/',
         views.MenuViewSet.as_view({'post': 'set_as_default'}),
         name='menu-set-as-default'),
    path('menus/<int:pk>/items/',
         views.MenuViewSet.as_view({'get': 'items'}),
         name='menu-items'),
    path('menu-stats/',
         views.MenuViewSet.as_view({'get': 'stats'}),
         name='menu-stats'),
    path('menu-activity/',
         views.MenuViewSet.as_view({'get': 'activity'}),
         name='menu-activity'),
    
    # Menu item endpoints
    path('menu-items/<int:pk>/update-cost-price/',
         views.MenuItemViewSet.as_view({'post': 'update_cost_price'}),
         name='menu-item-update-cost-price'),
    path('menu-items/<int:pk>/check-availability/',
         views.MenuItemViewSet.as_view({'get': 'check_availability'}),
         name='menu-item-check-availability'),
    path('menu-items/popular/',
         views.MenuItemViewSet.as_view({'get': 'popular'}),
         name='menu-items-popular'),
    
    # Recipe endpoints
    path('recipes/<int:pk>/ingredients/',
         views.RecipeViewSet.as_view({'get': 'ingredients'}),
         name='recipe-ingredients'),
    path('recipes/<int:pk>/add-ingredient/',
         views.RecipeViewSet.as_view({'post': 'add_ingredient'}),
         name='recipe-add-ingredient'),
    
    # Adjustment endpoints
    path('adjustments/<int:pk>/approve/', 
         views.InventoryAdjustmentViewSet.as_view({'post': 'approve'}), 
         name='adjustment-approve'),
    path('adjustments/<int:pk>/reject/', 
         views.InventoryAdjustmentViewSet.as_view({'post': 'reject'}), 
         name='adjustment-reject'),
    
    # Batch endpoints
    path('batch-stock/expiring-soon/',
         views.BatchStockViewSet.as_view({'get': 'expiring_soon'}),
         name='batch-stock-expiring-soon'),
    path('batch-stock/low-stock/',
         views.BatchStockViewSet.as_view({'get': 'low_stock'}),
         name='batch-stock-low-stock'),
    path('batch-stock/expired/',
         views.BatchStockViewSet.as_view({'get': 'expired'}),
         name='batch-stock-expired'),
    path('items/create/', InventoryItemCreateAPIView.as_view(), name='inventory-item-create'),
]
