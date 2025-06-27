from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Sum, Count, Q, Avg

from .models import Company, Branch
from .serializers import CompanySerializer,BranchSerializer
from apps.crm.serializers import CustomerSerializer
from apps.sales.serializers import OrderSerializer
from apps.sales.models import Order
from apps.crm.models import Customer
from apps.base.utils import get_request_branch_id


class CompanyViewSet(viewsets.ModelViewSet):
    """ViewSet for managing companies."""
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active','currency','timezone']
    search_fields = ['name',
        'legal_name',
        'tax_id',
        'registration_number'
    ]
    ordering_fields = [
        'name',
        'created_at',
        'branch_count',
        'active_branch_count'
    ]
    
    def get_serializer_context(self):
        """Add request to serializer context."""
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def perform_create(self, serializer):
        """Save company with current user as creator."""
        company = serializer.save(created_by=self.request.user)
        # Create default branch for the company
        Branch.objects.create(
            company=company,
            name=f"{company.name} Main Branch",
            code="MAIN",
            is_default=True,
            created_by=self.request.user
        )

    @action(detail=True, methods=['get'])
    def branches(self, request, pk=None):
        """Get all branches for the company."""
        company = self.get_object()
        branches = company.branches.all()
        serializer = BranchSerializer(branches, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get company statistics."""
        company = self.get_object()
        data = {
            'total_branches': company.branches.count(),
            'active_branches': company.branches.filter(is_active=True).count(),
            'total_sales': company.branches.annotate(
                total_sales=Sum('orders__total_amount')
            ).aggregate(Sum('total_sales'))['total_sales__sum'] or 0,
            'total_orders': company.branches.annotate(
                total_orders=Count('orders')
            ).aggregate(Sum('total_orders'))['total_orders__sum'] or 0
        }
        return Response(data)

    def get_queryset(self):
        queryset = super().get_queryset()
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(id=branch_id)
        return queryset


class BranchViewSet(viewsets.ModelViewSet):
    """ViewSet for managing branches."""
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['company','is_active','is_default','city','country']
    search_fields = ['name','code','address','phone','email']
    ordering_fields = ['name','created_at','order_count','active_order_count','total_sales']
    
    def perform_create(self, serializer):
        """Save branch with current user as creator."""
        branch = serializer.save(created_by=self.request.user)
        # Update company metadata
        company = branch.company
        company.metadata['branch_count'] = company.branches.count()
        company.save()
    
    def perform_update(self, serializer):
        """Update branch and handle default branch changes."""
        branch = serializer.save()
        # Update company metadata
        company = branch.company
        company.metadata['branch_count'] = company.branches.count()
        company.save()

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get branch statistics."""
        branch = self.get_object()
        data = {
            'total_orders': branch.orders.count(),
            'active_orders': branch.orders.filter(
                status__in=['draft', 'confirmed', 'processing', 'ready']
            ).count(),
            'completed_orders': branch.orders.filter(
                status='completed'
            ).count(),
            'total_sales': branch.orders.filter(
                status='completed'
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
            'average_order_value': branch.orders.filter(
                status='completed'
            ).aggregate(Avg('total_amount'))['total_amount__avg'] or 0,
            'top_customers': CustomerSerializer(
                Customer.objects.filter(
                    orders__branch=branch
                ).annotate(
                    total_spent=Sum('orders__total_amount')
                ).order_by('-total_spent')[:5],
                many=True
            ).data
        }
        return Response(data)

    @action(detail=True, methods=['get'])
    def active_orders(self, request, pk=None):
        """Get active orders for the branch."""
        branch = self.get_object()
        orders = branch.orders.filter(
            status__in=['draft', 'confirmed', 'processing', 'ready']
        ).order_by('-created_at')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def recent_orders(self, request, pk=None):
        """Get recently completed orders for the branch."""
        branch = self.get_object()
        orders = branch.orders.filter(
            status='completed'
        ).order_by('-completed_at')[:10]
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_opening_hours(self, request, pk=None):
        """Update branch opening hours."""
        branch = self.get_object()
        opening_hours = request.data.get('opening_hours')
        
        if not opening_hours:
            return Response(
                {'error': 'Opening hours are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            branch.opening_hours = opening_hours
            branch.save()
            return Response({'message': 'Opening hours updated successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def update_location(self, request, pk=None):
        """Update branch location coordinates."""
        branch = self.get_object()
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if not all([latitude, longitude]):
            return Response(
                {'error': 'Latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            branch.location = {
                'latitude': float(latitude),
                'longitude': float(longitude)
            }
            branch.save()
            return Response({'message': 'Location updated successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    def get_queryset(self):
        queryset = super().get_queryset()
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(id=branch_id)
        return queryset


class BranchStatsViewSet(viewsets.ViewSet):
    """ViewSet for branch statistics."""
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get overview statistics for all branches."""
        data = {
            'total_branches': Branch.objects.count(),
            'active_branches': Branch.objects.filter(is_active=True).count(),
            'total_sales': Order.objects.filter(
                status='completed'
            ).aggregate(Sum('total_amount'))['total_amount__sum'] or 0,
            'total_orders': Order.objects.count(),
            'average_sales': Order.objects.filter(
                status='completed'
            ).aggregate(Avg('total_amount'))['total_amount__avg'] or 0,
            'top_branches': BranchSerializer(
                Branch.objects.annotate(
                    total_sales=Sum('orders__total_amount')
                ).order_by('-total_sales')[:5],
                many=True
            ).data
        }
        return Response(data)

    @action(detail=False, methods=['get'])
    def by_company(self, request):
        """Get statistics by company."""
        companies = Company.objects.annotate(
            branch_count=Count('branches'),
            active_branch_count=Count('branches', filter=Q(branches__is_active=True)),
            total_sales=Sum('branches__orders__total_amount', filter=Q(branches__orders__status='completed'))
        ).order_by('-branch_count')
        
        serializer = CompanySerializer(companies, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def by_location(self, request):
        """Get statistics by location."""
        branches = Branch.objects.filter(
            location__isnull=False
        ).annotate(
            total_sales=Sum('orders__total_amount', filter=Q(orders__status='completed'))
        ).order_by('-total_sales')
        
        serializer = BranchSerializer(branches, many=True)
        return Response(serializer.data)
