from rest_framework import serializers
from rest_framework.serializers import ModelSerializer
from django.utils.translation import gettext_lazy as _
from django.db.models import Q
from django.utils import timezone

from .models import TableCategory, Table, TableReservation, FloorPlan


class FloorPlanSerializer(ModelSerializer):
    """Serializer for FloorPlan model."""
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    table_count = serializers.SerializerMethodField()
    
    class Meta:
        model = FloorPlan
        fields = [
            'id', 'name', 'branch', 'branch_name', 'width', 'height',
            'background_image', 'is_active', 'table_count', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'table_count']
    
    def get_table_count(self, obj):
        return obj.tables.count()


class TableCategorySerializer(ModelSerializer):
    """Serializer for TableCategory model."""
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    table_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = TableCategory
        fields = [
            'id', 'name', 'description', 'branch', 'branch_name',
            'capacity', 'color', 'is_default', 'table_count',
            'metadata', 'created_at', 'updated_at'
        ]
        read_only_fields = ['branch_name', 'table_count']

    def validate(self, data):
        """Validate category data."""
        if 'is_default' in data and data['is_default']:
            # Ensure only one default category per branch
            branch = data.get('branch') or self.instance.branch
            if TableCategory.objects.filter(
                branch=branch,
                is_default=True
            ).exclude(pk=getattr(self.instance, 'pk', None)).exists():
                raise serializers.ValidationError(
                    {'is_default': _('Only one default category is allowed per branch')}
                )
        return data


class TableSerializer(ModelSerializer):
    """Serializer for Table model."""
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    floor_plan_name = serializers.CharField(source='floor_plan.name', read_only=True, allow_null=True)
    waiter_name = serializers.SerializerMethodField()
    current_reservation = serializers.SerializerMethodField()
    reservation_count = serializers.SerializerMethodField()
    is_available = serializers.BooleanField(read_only=True)
    is_occupied = serializers.BooleanField(read_only=True)
    is_reserved = serializers.BooleanField(read_only=True)
    is_in_maintenance = serializers.BooleanField(read_only=True)
    is_cleaning = serializers.BooleanField(read_only=True)
    combined_tables_info = serializers.SerializerMethodField()
    
    def get_waiter_name(self, obj):
        return obj.waiter.user.get_full_name() if obj.waiter and obj.waiter.user else None
    
    def get_combined_tables_info(self, obj):
        if not obj.is_combined and not obj.combined_tables.exists():
            return None
        return {
            'is_combined': obj.is_combined,
            'combined_tables': [
                {'id': t.id, 'number': t.number, 'status': t.status}
                for t in obj.combined_tables.all()
            ]
        }
    
    def get_reservation_count(self, obj):
        return obj.reservations.count()
    
    def get_current_reservation(self, obj):
        now = timezone.now()
        reservation = obj.reservations.filter(
            Q(expected_arrival_time__lte=now, departure_time__gte=now) |
            Q(expected_arrival_time__gte=now)
        ).order_by('expected_arrival_time').first()
        
        if not reservation:
            return None
        
        return {
            'id': reservation.id,
            'reservation_number': reservation.reservation_number,
            'customer_name': str(reservation.customer) if reservation.customer else None,
            'expected_arrival_time': reservation.expected_arrival_time,
            'departure_time': reservation.departure_time,
            'covers': reservation.covers,
            'status': reservation.status
        }

    class Meta:
        model = Table
        fields = [
            'id', 'branch', 'branch_name', 'category', 'category_name', 'floor_plan', 'floor_plan_name',
            'number', 'name', 'description', 'capacity', 'location', 'size', 'shape', 'status',
            'waiter', 'waiter_name', 'is_combined', 'combined_tables', 'combined_tables_info',
            'metadata', 'created_at', 'updated_at', 'last_status_change',
            'is_available', 'is_occupied', 'is_reserved', 'is_in_maintenance', 'is_cleaning',
            'current_reservation', 'reservation_count'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'last_status_change', 'is_available',
            'is_occupied', 'is_reserved', 'is_in_maintenance', 'is_cleaning',
            'current_reservation', 'reservation_count'
        ]

    def validate(self, data):
        """Validate table data."""
        if 'category' in data and 'capacity' not in data:
            # Set default capacity from category
            data['capacity'] = data['category'].capacity
        return data


class TableReservationSerializer(ModelSerializer):
    """Serializer for TableReservation model."""
    table_number = serializers.CharField(source='table.number', read_only=True)
    table_capacity = serializers.IntegerField(source='table.capacity', read_only=True)
    branch_name = serializers.CharField(source='table.branch.name', read_only=True)
    customer_name = serializers.SerializerMethodField()
    customer_email = serializers.EmailField(source='customer.email', read_only=True, allow_null=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True, allow_null=True)
    waiter_name = serializers.SerializerMethodField()
    duration_minutes = serializers.SerializerMethodField()
    
    def get_customer_name(self, obj):
        return str(obj.customer) if obj.customer else obj.guest_name
    
    def get_waiter_name(self, obj):
        return str(obj.waiter) if obj.waiter else None
    
    def get_duration_minutes(self, obj):
        if obj.expected_arrival_time and obj.departure_time:
            return int((obj.departure_time - obj.expected_arrival_time).total_seconds() / 60)
        return None
    
    def validate(self, data):
        """Validate reservation data."""
        instance = self.instance
        table = data.get('table', getattr(instance, 'table', None))
        expected_arrival_time = data.get('expected_arrival_time', getattr(instance, 'expected_arrival_time', None))
        departure_time = data.get('departure_time', getattr(instance, 'departure_time', None))
        
        if not all([table, expected_arrival_time, departure_time]):
            return data
        
        if expected_arrival_time >= departure_time:
            raise serializers.ValidationError({
                'departure_time': _('Departure time must be after expected arrival time')
            })
        
        # Check for overlapping reservations
        overlapping = TableReservation.objects.filter(
            table=table,
            status__in=['pending', 'confirmed', 'seated'],
            expected_arrival_time__lt=departure_time,
            departure_time__gt=expected_arrival_time
        )
        
        if instance and instance.pk:
            overlapping = overlapping.exclude(pk=instance.pk)
        
        if overlapping.exists():
            raise serializers.ValidationError({
                'table': _('This table is already reserved for the selected time slot')
            })
        
        return data
    
    def create(self, validated_data):
        """Create a new reservation."""
        # Set default status if not provided
        if 'status' not in validated_data:
            validated_data['status'] = 'pending'
            
        # Set created_by to current user if not provided
        if 'created_by' not in validated_data and 'request' in self.context:
            validated_data['created_by'] = self.context['request'].user
            
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        """Update reservation and handle status changes."""
        # Update status change timestamp if status is being updated
        if 'status' in validated_data and validated_data['status'] != instance.status:
            instance.status_changed_at = timezone.now()
            
        return super().update(instance, validated_data)
    
    class Meta:
        model = TableReservation
        fields = [
            'id', 'reservation_number', 'table', 'table_number', 'table_capacity', 'branch_name',
            'customer', 'customer_name', 'customer_email', 'customer_phone', 'guest_name',
            'expected_arrival_time', 'actual_arrival_time', 'departure_time', 'duration_minutes',
            'covers', 'status', 'source', 'notes', 'waiter', 'waiter_name', 'created_by',
            'created_at', 'updated_at', 'status_changed_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'reservation_number', 'duration_minutes',
            'actual_arrival_time', 'departure_time', 'status_changed_at'
        ]
        extra_kwargs = {
            'expected_arrival_time': {'required': True},
            'departure_time': {'required': True},
            'covers': {'min_value': 1}
        }

