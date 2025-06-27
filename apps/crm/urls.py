from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CustomerViewSet,
    CustomerTagViewSet,
    CustomerSegmentViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'customers', CustomerViewSet, basename='customer')
router.register(r'tags', CustomerTagViewSet, basename='customer-tag')

# URL patterns
urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    
    # Customer segments
    path('segments/', CustomerSegmentViewSet.as_view({'get': 'list'}), name='customer-segments'),
    path('segments/value/', CustomerSegmentViewSet.as_view({'get': 'by_value'}), name='customer-segments-value'),
    path('segments/frequency/', CustomerSegmentViewSet.as_view({'get': 'by_frequency'}), name='customer-segments-frequency'),
    path('segments/recency/', CustomerSegmentViewSet.as_view({'get': 'by_recency'}), name='customer-segments-recency'),
    path('segments/loyalty/', CustomerSegmentViewSet.as_view({'get': 'by_loyalty'}), name='customer-segments-loyalty'),
]
