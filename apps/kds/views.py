from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404

from .models import KDSStation, KDSItem
from .serializers import (
    KDSStationSerializer,
    KDSItemSerializer,
    KDSItemStatusUpdateSerializer
)
from apps.base.utils import get_request_branch_id


class KDSStationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for KDS Stations.
    """
    queryset = KDSStation.objects.all()
    serializer_class = KDSStationSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['branch', 'station_type', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'updated_at']
    ordering = ['name']

    def get_queryset(self):
        """
        Optionally filter by branch if provided in query params.
        """
        queryset = super().get_queryset()
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        return queryset

    @action(detail=True, methods=['get'])
    def items(self, request, pk=None):
        """
        Get all items for a specific station.
        """
        station = self.get_object()
        items = station.kds_items.all()
        
        # Filter by status if provided
        status_param = request.query_params.get('status')
        if status_param:
            items = items.filter(status=status_param)
            
        serializer = KDSItemSerializer(items, many=True)
        return Response(serializer.data)


class KDSItemViewSet(viewsets.ModelViewSet):
    """
    API endpoint for KDS Items.
    """
    queryset = KDSItem.objects.all()
    serializer_class = KDSItemSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['station', 'status', 'station__branch']
    search_fields = ['name', 'description', 'kitchen_notes', 'order_item__product__name']
    ordering_fields = ['created_at', 'updated_at', 'completed_at']
    ordering = ['-created_at']

    def get_queryset(self):
        """
        Optionally filter by branch if provided in query params.
        """
        queryset = super().get_queryset()
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(station__branch_id=branch_id)
        return queryset

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """
        Update the status of a KDS item.
        """
        item = self.get_object()
        serializer = KDSItemStatusUpdateSerializer(data=request.data)
        
        if serializer.is_valid():
            serializer.update(item, serializer.validated_data)
            return Response(
                KDSItemSerializer(item).data,
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['get'])
    def active(self, request):
        """
        Get all active KDS items (not completed or cancelled).
        """
        active_items = self.get_queryset().exclude(
            status__in=['completed', 'cancelled']
        )
        serializer = self.get_serializer(active_items, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def completed(self, request):
        """
        Get all completed KDS items.
        """
        completed_items = self.get_queryset().filter(status='completed')
        serializer = self.get_serializer(completed_items, many=True)
        return Response(serializer.data)
