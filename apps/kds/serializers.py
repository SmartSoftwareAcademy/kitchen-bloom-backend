from rest_framework import serializers
from django.utils.translation import gettext_lazy as _

from .models import KDSStation, KDSItem
from apps.sales.serializers import OrderItemSerializer


class KDSStationSerializer(serializers.ModelSerializer):
    """Serializer for KDSStation model."""
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    station_type_display = serializers.CharField(source='get_station_type_display', read_only=True)
    active_orders_count = serializers.SerializerMethodField()

    class Meta:
        model = KDSStation
        fields = [
            'id', 'name', 'description', 'branch', 'branch_name',
            'station_type', 'station_type_display', 'is_active',
            'metadata', 'created_at', 'updated_at', 'active_orders_count'
        ]
        read_only_fields = ('created_at', 'updated_at')
        extra_kwargs = {
            'branch': {'required': True},
            'station_type': {'required': True}
        }

    def get_active_orders_count(self, obj):
        return obj.active_orders.count()


class KDSItemSerializer(serializers.ModelSerializer):
    """Serializer for KDSItem model."""
    station_name = serializers.CharField(source='station.name', read_only=True)
    order_item_details = OrderItemSerializer(source='order_item', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    time_since_created = serializers.SerializerMethodField()
    time_in_status = serializers.SerializerMethodField()

    class Meta:
        model = KDSItem
        fields = [
            'id', 'name', 'description', 'station', 'station_name',
            'order_item', 'order_item_details', 'status', 'status_display',
            'kitchen_notes', 'completed_at', 'metadata', 'created_at',
            'updated_at', 'time_since_created', 'time_in_status'
        ]
        read_only_fields = ('created_at', 'updated_at', 'completed_at')
        extra_kwargs = {
            'station': {'required': True},
            'order_item': {'required': True},
            'status': {'required': True}
        }

    def get_time_since_created(self, obj):
        from django.utils import timezone
        if not obj.created_at:
            return None
        return (timezone.now() - obj.created_at).total_seconds() // 60  # minutes

    def get_time_in_status(self, obj):
        from django.utils import timezone
        if not obj.updated_at:
            return None
        return (timezone.now() - obj.updated_at).total_seconds() // 60  # minutes


class KDSItemStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating KDSItem status."""
    status = serializers.ChoiceField(
        choices=KDSItem._meta.get_field('status').choices,
        required=True
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def update(self, instance, validated_data):
        status = validated_data.get('status')
        notes = validated_data.get('notes', '')
        
        if status == 'in_progress':
            instance.mark_in_progress()
        elif status == 'completed':
            instance.mark_completed()
        elif status == 'cancelled':
            instance.mark_cancelled()
        
        if notes:
            instance.kitchen_notes = notes
            instance.save()
        
        return instance
