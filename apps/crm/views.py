from rest_framework import generics, viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Q, Count, Sum
from django.utils import timezone

from .models import Customer, CustomerTag
from .serializers import CustomerSerializer,CustomerCreateUpdateSerializer,CustomerTagSerializer
from apps.sales.models import Order
from apps.loyalty.models import LoyaltyProgram, LoyaltyTransaction
from apps.loyalty.serializers import LoyaltyTransactionSerializer

class CustomerViewSet(viewsets.ModelViewSet):
    """ViewSet for managing customers."""
    queryset = Customer.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'customer_type',
        'tags',
        'loyalty_program'
    ]
    search_fields = [
        'first_name',
        'last_name',
        'email',
        'phone',
        'business_name'
    ]
    ordering_fields = [
        'created_at',
        'last_name',
        'total_spent',
        'loyalty_points'
    ]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action in ['create', 'update', 'partial_update']:
            return CustomerCreateUpdateSerializer
        return CustomerSerializer

    def perform_create(self, serializer):
        """Save customer with current user as creator."""
        customer = serializer.save(created_by=self.request.user)
        # Update loyalty program if provided
        if serializer.validated_data.get('loyalty_program'):
            customer.update_loyalty_program()

    def perform_update(self, serializer):
        """Update customer and handle loyalty program changes."""
        customer = serializer.save()
        # Check if loyalty program changed
        if 'loyalty_program' in serializer.validated_data:
            customer.update_loyalty_program()

    @action(detail=True, methods=['get'])
    def loyalty_info(self, request, pk=None):
        """Get customer's loyalty information."""
        customer = self.get_object()
        data = {
            'total_points': customer.loyalty_points,
            'current_tier': str(customer.loyalty_tier) if customer.loyalty_tier else None,
            'points_to_next_tier': customer.points_to_next_tier,
            'recent_transactions': LoyaltyTransactionSerializer(
                customer.loyalty_transactions.all().order_by('-created_at')[:5],
                many=True
            ).data,
            'available_rewards': customer.get_available_rewards()
        }
        return Response(data)

    @action(detail=True, methods=['get'])
    def order_history(self, request, pk=None):
        """Get customer's order history."""
        customer = self.get_object()
        orders = Order.objects.filter(customer=customer).order_by('-created_at')
        serializer = CustomerOrderHistorySerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_tag(self, request, pk=None):
        """Add a tag to the customer."""
        customer = self.get_object()
        tag_id = request.data.get('tag_id')
        try:
            tag = CustomerTag.objects.get(id=tag_id)
            customer.tags.add(tag)
            return Response({'message': 'Tag added successfully'})
        except CustomerTag.DoesNotExist:
            return Response(
                {'error': 'Tag not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def remove_tag(self, request, pk=None):
        """Remove a tag from the customer."""
        customer = self.get_object()
        tag_id = request.data.get('tag_id')
        try:
            tag = CustomerTag.objects.get(id=tag_id)
            customer.tags.remove(tag)
            return Response({'message': 'Tag removed successfully'})
        except CustomerTag.DoesNotExist:
            return Response(
                {'error': 'Tag not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def update_communication(self, request, pk=None):
        """Add/update customer communication."""
        customer = self.get_object()
        communication_type = request.data.get('communication_type')
        subject = request.data.get('subject')
        details = request.data.get('details')
        
        if not all([communication_type, subject]):
            return Response(
                {'error': 'communication_type and subject are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        customer.communications.create(
            communication_type=communication_type,
            subject=subject,
            details=details,
            created_by=self.request.user
        )
        return Response({'message': 'Communication added successfully'})


class CustomerTagViewSet(viewsets.ModelViewSet):
    """ViewSet for managing customer tags."""
    queryset = CustomerTag.objects.all()
    serializer_class = CustomerTagSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = []
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'customer_count']

    def perform_create(self, serializer):
        """Save tag with current user as creator."""
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['get'])
    def customers(self, request, pk=None):
        """Get customers with this tag."""
        tag = self.get_object()
        customers = tag.customers.all()
        serializer = CustomerSerializer(customers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Get tag statistics."""
        tags = CustomerTag.objects.all().annotate(
            customer_count=Count('customers')
        ).order_by('-customer_count')
        serializer = CustomerTagSerializer(tags, many=True)
        return Response(serializer.data)


class CustomerSegmentViewSet(viewsets.ViewSet):
    """ViewSet for customer segmentation."""
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        return Response({'detail': 'Listing all customer segments is not supported. Use a specific segment endpoint.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    @action(detail=False, methods=['get'])
    def by_value(self, request):
        """Segment customers by total value."""
        customers = Customer.objects.annotate(
            total_spent=Sum('orders__total_amount')
        ).order_by('-total_spent')[:10]
        serializer = CustomerSerializer(customers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_frequency(self, request):
        """Segment customers by order frequency."""
        customers = Customer.objects.annotate(
            order_count=Count('orders')
        ).order_by('-order_count')[:10]
        serializer = CustomerSerializer(customers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_recency(self, request):
        """Segment customers by recency."""
        customers = Customer.objects.order_by('-orders__created_at')[:10]
        serializer = CustomerSerializer(customers, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_loyalty(self, request):
        """Segment customers by loyalty points."""
        customers = Customer.objects.annotate(
            total_points=Sum('loyalty_transactions__points')
        ).order_by('-total_points')[:10]
        serializer = CustomerSerializer(customers, many=True)
        return Response(serializer.data)
