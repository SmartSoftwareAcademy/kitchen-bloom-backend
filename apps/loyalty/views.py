from rest_framework import generics
from rest_framework import viewsets
from rest_framework import permissions
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.decorators import action
from apps.sales.models import Order
from apps.crm.models import Customer

from .models import (
    LoyaltyProgram,
    LoyaltyTier,
    LoyaltyTransaction,
    LoyaltyReward,
    LoyaltyRedemption
)
from .serializers import (
    LoyaltyProgramSerializer,
    LoyaltyTierSerializer,
    LoyaltyTransactionSerializer,
    LoyaltyRewardSerializer,
    LoyaltyRedemptionSerializer
)


class LoyaltyProgramViewSet(viewsets.ModelViewSet):
    """ViewSet for managing loyalty programs."""
    queryset = LoyaltyProgram.objects.all()
    serializer_class = LoyaltyProgramSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'program_type',
        'status',
        'branch'
    ]
    search_fields = ['name', 'description']
    ordering_fields = ['created_at', 'updated_at']

    def perform_create(self, serializer):
        """Save the program with the current user as the creator."""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def process_order(self, request, pk=None):
        """Process loyalty points for a completed order."""
        program = self.get_object()
        order_id = request.data.get('order_id')
        
        if not order_id:
            return Response(
                {'error': 'order_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            order = Order.objects.get(id=order_id)
            points = program.process_order_points(order)
            return Response({'points_earned': points})
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class LoyaltyTierViewSet(viewsets.ModelViewSet):
    """ViewSet for managing loyalty tiers."""
    queryset = LoyaltyTier.objects.all()
    serializer_class = LoyaltyTierSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'program',
        'minimum_points'
    ]
    search_fields = ['name', 'program__name']
    ordering_fields = ['minimum_points']

    def perform_create(self, serializer):
        """Save the tier with the current user as the creator."""
        serializer.save(created_by=self.request.user)


class LoyaltyTransactionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing loyalty transactions."""
    queryset = LoyaltyTransaction.objects.all()
    serializer_class = LoyaltyTransactionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'customer',
        'program',
        'transaction_type'
    ]
    search_fields = [
        'customer__name',
        'program__name',
        'notes'
    ]
    ordering_fields = ['created_at']

    def perform_create(self, serializer):
        """Save the transaction with the current user as the creator."""
        serializer.save(created_by=self.request.user)


class LoyaltyRewardViewSet(viewsets.ModelViewSet):
    """ViewSet for managing loyalty rewards."""
    queryset = LoyaltyReward.objects.all()
    serializer_class = LoyaltyRewardSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'program',
        'is_active'
    ]
    search_fields = ['name', 'program__name']
    ordering_fields = ['created_at']

    def perform_create(self, serializer):
        """Save the reward with the current user as the creator."""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'])
    def redeem(self, request, pk=None):
        """Process reward redemption."""
        reward = self.get_object()
        customer_id = request.data.get('customer_id')
        transaction_id = request.data.get('transaction_id')
        
        if not customer_id or not transaction_id:
            return Response(
                {'error': 'customer_id and transaction_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            customer = Customer.objects.get(id=customer_id)
            transaction = LoyaltyTransaction.objects.get(id=transaction_id)
            
            # Create redemption
            reward.redeem(customer, transaction)
            
            return Response(
                {'message': 'Reward redeemed successfully'},
                status=status.HTTP_200_OK
            )
        except (Customer.DoesNotExist, LoyaltyTransaction.DoesNotExist):
            return Response(
                {'error': 'Customer or transaction not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class LoyaltyRedemptionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing loyalty redemptions."""
    queryset = LoyaltyRedemption.objects.all()
    serializer_class = LoyaltyRedemptionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'customer',
        'reward'
    ]
    search_fields = [
        'customer__name',
        'reward__name'
    ]
    ordering_fields = ['created_at']

    def perform_create(self, serializer):
        """Save the redemption with the current user as the creator."""
        serializer.save(created_by=self.request.user)


class CustomerLoyaltyView(generics.RetrieveAPIView):
    """View to get customer's loyalty information."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, customer_id):
        try:
            customer = Customer.objects.get(id=customer_id)
            program = customer.loyalty_program
            
            data = {
                'customer': {
                    'id': customer.id,
                    'name': str(customer),
                    'total_points': customer.total_points,
                    'current_tier': {
                        'id': customer.loyalty_tier.id if customer.loyalty_tier else None,
                        'name': str(customer.loyalty_tier) if customer.loyalty_tier else None
                    }
                },
                'program': {
                    'id': program.id,
                    'name': program.name,
                    'type': program.program_type,
                    'points_per_dollar': float(program.points_per_dollar),
                    'minimum_points_for_reward': program.minimum_points_for_reward
                },
                'recent_transactions': LoyaltyTransactionSerializer(
                    customer.loyalty_transactions.all().order_by('-created_at')[:5],
                    many=True
                ).data,
                'available_rewards': LoyaltyRewardSerializer(
                    program.rewards.filter(is_active=True),
                    many=True
                ).data
            }
            
            return Response(data)
        except Customer.DoesNotExist:
            return Response(
                {'error': 'Customer not found'},
                status=status.HTTP_404_NOT_FOUND
            )
