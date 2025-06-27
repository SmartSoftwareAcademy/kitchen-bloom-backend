from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    LoyaltyProgramViewSet,
    LoyaltyTierViewSet,
    LoyaltyTransactionViewSet,
    LoyaltyRewardViewSet,
    LoyaltyRedemptionViewSet,
    CustomerLoyaltyView
)

# Create router and register viewsets
router = DefaultRouter()
router.register(r'programs', LoyaltyProgramViewSet, basename='loyalty-program')
router.register(r'tiers', LoyaltyTierViewSet, basename='loyalty-tier')
router.register(r'transactions', LoyaltyTransactionViewSet, basename='loyalty-transaction')
router.register(r'rewards', LoyaltyRewardViewSet, basename='loyalty-reward')
router.register(r'redemptions', LoyaltyRedemptionViewSet, basename='loyalty-redemption')

# URL patterns
urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    
    # Customer loyalty info endpoint
    path('customer/<int:customer_id>/', CustomerLoyaltyView.as_view(), name='customer-loyalty'),
]
