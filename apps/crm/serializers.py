from rest_framework import serializers
from django.db.models import Sum
from apps.crm.models import Customer, CustomerTag
from apps.loyalty.models import LoyaltyProgram, LoyaltyTier
from apps.sales.models import Order


class CustomerTagSerializer(serializers.ModelSerializer):
    """Serializer for customer tags."""
    customer_count = serializers.SerializerMethodField()

    class Meta:
        model = CustomerTag
        fields = ['id', 'name', 'description', 'color', 'customer_count']
        read_only_fields = ['customer_count']

    def get_customer_count(self, obj):
        return obj.customers.count()

class CustomerContactSerializer(serializers.ModelSerializer):
    """Serializer for customer contacts."""
    full_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'full_name', 'email', 'phone',
            'alternate_phone', 'address_line1', 'address_line2',
            'city', 'state', 'postal_code', 'country', 'notes'
        ]
        read_only_fields = ['id']

    def get_full_name(self, obj):
        if obj.user:
            return obj.user.get_full_name()
        return obj.company_name or "Guest"

    def get_email(self, obj):
        if obj.user:
            return obj.user.email
        return ""

    def get_phone(self, obj):
        if obj.user and hasattr(obj.user, 'phone'):
            return obj.user.phone
        return obj.alternate_phone or ""

class CustomerAddressSerializer(serializers.ModelSerializer):
    """Serializer for customer addresses."""
    class Meta:
        model = Customer
        fields = [
            'id', 'address_line1', 'address_line2', 'city',
            'state', 'postal_code', 'country', 'notes'
        ]

class CustomerCommunicationSerializer(serializers.ModelSerializer):
    """Serializer for customer communications."""
    class Meta:
        model = Customer
        fields = [
            'id', 'communication_type', 'communication_date', 'subject', 'details', 'notes'
        ]

class CustomerLoyaltySerializer(serializers.ModelSerializer):
    """Serializer for customer loyalty information."""
    loyalty_program = serializers.StringRelatedField()
    loyalty_tier = serializers.StringRelatedField()
    total_points = serializers.SerializerMethodField()
    available_rewards = serializers.SerializerMethodField()

    class Meta:
        model = Customer
        fields = [
            'id', 'loyalty_program', 'loyalty_tier', 'total_points', 'available_rewards'
        ]

    def get_total_points(self, obj):
        return obj.loyalty_transactions.filter(
            transaction_type='earn'
        ).aggregate(Sum('points'))['points__sum'] or 0

    def get_available_rewards(self, obj):
        if obj.loyalty_program:
            rewards = obj.loyalty_program.rewards.filter(is_active=True)
            return [{
                'id': r.id,
                'name': r.name,
                'points_required': r.points_required,
                'value': r.value
            } for r in rewards]
        return []

class CustomerOrderHistorySerializer(serializers.ModelSerializer):
    """Serializer for customer order history."""
    order_type = serializers.CharField(source='get_order_type_display')
    payment_method = serializers.CharField(source='get_payment_method_display')
    status = serializers.CharField(source='get_status_display')

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'order_type', 'status', 'total_amount',
            'payment_method', 'created_at', 'notes'
        ]

class CustomerSerializer(serializers.ModelSerializer):
    """Main serializer for customer information."""
    full_name = serializers.SerializerMethodField()
    email= serializers.SerializerMethodField()
    tags = CustomerTagSerializer(many=True, read_only=True)
    contacts = CustomerContactSerializer(many=True, read_only=True)
    addresses = CustomerAddressSerializer(many=True, read_only=True)
    communications = CustomerCommunicationSerializer(many=True, read_only=True)
    loyalty = CustomerLoyaltySerializer(source='*', read_only=True)
    recent_orders = CustomerOrderHistorySerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = [
            'id', 'full_name', 'email', 'alternate_phone', 'date_of_birth',
            'gender', 'customer_type', 'customer_code', 'company_name', 'company_registration',
            'vat_number', 'website', 'address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country',
            'tax_id', 'preferred_contact_method', 'marketing_opt_in', 'notes', 'tags', 'contacts', 'addresses',
            'communications', 'loyalty', 'recent_orders'
        ]

    def get_full_name(self, obj):
        if obj.user:
            return obj.user.get_full_name()
        return obj.company_name or "Guest"
    def get_email(self, obj):
        if obj.user:
            return obj.user.email
        return "Guest"


class CustomerCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating customers."""
    class Meta:
        model = Customer
        fields = [
            'alternate_phone', 'date_of_birth',
            'gender', 'customer_type', 'company_name', 'company_registration', 'vat_number', 'website',
            'address_line1', 'address_line2', 'city', 'state', 'postal_code', 'country', 'tax_id',
            'preferred_contact_method', 'marketing_opt_in', 'notes', 'tags', 'loyalty_program'
        ]

    def validate(self, data):
        """Validate customer data."""
        if data.get('customer_type') == 'business' and not data.get('company_name'):
            raise serializers.ValidationError(
                {'company_name': 'Company name is required for business customers'}
            )
        return data

    def create(self, validated_data):
        """Create a new customer."""
        tags = validated_data.pop('tags', [])
        customer = Customer.objects.create(**validated_data)
        customer.tags.set(tags)
        return customer

    def update(self, instance, validated_data):
        """Update an existing customer."""
        tags = validated_data.pop('tags', [])
        instance = super().update(instance, validated_data)
        instance.tags.set(tags)
        return instance

class CustomerSummarySerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    class Meta:
        model = Customer
        fields = ['id', 'full_name', 'email', 'alternate_phone']

    def get_full_name(self, obj):
        if obj.user:
            return obj.user.get_full_name()
        return obj.company_name or "Guest"

    def get_email(self, obj):
        if obj.user:
            return obj.user.email
        return ""
