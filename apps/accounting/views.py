from rest_framework import viewsets, status, permissions, mixins
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.db.models.functions import Coalesce
from datetime import datetime, timedelta
from decimal import Decimal

from .models import (
    GiftCard, GiftCardRedemption, ExpenseCategory, Expense,
    RevenueAccount, RevenueCategory, Revenue
)
from .serializers import (
    GiftCardSerializer, GiftCardRedemptionSerializer, GiftCardCreateSerializer,
    GiftCardRedeemSerializer, ExpenseCategorySerializer, ExpenseSerializer,
    RevenueAccountSerializer, RevenueCategorySerializer, RevenueSerializer
)
from apps.sales.models import Order, Payment
from apps.reporting.modules.financial_reports import FinancialReportGenerator

class GiftCardViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing gift cards.
    """
    queryset = GiftCard.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return GiftCardCreateSerializer
        elif self.action == 'redeem':
            return GiftCardRedeemSerializer
        return GiftCardSerializer
    
    def get_queryset(self):
        """
        Filter gift cards based on user permissions and query parameters.
        Customers can only see their own gift cards.
        Staff can see all gift cards or filter by customer.
        """
        queryset = GiftCard.objects.select_related('issued_to', 'issued_by')
        
        # Customers can only see their own gift cards
        if not self.request.user.is_staff:
            customer = getattr(self.request.user, 'customer_profile', None)
            if not customer:
                return GiftCard.objects.none()
            return queryset.filter(issued_to=customer)
        
        # Staff can filter by customer
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(issued_to_id=customer_id)
            
        # Filter by status
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
            
        # Filter by expiration
        expires_soon = self.request.query_params.get('expires_soon', '').lower() == 'true'
        if expires_soon:
            soon = timezone.now() + timezone.timedelta(days=30)
            queryset = queryset.filter(
                expiry_date__isnull=False,
                expiry_date__lte=soon,
                status='active'
            )
            
        return queryset
    
    def perform_create(self, serializer):
        """Set the issued_by field to the current user."""
        if not self.request.user.is_staff:
            raise PermissionDenied("Only staff can create gift cards.")
            
        serializer.save(
            issued_by=self.request.user,
            current_balance=serializer.validated_data['initial_value']
        )
    
    @action(detail=True, methods=['post'])
    def redeem(self, request, pk=None):
        """Redeem an amount from the gift card."""
        gift_card = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        amount = serializer.validated_data['amount']
        order_id = serializer.validated_data.get('order_id')
        
        with transaction.atomic():
            success = gift_card.redeem(
                amount=amount,
                order_id=order_id,
                redeemed_by=request.user
            )
            
            if not success:
                return Response(
                    {'error': 'Unable to process redemption. Check gift card status and balance.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get updated gift card data
            gift_card.refresh_from_db()
            return Response(
                GiftCardSerializer(gift_card).data,
                status=status.HTTP_200_OK
            )
    
    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        """Void the gift card."""
        if not request.user.is_staff:
            raise PermissionDenied("Only staff can void gift cards.")
            
        gift_card = self.get_object()
        
        with transaction.atomic():
            success = gift_card.void(voided_by=request.user)
            
            if not success:
                return Response(
                    {'error': 'Unable to void gift card. It may already be voided or expired.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            gift_card.refresh_from_db()
            return Response(
                GiftCardSerializer(gift_card).data,
                status=status.HTTP_200_OK
            )
    
    @action(detail=True, methods=['get'])
    def transactions(self, request, pk=None):
        """Get all transactions for this gift card."""
        gift_card = self.get_object()
        
        # Check permissions - customer can only see their own gift card transactions
        if not request.user.is_staff and gift_card.issued_to.user != request.user:
            raise PermissionDenied("You don't have permission to view these transactions.")
        
        transactions = gift_card.redemptions.all().order_by('-created_at')
        page = self.paginate_queryset(transactions)
        
        if page is not None:
            serializer = GiftCardRedemptionSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = GiftCardRedemptionSerializer(transactions, many=True)
        return Response(serializer.data)

class GiftCardRedemptionViewSet(
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet
    ):
    """
    API endpoint for viewing gift card redemptions.
    """
    serializer_class = GiftCardRedemptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        Filter redemptions based on user permissions.
        Customers can only see their own redemptions.
        Staff can see all redemptions or filter by customer.
        """
        queryset = GiftCardRedemption.objects.select_related(
            'gift_card', 'redeemed_by', 'order', 'gift_card__issued_to'
        )
        
        # Customers can only see their own redemptions
        if not self.request.user.is_staff:
            customer = getattr(self.request.user, 'customer_profile', None)
            if not customer:
                return GiftCardRedemption.objects.none()
            return queryset.filter(gift_card__issued_to=customer)
        
        # Staff can filter by customer
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(gift_card__issued_to_id=customer_id)
            
        # Filter by redemption type
        redemption_type = self.request.query_params.get('redemption_type')
        if redemption_type:
            queryset = queryset.filter(redemption_type=redemption_type)
            
        # Filter by date range
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
            
        return queryset.order_by('-created_at')

class ExpenseCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing expense categories.
    """
    queryset = ExpenseCategory.objects.all()
    serializer_class = ExpenseCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter expense categories based on user permissions."""
        if not self.request.user.is_staff:
            return ExpenseCategory.objects.none()
        return ExpenseCategory.objects.all()
    
    def perform_create(self, serializer):
        """Set the created_by field to the current user."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Set the updated_by field to the current user."""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Set the deleted_by field to the current user."""
        instance.deleted_by = self.request.user
        instance.save()

class ExpenseViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing expenses.
    """
    queryset = Expense.objects.all()
    serializer_class = ExpenseSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter expenses based on user permissions."""
        if not self.request.user.is_staff:
            return Expense.objects.none()
        return Expense.objects.all()
    
    def perform_create(self, serializer):
        """Set the created_by field to the current user."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Set the updated_by field to the current user."""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Set the deleted_by field to the current user."""
        instance.deleted_by = self.request.user
        instance.save()

class RevenueViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing revenues.
    """
    queryset = Revenue.objects.all()
    serializer_class = RevenueSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter revenues based on user permissions."""
        if not self.request.user.is_staff:
            return Revenue.objects.none()
        return Revenue.objects.all()
    
    def perform_create(self, serializer):
        """Set the created_by field to the current user."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Set the updated_by field to the current user."""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Set the deleted_by field to the current user."""
        instance.deleted_by = self.request.user
        instance.save()
    
class RevenueCategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing revenue categories.
    """
    queryset = RevenueCategory.objects.all()
    serializer_class = RevenueCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter revenue categories based on user permissions."""
        if not self.request.user.is_staff:
            return RevenueCategory.objects.none()
        return RevenueCategory.objects.all()
    
    def perform_create(self, serializer):
        """Set the created_by field to the current user."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Set the updated_by field to the current user."""
        serializer.save(updated_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Set the deleted_by field to the current user."""
        instance.deleted_by = self.request.user
        instance.save()
    
class RevenueAccountViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing revenue accounts.
    """
    queryset = RevenueAccount.objects.all()
    serializer_class = RevenueAccountSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter revenue accounts based on user permissions."""
        return RevenueAccount.objects.filter(is_active=True)
    
    def perform_create(self, serializer):
        """Set the created_by field to the current user."""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set the last_modified_by field to the current user."""
        serializer.save(last_modified_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete the revenue account."""
        instance.is_active = False
        instance.deleted_by = self.request.user
        instance.save()

    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        """Get accounting dashboard data."""
        try:
            # Get current month data
            today = timezone.now().date()
            start_of_month = today.replace(day=1)
            last_month = (start_of_month - timedelta(days=1)).replace(day=1)
            
            # Current month metrics
            current_month_revenue = Revenue.objects.filter(
                revenue_date__gte=start_of_month,
                revenue_date__lte=today,
                status='paid'
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            current_month_expenses = Expense.objects.filter(
                expense_date__gte=start_of_month,
                expense_date__lte=today,
                status__in=['approved', 'paid']
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            # Last month metrics for growth calculation
            last_month_revenue = Revenue.objects.filter(
                revenue_date__gte=last_month,
                revenue_date__lt=start_of_month,
                status='paid'
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            last_month_expenses = Expense.objects.filter(
                expense_date__gte=last_month,
                expense_date__lt=start_of_month,
                status__in=['approved', 'paid']
            ).aggregate(
                total=Coalesce(Sum('amount'), Decimal('0.00'))
            )['total']
            
            # Calculate growth percentages
            revenue_growth = 0
            if last_month_revenue > 0:
                revenue_growth = ((current_month_revenue - last_month_revenue) / last_month_revenue) * 100
                
            expense_growth = 0
            if last_month_expenses > 0:
                expense_growth = ((current_month_expenses - last_month_expenses) / last_month_expenses) * 100
            
            # Calculate profit and margin
            net_profit = current_month_revenue - current_month_expenses
            profit_margin = (net_profit / current_month_revenue * 100) if current_month_revenue > 0 else 0
            
            # Gift card data
            gift_card_balance = GiftCard.objects.filter(
                status='active',
                expiry_date__gte=today
            ).aggregate(
                total=Coalesce(Sum('current_balance'), Decimal('0.00'))
            )['total']
            
            active_gift_cards = GiftCard.objects.filter(
                status='active',
                expiry_date__gte=today
            ).count()
            
            # Top revenue categories
            top_revenue_categories = Revenue.objects.filter(
                revenue_date__gte=start_of_month,
                revenue_date__lte=today,
                status='paid'
            ).values('category__name').annotate(
                amount=Sum('amount'),
                count=Count('id')
            ).order_by('-amount')[:5]
            
            # Recent revenues
            recent_revenues = Revenue.objects.filter(
                status='paid'
            ).select_related('category').order_by('-revenue_date')[:5]
            
            # Recent expenses
            recent_expenses = Expense.objects.filter(
                status__in=['approved', 'paid']
            ).select_related('category').order_by('-expense_date')[:5]
            
            # Format the data
            dashboard_data = {
                'totalRevenue': float(current_month_revenue),
                'totalExpenses': float(current_month_expenses),
                'netProfit': float(net_profit),
                'profitMargin': float(profit_margin),
                'revenueGrowth': float(revenue_growth),
                'expenseGrowth': float(expense_growth),
                'giftCardBalance': float(gift_card_balance),
                'activeGiftCards': active_gift_cards,
                'topRevenueCategories': [
                    {
                        'id': idx + 1,
                        'name': item['category__name'] or 'Uncategorized',
                        'amount': float(item['amount']),
                        'percentage': float((item['amount'] / current_month_revenue) * 100) if current_month_revenue > 0 else 0
                    }
                    for idx, item in enumerate(top_revenue_categories)
                ],
                'recentRevenues': [
                    {
                        'id': revenue.id,
                        'description': revenue.description,
                        'amount': float(revenue.amount),
                        'revenue_date': revenue.revenue_date.isoformat(),
                        'category': revenue.category.name if revenue.category else 'Uncategorized'
                    }
                    for revenue in recent_revenues
                ],
                'recentExpenses': [
                    {
                        'id': expense.id,
                        'description': expense.description,
                        'amount': float(expense.amount),
                        'expense_date': expense.expense_date.isoformat(),
                        'status': expense.status,
                        'category': expense.category.name if expense.category else 'Uncategorized'
                    }
                    for expense in recent_expenses
                ]
            }
            
            return Response(dashboard_data)
            
        except Exception as e:
            return Response(
                {'error': f'Failed to load dashboard data: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

def get_dashboard_data(request):
    # Implement the logic to fetch and return the dashboard data
    # This is a placeholder and should be replaced with the actual implementation
    return Response({'message': 'Dashboard data fetching logic not implemented yet'})