from rest_framework import serializers
from apps.sales.models import Order, OrderItem, Payment,Dispute, Customer, Table
from apps.sales.services.payment_history import PaymentHistory
from apps.loyalty.models import LoyaltyTransaction
from django.db import transaction
from apps.inventory.models import Menu, MenuItem, Category, Recipe, RecipeIngredient, UnitOfMeasure, Product
from django.contrib.auth import get_user_model
from apps.crm.serializers import CustomerSerializer, CustomerSummarySerializer
User = get_user_model()

class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for payments."""
    payment_method_display = serializers.CharField(
        source='get_payment_method_display',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    disputes_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Payment
        fields = [
            'id', 'order', 'amount', 'method', 'payment_method_display',
            'status', 'status_display', 'transaction_reference', 'notes',
            'created_at', 'updated_at', 'disputes_count'
        ]
        read_only_fields = ['created_at', 'updated_at', 'disputes_count']

    def get_disputes_count(self, obj):
        """Get count of disputes for this payment."""
        return obj.disputes.count()

class DisputeSerializer(serializers.ModelSerializer):
    """Serializer for payment disputes."""
    payment_method = serializers.CharField(
        source='payment.method',
        read_only=True
    )
    payment_amount = serializers.DecimalField(
        source='payment.amount',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    reported_by_name = serializers.CharField(
        source='reported_by.get_full_name',
        read_only=True
    )
    resolved_by_name = serializers.CharField(
        source='resolved_by.get_full_name',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    
    class Meta:
        model = Dispute
        fields = [
            'id', 'payment', 'payment_method', 'payment_amount',
            'reason', 'evidence', 'status', 'status_display',
            'reported_by', 'reported_by_name', 'resolved_by',
            'resolved_by_name', 'resolution_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'payment', 'payment_method', 'payment_amount',
            'reported_by', 'reported_by_name', 'resolved_by',
            'resolved_by_name', 'created_at', 'updated_at'
        ]

class PaymentHistorySerializer(serializers.ModelSerializer):
    """Serializer for payment history records."""
    payment_method = serializers.CharField(
        source='payment.method',
        read_only=True
    )
    payment_amount = serializers.DecimalField(
        source='payment.amount',
        max_digits=10,
        decimal_places=2,
        read_only=True
    )
    history_type_display = serializers.CharField(
        source='get_history_type_display',
        read_only=True
    )
    
    class Meta:
        model = PaymentHistory
        fields = [
            'id', 'payment', 'payment_method', 'payment_amount',
            'history_type', 'history_type_display', 'details',
            'created_at'
        ]
        read_only_fields = [
            'id', 'payment', 'payment_method', 'payment_amount',
            'history_type', 'history_type_display', 'details',
            'created_at'
        ]

    def validate(self, data):
        """Validate dispute data."""
        if 'status' in data and data['status'] != Dispute.Status.PENDING:
            raise serializers.ValidationError(
                'Only pending disputes can be created. Use update endpoint for other statuses.'
            )
        return data

class OrderItemSerializer(serializers.ModelSerializer):
    """Serializer for order items."""
    product_name = serializers.CharField(source='product.name', read_only=True)
    product_price = serializers.DecimalField(
        source='product.selling_price',
        read_only=True,
        max_digits=10,
        decimal_places=2
    )
    menu_item_name = serializers.CharField(source='menu_item.name', read_only=True)
    menu_item_price = serializers.DecimalField(
        source='menu_item.selling_price',
        read_only=True,
        max_digits=10,
        decimal_places=2
    )
    item_name = serializers.SerializerMethodField()
    item_description = serializers.SerializerMethodField()
    item_image_url = serializers.SerializerMethodField()
    total = serializers.DecimalField(
        read_only=True,
        max_digits=10,
        decimal_places=2
    )
    modifiers = serializers.CharField(required=False, allow_blank=True)
    kitchen_display_data = serializers.SerializerMethodField()
    assigned_customer = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), required=False, allow_null=True)
    allergens = serializers.SerializerMethodField()
    kitchen_notes = serializers.CharField(required=False, allow_blank=True)
    is_custom = serializers.BooleanField(required=False, default=False)
    custom_data = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'item_type', 'product', 'product_name', 'product_price',
            'menu_item', 'menu_item_name', 'menu_item_price',
            'item_name', 'item_description', 'item_image_url',
            'quantity', 'unit_price', 'status', 'notes',
            'kitchen_notes', 'kitchen_status', 'discount_amount',
            'tax_amount', 'subtotal', 'total', 'modifiers',
            'allergens', 'kitchen_display_data',
            'ingredients_consumed', 'inventory_updated', 'assigned_customer',
            'created_at', 'updated_at', 'is_custom', 'custom_data'
        ]
        read_only_fields = ['subtotal', 'total', 'ingredients_consumed', 'inventory_updated']

    def get_item_name(self, obj):
        return obj.get_item_name()

    def get_item_description(self, obj):
        return obj.get_item_description()

    def get_item_image_url(self, obj):
        return obj.get_item_image_url()

    def validate_quantity(self, value):
        """Validate that quantity is positive and doesn't exceed available stock."""
        if value <= 0:
            raise serializers.ValidationError('Quantity must be greater than zero')
        return value

    def validate(self, data):
        """Validate item data based on item type."""
        item_type = data.get('item_type', 'product')
        
        # Validate that the appropriate item is provided based on item_type
        if item_type == 'product':
            if not data.get('product'):
                raise serializers.ValidationError('Product is required for product items')
            # Ensure menu_item is not set for product items
            data['menu_item'] = None
        elif item_type == 'menu_item':
            if not data.get('menu_item'):
                raise serializers.ValidationError('Menu item is required for menu item orders')
            # Ensure product is not set for menu_item items
            data['product'] = None
        
        # Set unit price based on item type
        if not data.get('unit_price'):
            if item_type == 'product' and data.get('product'):
                data['unit_price'] = data['product'].selling_price
            elif item_type == 'menu_item' and data.get('menu_item'):
                data['unit_price'] = data['menu_item'].selling_price
        
        return data

    def get_kitchen_display_data(self, obj):
        """Get data formatted for kitchen display."""
        return {
            'name': obj.get_item_name(),
            'quantity': obj.quantity,
            'modifiers': obj.modifiers,
            'notes': obj.kitchen_notes,
            'status': obj.get_status_display(),
            'created_at': obj.created_at
        }

    def get_allergens(self, obj):
        if obj.product and hasattr(obj.product, 'allergens'):
            return [a.name for a in obj.product.allergens.all()]
        elif obj.menu_item and hasattr(obj.menu_item, 'allergens'):
            return [a.name for a in obj.menu_item.allergens.all()]
        return []

    def to_internal_value(self, data):
        # Allow frontend to send product_id or menu_item_id
        if 'product_id' in data and 'product' not in data:
            data['product'] = data.pop('product_id')
        if 'menu_item_id' in data and 'menu_item' not in data:
            data['menu_item'] = data.pop('menu_item_id')

        # Convert kitchen_notes to string if it's not already
        if 'kitchen_notes' in data and data['kitchen_notes'] is not None:
            data = data.copy()
            if isinstance(data['kitchen_notes'], (dict, list)):
                import json
                data['kitchen_notes'] = json.dumps(data['kitchen_notes'])
            elif not isinstance(data['kitchen_notes'], str):
                data['kitchen_notes'] = str(data['kitchen_notes'])
        return super().to_internal_value(data)

    def to_representation(self, instance):
        # Keep kitchen_notes as string since it's a CharField
        return super().to_representation(instance)

class OrderSerializer(serializers.ModelSerializer):
    """Serializer for orders."""
    customers = CustomerSerializer(many=True, read_only=True)
    tables = serializers.PrimaryKeyRelatedField(queryset=Table.objects.all(), many=True, required=False)
    items = OrderItemSerializer(many=True)
    payments = serializers.SerializerMethodField()
    branch = serializers.PrimaryKeyRelatedField(queryset=Order._meta.get_field('branch').related_model.objects.all(), required=False, allow_null=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'branch', 'customers', 'tables',
            'order_type', 'status', 'delivery_address', 'subtotal', 'tax_amount',
            'discount_amount', 'total_amount', 'payment_status', 'payment_method',
            'notes', 'created_at', 'updated_at', 'items', 'payments'
        ]
        read_only_fields = fields

    def get_payments(self, obj):
        """Get payment details for the order."""
        return PaymentSerializer(obj.payments.all(), many=True).data

    def validate(self, data):
        """Validate order data."""
        # Normalize order_type before any checks
        order_type = data.get('order_type')
        if order_type:
            normalized = str(order_type).replace('-', '_').lower()
            data['order_type'] = normalized
        else:
            normalized = None
        valid_types = [c[0] for c in Order.OrderType.choices]
        if normalized and normalized not in valid_types:
            raise serializers.ValidationError({'order_type': f'"{order_type}" is not a valid choice.'})
        # Validate order type specific fields
        if normalized == Order.OrderType.DELIVERY and not data.get('delivery_address'):
            raise serializers.ValidationError(
                {'delivery_address': 'Delivery address is required for delivery orders'}
            )
        if normalized == Order.OrderType.DINE_IN and not data.get('tables'):
            raise serializers.ValidationError(
                {'tables': 'Tables are required for dine-in orders'}
            )
        # Validate payment
        if data.get('payment_status') == Order.PaymentStatus.PAID:
            if not data.get('payment_method'):
                raise serializers.ValidationError(
                    {'payment_method': 'Payment method is required for paid orders'}
                )
                
        return data

    def create(self, validated_data):
        """Create a new order."""
        with transaction.atomic():
            items_data = validated_data.pop('items', [])
            customers_data = validated_data.pop('customers', [])
            tables_data = validated_data.pop('tables', [])
            
            order = super().create(validated_data)
            
            if customers_data:
                order.customers.set(customers_data)
            if tables_data:
                order.tables.set(tables_data)

            # Create order items
            for item_data in items_data:
                allergens = item_data.pop('allergens', [])
                assigned_customer = item_data.pop('assigned_customer', None)
                order_item = OrderItem(order=order, assigned_customer=assigned_customer, **item_data)
                order_item._skip_ws = True
                order_item.save()
                if allergens:
                    order_item.allergens.set(allergens)
                # Inventory deduction for menu items
                if order_item.item_type == 'menu_item' and order_item.menu_item:
                    recipe = getattr(order_item.menu_item, 'recipe', None)
                    if recipe:
                        for recipe_ingredient in recipe.ingredients.all():
                            ingredient = recipe_ingredient.ingredient
                            branch_stock = ingredient.get_stock_for_branch(order.branch)
                            if branch_stock:
                                quantity_needed = recipe_ingredient.quantity * order_item.quantity
                                if branch_stock.current_stock >= quantity_needed:
                                    branch_stock.current_stock -= quantity_needed
                                    branch_stock.save()
            # Calculate totals and save once
            order._skip_ws = True
            order.calculate_totals()
            order.save()
            # Create loyalty points transaction if applicable
            if order.customers.exists() and order.customers.first().loyalty_program:
                try:
                    points = order.customers.first().loyalty_program.calculate_points(order.total_amount)
                    LoyaltyTransaction.objects.create(
                        customer=order.customers.first(),
                        program=order.customers.first().loyalty_program,
                        transaction_type=LoyaltyTransaction.TransactionType.EARN,
                        points=points,
                        reference_order=order,
                        notes=f'Points earned from order {order.order_number}'
                    )
                    # Update customer tier
                    order.customers.first().update_loyalty_tier()
                except Exception as e:
                    # Log error but don't fail the order creation
                    print(f"Error creating loyalty transaction: {e}")
            return order

class OrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating orders."""
    items = OrderItemSerializer(many=True)
    branch = serializers.PrimaryKeyRelatedField(queryset=Order._meta.get_field('branch').related_model.objects.all(), required=False, allow_null=True)
    customers = serializers.PrimaryKeyRelatedField(queryset=Customer.objects.all(), many=True, required=False)
    customer_ids = serializers.ListField(child=serializers.IntegerField(), required=False, write_only=True)
    tables = serializers.PrimaryKeyRelatedField(queryset=Table.objects.all(), many=True, required=False)
    payment_status = serializers.CharField(required=False, default='pending')
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, default=0)
    service_type = serializers.CharField(required=False, default='regular')

    class Meta:
        model = Order
        fields = [
            'branch', 'order_type', 'tables', 'customers', 'customer_ids', 'delivery_address', 'notes', 'items',
            'payment_status', 'subtotal', 'tax_amount', 'discount_amount', 'total_amount', 'service_type'
        ]

    def validate(self, data):
        """Validate order data."""
        # Normalize order_type before any checks
        order_type = data.get('order_type')
        if order_type:
            normalized = str(order_type).replace('-', '_').lower()
            data['order_type'] = normalized
        else:
            normalized = None
        valid_types = [c[0] for c in Order.OrderType.choices]
        if normalized and normalized not in valid_types:
            raise serializers.ValidationError({'order_type': f'"{order_type}" is not a valid choice.'})
        # Validate order type specific fields
        if normalized == Order.OrderType.DELIVERY and not data.get('delivery_address'):
            raise serializers.ValidationError(
                {'delivery_address': 'Delivery address is required for delivery orders'}
            )
        if normalized == Order.OrderType.DINE_IN and not data.get('tables'):
            raise serializers.ValidationError(
                {'tables': 'Tables are required for dine-in orders'}
            )
        return data

    def create(self, validated_data):
        """Create order with items."""
        with transaction.atomic():
            items_data = validated_data.pop('items', [])
            customers = validated_data.pop('customers', [])
            customer_ids = validated_data.pop('customer_ids', [])
            tables = validated_data.pop('tables', [])
            
            # Convert customer_ids to customers if provided
            if customer_ids and not customers:
                customers = Customer.objects.filter(id__in=customer_ids)
            
            # Create order first
            order = Order.objects.create(**validated_data)
            
            # Set many-to-many relationships efficiently
            if customers:
                order.customers.set(customers)
            if tables:
                order.tables.set(tables)
            
            # Create order items in bulk to reduce database calls
            order_items = []
            for item_data in items_data:
                allergens = item_data.pop('allergens', [])
                assigned_customer = item_data.pop('assigned_customer', None)
                is_custom = item_data.get('is_custom', False)
                custom_data = item_data.get('custom_data', None)
                if is_custom and custom_data:
                    # Create a custom MenuItem
                    menu = Menu.objects.filter(branch=order.branch, is_active=True).first()
                    if not menu:
                        menu = Menu.objects.create(
                            name='Custom Menu',
                            branch=order.branch,
                            is_active=True,
                            is_default=False,
                            created_by=order.created_by
                        )
                    # Optionally, use a special category for custom items
                    category = None
                    if 'category' in custom_data:
                        category = Category.objects.filter(name=custom_data['category']).first()
                    menu_item = MenuItem.objects.create(
                        menu=menu,
                        name=custom_data.get('name', 'Custom Item'),
                        description=custom_data.get('description', ''),
                        category=category,
                        selling_price=item_data.get('unit_price', 0),
                        cost_price=custom_data.get('cost_price', 0),
                        is_available=True,
                        created_by=order.created_by
                    )
                    # Handle recipe if provided
                    recipe_data = custom_data.get('recipe')
                    if recipe_data:
                        recipe = Recipe.objects.create(
                            menu_item=menu_item,
                            instructions=recipe_data.get('instructions', ''),
                            servings=recipe_data.get('servings', 1),
                            created_by=order.created_by
                        )
                        for ing in recipe_data.get('ingredients', []):
                            product = Product.objects.filter(id=ing['product_id']).first()
                            unit = UnitOfMeasure.objects.filter(id=ing['unit_id']).first()
                            if product and unit:
                                RecipeIngredient.objects.create(
                                    recipe=recipe,
                                    ingredient=product,
                                    quantity=ing['quantity'],
                                    unit_of_measure=unit,
                                    notes=ing.get('notes', ''),
                                    is_optional=ing.get('is_optional', False)
                                )
                    item_data['menu_item'] = menu_item
                    item_data['item_type'] = 'custom_item'
                order_item = OrderItem(order=order, assigned_customer=assigned_customer, **item_data)
                order_item._skip_ws = True
                order_items.append((order_item, allergens))
            
            # Save all order items
            for order_item, allergens in order_items:
                order_item.save()
                if allergens:
                    order_item.allergens.set(allergens)
                
                # Inventory deduction for menu items - optimized to prevent freezing
                if order_item.item_type in ['menu_item', 'custom_item'] and order_item.menu_item:
                    try:
                        recipe = getattr(order_item.menu_item, 'recipe', None)
                        if recipe:
                            # Prefetch ingredients to avoid N+1 queries
                            recipe_ingredients = recipe.ingredients.select_related('ingredient').all()
                            for recipe_ingredient in recipe_ingredients:
                                ingredient = recipe_ingredient.ingredient
                                branch_stock = ingredient.get_stock_for_branch(order.branch)
                                if branch_stock and branch_stock.current_stock >= (recipe_ingredient.quantity * order_item.quantity):
                                    quantity_needed = recipe_ingredient.quantity * order_item.quantity
                                    branch_stock.current_stock -= quantity_needed
                                    branch_stock.save(update_fields=['current_stock'])
                    except Exception as e:
                        # Log error but don't fail the order creation
                        print(f"Error updating inventory for menu item {order_item.menu_item.id}: {e}")
            
            # Calculate totals and save once
            order._skip_ws = True
            order.calculate_totals()
            order.save()
            
            # Create loyalty points transaction if applicable
            if order.customers.exists() and order.customers.first().loyalty_program:
                try:
                    points = order.customers.first().loyalty_program.calculate_points(order.total_amount)
                    LoyaltyTransaction.objects.create(
                        customer=order.customers.first(),
                        program=order.customers.first().loyalty_program,
                        transaction_type=LoyaltyTransaction.TransactionType.EARN,
                        points=points,
                        reference_order=order,
                        notes=f'Points earned from order {order.order_number}'
                    )
                    # Update customer tier
                    order.customers.first().update_loyalty_tier()
                except Exception as e:
                    # Log error but don't fail the order creation
                    print(f"Error creating loyalty transaction: {e}")
            
            return order

class OrderListSerializer(serializers.ModelSerializer):
    customers = CustomerSummarySerializer(many=True, read_only=True)
    items= OrderItemSerializer(read_only=True, many=True)
    payments= PaymentSerializer(read_only=True, many=True)
    class Meta:
        model = Order
        fields = [
            'id', 'order_number','status', 'total_amount', 'created_at','customers','items','payments'
        ]
