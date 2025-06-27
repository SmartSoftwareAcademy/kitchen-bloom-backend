from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    OrderViewSet,
    OrderItemViewSet,
    PaymentViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'orders', OrderViewSet, basename='order')
router.register(r'order-items', OrderItemViewSet, basename='order-item')
router.register(r'payments', PaymentViewSet, basename='payment')

# URL patterns
urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    
    # Order-specific actions
    path('orders/<int:pk>/confirm/', OrderViewSet.as_view({'post': 'confirm_order'}), name='order-confirm'),
    path('orders/<int:pk>/process-kitchen/', OrderViewSet.as_view({'post': 'process_kitchen'}), name='order-process-kitchen'),
    path('orders/<int:pk>/mark-ready/', OrderViewSet.as_view({'post': 'mark_ready'}), name='order-mark-ready'),
    path('orders/<int:pk>/split/', OrderViewSet.as_view({'post': 'split_order'}), name='order-split'),
    path('orders/<int:pk>/loyalty-info/', OrderViewSet.as_view({'get': 'loyalty_info'}), name='order-loyalty-info'),
    path('orders/<int:pk>/apply-loyalty-points/', OrderViewSet.as_view({'post': 'apply_loyalty_points'}), name='order-apply-loyalty-points'),
    path('orders/<int:pk>/process-payment/', PaymentViewSet.as_view({'post': 'process_payment'}), name='order-process-payment'),
    path('orders/<int:pk>/refund/', OrderViewSet.as_view({'post': 'refund'}), name='order-refund'),
    
    # Order item actions
    path('order-items/<int:pk>/update-status/', OrderItemViewSet.as_view({'post': 'update_status'}), name='order-item-update-status'),
    path('order-items/<int:pk>/consume-ingredients/', OrderItemViewSet.as_view({'post': 'consume_ingredients'}), name='order-item-consume-ingredients'),
    
    # Order item modifiers
    path('order-items/<int:pk>/modifiers/', OrderItemViewSet.as_view({
        'get': 'modifiers',
        'post': 'modifiers'
    }), name='order-item-modifiers'),
    path('order-items/<int:pk>/modifiers/<int:modifier_id>/', OrderItemViewSet.as_view({
        'get': 'modifier_detail',
        'put': 'modifier_detail',
        'patch': 'modifier_detail',
        'delete': 'modifier_detail'
    }), name='order-item-modifier-detail'),
]
