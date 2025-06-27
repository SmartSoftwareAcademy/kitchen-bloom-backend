from rest_framework import viewsets, permissions, status, serializers
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend

from apps.base.mixins import MultiSerializerViewSetMixin
from django.db.models import Q, Sum
from django.utils import timezone
from apps.base.utils import get_request_branch_id

from apps.tables.models import TableCategory, Table, TableReservation, FloorPlan
from apps.tables.serializers import (
    TableCategorySerializer,
    TableSerializer,
    TableReservationSerializer,
    FloorPlanSerializer
)


class FloorPlanViewSet(MultiSerializerViewSetMixin, viewsets.ModelViewSet):
    """ViewSet for managing floor plans."""
    queryset = FloorPlan.objects.all()
    serializer_class = FloorPlanSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['branch', 'is_active']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']

    def perform_create(self, serializer):
        """Save floor plan with current user as creator."""
        floor_plan = serializer.save(created_by=self.request.user)
        # Update branch metadata
        branch = floor_plan.branch
        branch.metadata['floor_plan_count'] = branch.floor_plans.count()
        branch.save()

    @action(detail=True, methods=['get'])
    def tables(self, request, pk=None):
        """Get all tables in this floor plan."""
        floor_plan = self.get_object()
        tables = floor_plan.tables.all()
        serializer = TableSerializer(tables, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_layout(self, request, pk=None):
        """Update floor plan layout with table positions."""
        floor_plan = self.get_object()
        layout_data = request.data.get('layout', {})
        
        # Update table positions
        for table_id, position in layout_data.get('tables', {}).items():
            try:
                table = Table.objects.get(id=table_id, floor_plan=floor_plan)
                table.x = position.get('x', 0)
                table.y = position.get('y', 0)
                table.rotation = position.get('rotation', 0)
                table.save()
            except Table.DoesNotExist:
                continue
                
        return Response({'status': 'layout updated'}, status=status.HTTP_200_OK)


class TableCategoryViewSet(MultiSerializerViewSetMixin, viewsets.ModelViewSet):
    """ViewSet for managing table categories."""
    queryset = TableCategory.objects.all()
    serializer_class = TableCategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['branch', 'is_default']
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at', 'table_count']

    def perform_create(self, serializer):
        """Save category with current user as creator."""
        category = serializer.save(created_by=self.request.user)
        # Update branch metadata
        branch = category.branch
        branch.metadata['table_category_count'] = branch.table_categories.count()
        branch.save()

    def perform_update(self, serializer):
        """Update category and handle default category changes."""
        category = serializer.save()
        # Update branch metadata
        branch = category.branch
        branch.metadata['table_category_count'] = branch.table_categories.count()
        branch.save()

    @action(detail=True, methods=['get'])
    def tables(self, request, pk=None):
        """Get all tables in this category."""
        category = self.get_object()
        tables = category.tables.all()
        serializer = TableSerializer(tables, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def stats(self, request, pk=None):
        """Get statistics for this category."""
        category = self.get_object()
        data = {
            'table_count': category.tables.count(),
            'available_tables': category.tables.filter(status='available').count(),
            'occupied_tables': category.tables.filter(status='occupied').count(),
            'reserved_tables': category.tables.filter(status='reserved').count(),
            'maintenance_tables': category.tables.filter(status='maintenance').count(),
            'total_capacity': category.tables.aggregate(
                total_capacity=Sum('capacity'))['total_capacity'] or 0
        }
        return Response(data)


class TableViewSet(MultiSerializerViewSetMixin, viewsets.ModelViewSet):
    """ViewSet for managing tables."""
    queryset = Table.objects.select_related(
        'branch', 'category', 'floor_plan', 'waiter'
    ).prefetch_related('combined_tables')
    
    def get_queryset(self):
        queryset = super().get_queryset()
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(branch_id=branch_id)
        
        # Filter by status if provided
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
            
        # Filter by waiter if waiter_id is provided
        waiter_id = self.request.query_params.get('waiter_id')
        if waiter_id:
            queryset = queryset.filter(waiter_id=waiter_id)
            
        # Filter by floor plan if floor_plan_id is provided
        floor_plan_id = self.request.query_params.get('floor_plan_id')
        if floor_plan_id:
            queryset = queryset.filter(floor_plan_id=floor_plan_id)
            
        return queryset

    serializer_class = TableSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['branch', 'category', 'status']
    search_fields = ['number', 'branch__name', 'category__name']
    ordering_fields = ['number', 'created_at', 'status']

    def perform_create(self, serializer):
        """Save table with current user as creator."""
        table = serializer.save(created_by=self.request.user)
        # Update category and branch metadata
        category = table.category
        if category:
            category.metadata['table_count'] = category.tables.count()
            category.save()
        branch = table.branch
        branch.metadata['table_count'] = branch.tables.count()
        branch.save()

    def perform_update(self, serializer):
        """Update table and handle status changes."""
        table = serializer.save()
        # Update category and branch metadata
        category = table.category
        if category:
            category.metadata['table_count'] = category.tables.count()
            category.save()
        branch = table.branch
        branch.metadata['table_count'] = branch.tables.count()
        branch.save()

    @action(detail=True, methods=['get'])
    def reservations(self, request, pk=None):
        """Get all reservations for this table."""
        table = self.get_object()
        reservations = table.reservations.all()
        serializer = TableReservationSerializer(reservations, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def current_reservation(self, request, pk=None):
        """Get current reservation for this table."""
        table = self.get_object()
        current_reservation = table.reservations.filter(
            status__in=['confirmed', 'arrived']
        ).first()
        if current_reservation:
            serializer = TableReservationSerializer(current_reservation)
            return Response(serializer.data)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update table status."""
        table = self.get_object()
        new_status = request.data.get('status')
        
        if not new_status or new_status not in ['available', 'occupied', 'reserved', 'maintenance', 'cleaning']:
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Handle status transitions
        if new_status == 'occupied' and table.status != 'reserved':
            return Response(
                {'error': 'Table must be reserved before it can be occupied'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Update status and track the change
        old_status = table.status
        table.status = new_status
        table.last_status_change = timezone.now()
        
        # Clear waiter if table is available
        if new_status == 'available':
            table.waiter = None
            
        table.save()
        
        # Log the status change
        # TODO: Add logging to activity log
        
        return Response(
            {
                'message': f'Table status updated from {old_status} to {new_status}',
                'table': TableSerializer(table).data
            },
            status=status.HTTP_200_OK
        )
        
    @action(detail=True, methods=['post'])
    def assign_waiter(self, request, pk=None):
        """Assign a waiter to this table."""
        table = self.get_object()
        waiter_id = request.data.get('waiter_id')
        
        if not waiter_id:
            return Response(
                {'error': 'waiter_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # In a real app, you would verify the waiter exists and has the right permissions
        table.waiter_id = waiter_id
        table.save()
        
        return Response(
            {'message': f'Waiter assigned to table {table.number}'},
            status=status.HTTP_200_OK
        )
        
    @action(detail=True, methods=['post'])
    def combine_tables(self, request, pk=None):
        """Combine this table with other tables."""
        table = self.get_object()
        table_ids = request.data.get('table_ids', [])
        
        if not table_ids:
            return Response(
                {'error': 'No tables to combine'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Get the tables to combine
            tables_to_combine = Table.objects.filter(id__in=table_ids)
            
            # Mark the main table as combined
            table.is_combined = True
            table.combined_tables.set(tables_to_combine)
            table.save()
            
            # Update status of combined tables
            tables_to_combine.update(status='combined')
            
            return Response(
                {'message': f'Successfully combined {tables_to_combine.count()} tables with {table.number}'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
    @action(detail=True, methods=['post'])
    def split_tables(self, request, pk=None):
        """Split combined tables back to individual tables."""
        table = self.get_object()
        
        if not table.is_combined:
            return Response(
                {'error': 'Table is not combined'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            # Get combined tables
            combined_tables = table.combined_tables.all()
            
            # Reset combined tables status
            combined_tables.update(status='available')
            
            # Clear combined tables and reset main table
            table.combined_tables.clear()
            table.is_combined = False
            table.save()
            
            return Response(
                {'message': f'Split {combined_tables.count()} tables from {table.number}'},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class TableReservationViewSet(MultiSerializerViewSetMixin, viewsets.ModelViewSet):
    """ViewSet for managing table reservations."""
    queryset = TableReservation.objects.select_related(
        'table', 'customer', 'waiter', 'created_by'
    )
    
    def get_queryset(self):
        queryset = super().get_queryset()
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            queryset = queryset.filter(table__branch_id=branch_id)
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date')
        end_date = self.request.query_params.get('end_date')
        
        if start_date and end_date:
            queryset = queryset.filter(
                Q(expected_arrival_time__date__range=(start_date, end_date)) |
                Q(departure_time__date__range=(start_date, end_date))
            )
        
        # Filter by status if provided
        status_param = self.request.query_params.get('status')
        if status_param:
            queryset = queryset.filter(status=status_param)
            
        # Filter by table if table_id is provided
        table_id = self.request.query_params.get('table_id')
        if table_id:
            queryset = queryset.filter(table_id=table_id)
            
        # Filter by customer if customer_id is provided
        customer_id = self.request.query_params.get('customer_id')
        if customer_id:
            queryset = queryset.filter(customer_id=customer_id)
            
        # Filter by waiter if waiter_id is provided
        waiter_id = self.request.query_params.get('waiter_id')
        if waiter_id:
            queryset = queryset.filter(waiter_id=waiter_id)
            
        return queryset.order_by('expected_arrival_time')

    serializer_class = TableReservationSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['table', 'customer', 'status', 'expected_arrival_time']
    search_fields = ['table__number', 'customer__name', 'customer__email']
    ordering_fields = ['expected_arrival_time', 'created_at', 'status']

    def perform_create(self, serializer):
        """Save reservation with current user as creator."""
        # Check if table is available
        table = serializer.validated_data['table']
        if table.status != 'available':
            raise serializers.ValidationError(
                {'table': 'Table is not available for reservation'}
            )
            
        # Create reservation
        reservation = serializer.save(created_by=self.request.user)
        # Update table status
        table.status = 'reserved'
        table.save()
        return reservation

    def perform_update(self, serializer):
        """Update reservation and handle status changes."""
        reservation = serializer.save()
        # Update table status if needed
        table = reservation.table
        if reservation.status == 'confirmed':
            table.status = 'reserved'
        elif reservation.status in ['cancelled', 'no_show']:
            table.status = 'available'
        table.save()
        return reservation

    @action(detail=True, methods=['get'])
    def table_info(self, request, pk=None):
        """Get table information for this reservation."""
        reservation = self.get_object()
        table = reservation.table
        serializer = TableSerializer(table)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update reservation status."""
        reservation = self.get_object()
        new_status = request.data.get('status')
        
        valid_statuses = ['pending', 'confirmed', 'seated', 'completed', 'cancelled', 'no_show']
        if not new_status or new_status not in valid_statuses:
            return Response(
                {'error': f'Invalid status. Must be one of: {", ".join(valid_statuses)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Handle status transitions and validations
        old_status = reservation.status
        
        # Validate status transition
        if old_status == 'completed' and new_status != 'completed':
            return Response(
                {'error': 'Cannot change status from completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if new_status == 'seated' and old_status not in ['confirmed', 'pending']:
            return Response(
                {'error': 'Only confirmed or pending reservations can be seated'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        if new_status == 'completed' and old_status != 'seated':
            return Response(
                {'error': 'Only seated reservations can be marked as completed'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Update status and timestamps
        reservation.status = new_status
        now = timezone.now()
        
        if new_status == 'seated':
            reservation.actual_arrival_time = now
        elif new_status == 'completed':
            reservation.departure_time = now
            
        reservation.status_changed_at = now
        reservation.save()
        
        # Update table status
        table = reservation.table
        if new_status == 'seated':
            table.status = 'occupied'
            table.save()
        elif new_status in ['completed', 'cancelled', 'no_show']:
            table.status = 'available'
            table.waiter = None  # Clear waiter assignment
            table.save()
        
        # TODO: Add logging to activity log
        
        return Response(
            {
                'message': f'Reservation status updated from {old_status} to {new_status}',
                'reservation': TableReservationSerializer(reservation).data
            },
            status=status.HTTP_200_OK
        )
        
    @action(detail=False, methods=['get'])
    def upcoming(self, request):
        """Get upcoming reservations."""
        now = timezone.now()
        end_time = now + timezone.timedelta(hours=24)  # Next 24 hours
        
        queryset = self.get_queryset().filter(
            expected_arrival_time__range=(now, end_time),
            status__in=['pending', 'confirmed']
        ).order_by('expected_arrival_time')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
        
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current reservations (seated)."""
        queryset = self.get_queryset().filter(
            status='seated'
        ).order_by('expected_arrival_time')
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
