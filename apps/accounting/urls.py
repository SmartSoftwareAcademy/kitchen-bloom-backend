from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    GiftCardViewSet, GiftCardRedemptionViewSet, ExpenseCategoryViewSet, ExpenseViewSet,
    RevenueCategoryViewSet, RevenueAccountViewSet, RevenueViewSet
)

app_name = 'accounting'

# Create router and register viewsets
router = DefaultRouter()
router.register(r'gift-cards', GiftCardViewSet, basename='gift-card')
router.register(r'gift-card-redemptions', GiftCardRedemptionViewSet, basename='gift-card-redemption')
router.register(r'expense-categories', ExpenseCategoryViewSet, basename='expense-category')
router.register(r'expenses', ExpenseViewSet, basename='expense')
router.register(r'revenue-categories', RevenueCategoryViewSet, basename='revenue-category')
router.register(r'revenue-accounts', RevenueAccountViewSet, basename='revenue-account')
router.register(r'revenues', RevenueViewSet, basename='revenue')

urlpatterns = [
    # API endpoints
    path('', include(router.urls)),
    
    # Gift Card custom actions
    path('gift-cards/<int:pk>/redeem/', GiftCardViewSet.as_view({'post': 'redeem'}), name='gift-card-redeem'),
    path('gift-cards/<int:pk>/void/', GiftCardViewSet.as_view({'post': 'void'}), name='gift-card-void'),
    path('gift-cards/<int:pk>/transactions/', GiftCardViewSet.as_view({'get': 'transactions'}), name='gift-card-transactions'),
]
