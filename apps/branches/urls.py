from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    CompanyViewSet,
    BranchViewSet,
    BranchStatsViewSet
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'companies', CompanyViewSet, basename='company')
router.register(r'branches', BranchViewSet, basename='branch')

# URL patterns
urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    
    # Branch statistics endpoints
    path('branch-stats/', BranchStatsViewSet.as_view({'get': 'overview'}), name='branch-stats-overview'),
    path('branch-stats/by-company/', BranchStatsViewSet.as_view({'get': 'by_company'}), name='branch-stats-by-company'),
    path('branch-stats/by-location/', BranchStatsViewSet.as_view({'get': 'by_location'}), name='branch-stats-by-location'),
    
    # Company-specific branch endpoints
    path('companies/<int:company_id>/branches/', CompanyViewSet.as_view({'get': 'branches'}), name='company-branches'),
    path('companies/<int:company_id>/stats/', CompanyViewSet.as_view({'get': 'stats'}), name='company-stats'),
    
    # Branch-specific endpoints
    path('branches/<int:branch_id>/stats/', BranchViewSet.as_view({'get': 'stats'}), name='branch-stats'),
    path('branches/<int:branch_id>/active-orders/', BranchViewSet.as_view({'get': 'active_orders'}), name='branch-active-orders'),
    path('branches/<int:branch_id>/recent-orders/', BranchViewSet.as_view({'get': 'recent_orders'}), name='branch-recent-orders'),
    path('branches/<int:branch_id>/update-opening-hours/', BranchViewSet.as_view({'post': 'update_opening_hours'}), name='branch-update-opening-hours'),
    path('branches/<int:branch_id>/update-location/', BranchViewSet.as_view({'post': 'update_location'}), name='branch-update-location')
]
