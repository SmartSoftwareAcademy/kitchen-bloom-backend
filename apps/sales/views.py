from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .serializers import DisputeSerializer, OrderListSerializer, OrderSerializer, OrderCreateSerializer
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.sales.models import Order, OrderItem,Payment
from apps.sales.services.payment_verification import PaymentVerificationService
from apps.sales.services.payment_history import PaymentHistoryService
from apps.sales.gateways.factory import PaymentGatewayFactory
from apps.sales.serializers import (
    OrderSerializer, 
    OrderCreateSerializer, 
    OrderItemSerializer, 
    PaymentSerializer,
)
from apps.sales.models import PaymentHistory
from apps.crm.models import Customer
from apps.inventory.models import Product
from apps.loyalty.models import LoyaltyTransaction
from apps.branches.models import Branch
from apps.tables.models import Table
from apps.sales.services.accounting import create_revenue_for_order
from apps.base.utils import get_request_branch_id

class PaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for managing payments."""
    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['order', 'method', 'status', 'created_at']
    ordering_fields = ['created_at', 'amount', 'status']
    
    def create(self, request, *args, **kwargs):
        """Create a new payment."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        
        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers
        )

    @action(detail=False, methods=['post'])
    def process_payment(self, request, pk=None):
        """Process a new payment for an order."""
        order_id = pk
        amount = request.data.get('amount')
        method = request.data.get('method')
        transaction_reference = request.data.get('transaction_reference',None)
        notes = request.data.get('notes', '')
        user=request.user

        if not pk or not amount or not method:
            return Response(
                {'error': 'order id, amount, and method are required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            order = Order.objects.get(id=order_id)

            # Validate payment amount
            if amount <= 0:
                raise ValidationError('Payment amount must be greater than zero')
            
            if amount > order.total_amount:
                # get exact amount
                amount=order.total_amount
            
            if transaction_reference is None and method == 'cash':
                transaction_reference=method
            
            # Process payment through gateway
            gateway = PaymentGatewayFactory.get_gateway(method)
            if gateway:
                result = gateway.initialize_payment(amount, transaction_reference, {
                    'phone_number': request.data.get('phone_number'),
                    'currency': request.data.get('currency', 'USD'),
                    'description': f'Payment for order {order_id}'
                })
                
                if not result.get('success'):
                    payment.status = Payment.Status.FAILED
                    payment.save()
                    return Response(
                        {'error': result.get('error', 'Payment processing failed')},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Create payment
            payment = order.process_payment(amount,method,transaction_reference,notes,user)

            # Create payment history
            history_service = PaymentHistoryService(payment)
            history_service.create_history_record(
                history_type=PaymentHistory.HistoryType.PAYMENT,
                details={
                    'amount': float(amount),
                    'method': method,
                    'status': payment.status
                }
            )

            # Create revenue if payment is completed/paid
            if payment.status in ['completed','partial', 'paid']:
                create_revenue_for_order(payment.order, payment)

            return Response(PaymentSerializer(payment).data)
            
        except Order.DoesNotExist:
            return Response(
                {'error': 'Order not found'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            return Response(
                {'error': f'Payment processing failed. {e}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def process_refund(self, request, pk=None):
        """Process a refund for a payment."""
        payment = self.get_object()
        
        try:
            amount = request.data.get('amount')
            if amount and amount > payment.amount:
                return Response(
                    {'error': 'Refund amount cannot exceed original payment amount'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Process refund through gateway
            gateway = PaymentGatewayFactory.get_gateway(payment.method)
            if gateway:
                result = gateway.refund_payment(payment.transaction_reference, amount)
                
                if not result.get('success'):
                    return Response(
                        {'error': result.get('error', 'Refund processing failed')},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            # Update payment status
            payment.status = Payment.Status.REFUNDED
            payment.save()
            
            # Update order status
            payment.order.update_payment_status()
            
            # Create payment history
            history_service = PaymentHistoryService(payment)
            history_service.create_history_record(
                history_type=PaymentHistory.HistoryType.REFUND,
                details={
                    'amount': float(amount),
                    'status': payment.status
                }
            )
            
            return Response(PaymentSerializer(payment).data)
            
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            return Response(
                {'error': 'Refund processing failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        """Verify payment status with payment gateway."""
        payment = self.get_object()
        
        try:
            # Use payment verification service
            verifier = PaymentVerificationService(payment)
            is_verified = verifier.verify()
            
            # Update payment status if verification is successful
            if is_verified:
                payment.status = Payment.Status.COMPLETED
                payment.save()
                
                # Create payment history record
                history_service = PaymentHistoryService(payment)
                history_service.create_history_record(
                    history_type=PaymentHistory.HistoryType.VERIFICATION,
                    details={
                        'status': payment.status,
                        'method': payment.method
                    }
                )
                
            return Response({
                'message': 'Payment verification completed',
                'is_verified': is_verified,
                'payment': PaymentSerializer(payment).data
            })
            
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            return Response(
                {'error': 'Payment verification failed'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def dispute(self, request, pk=None):
        """Handle payment disputes."""
        try:
            payment = self.get_object()
            serializer = DisputeSerializer(data=request.data)
            if serializer.is_valid():
                dispute = serializer.save(
                    payment=payment,
                reported_by=request.user
            )
            
            # Update payment status to disputed
            payment.status = Payment.Status.DISPUTED
            payment.save()
            
            # Create payment history record
            history_service = PaymentHistoryService(payment)
            history_service.create_history_record(
                history_type=PaymentHistory.HistoryType.DISPUTE,
                details={
                    'dispute_id': dispute.id,
                    'reason': dispute.reason,
                    'status': dispute.status
                }
            )
            
            return Response({
                'message': 'Dispute created successfully',
                'dispute': DisputeSerializer(dispute).data
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['get'])
    def history(self, request):
        """Get payment history for a specific order."""
        order_id = request.query_params.get('order_id')

        if not order_id:
            return Response(
                {'error': 'order_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            payments = Payment.objects.filter(order_id=order_id)
            serializer = PaymentSerializer(payments, many=True)
            return Response(serializer.data)

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def status(self, request, pk=None):
        """Get payment status."""
        payment = self.get_object()
        return Response({
            'status': payment.status,
            'payment_method': payment.method,
            'amount': payment.amount,
            'transaction_reference': payment.transaction_reference
        })

    def perform_create(self, serializer):
        """Save payment with current user as creator."""
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        """Update payment and handle status changes."""
        payment = serializer.save()

        # Update order payment status if payment status changes
        if 'status' in serializer.validated_data:
            payment.order.update_payment_status()

    def update(self, request, *args, **kwargs):
        """Update an existing payment."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        if getattr(instance, '_prefetched_objects_cache', None):
            instance._prefetched_objects_cache = {}
        
        return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Delete a payment."""
        instance = self.get_object()
        self.perform_destroy(instance)
        
        return Response(status=status.HTTP_204_NO_CONTENT)

class OrderViewSet(viewsets.ModelViewSet):
    """ViewSet for managing orders."""
    queryset = Order.objects.all().prefetch_related('items', 'payments', 'customers', 'tables')
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['order_type', 'status', 'branch']
    search_fields = ['order_number']
    ordering_fields = ['created_at', 'total_amount', 'status', 'payment_status']

    def get_serializer_class(self):
        print("=========ACTION=========",self.action)
        """Return appropriate serializer based on action."""
        if self.action == 'create':
            return OrderCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return OrderSerializer
        elif self.action == 'list':
            return OrderListSerializer
        elif self.action == 'retrieve':
            return OrderListSerializer
        return OrderSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        payment_status = self.request.query_params.get('payment_status')
        if payment_status:
            # Accept comma-separated or list
            if ',' in payment_status:
                statuses = payment_status.split(',')
            else:
                statuses = [payment_status]
            queryset = queryset.filter(payment_status__in=statuses)
        return queryset
    
    def perform_create(self, serializer):
        """Create order with inventory tracking and set branch from header if not present."""
        branch_id = get_request_branch_id(self.request)
        if branch_id:
            try:
                branch = Branch.objects.get(id=branch_id)
                if not serializer.validated_data.get('branch'):
                    serializer.validated_data['branch'] = branch
            except Branch.DoesNotExist:
                pass  # Branch not found, continue without setting it
        
        order = serializer.save()
        if order.status == Order.Status.CONFIRMED:
            self._update_inventory_for_order(order)
    
    def perform_update(self, serializer):
        """Update order and handle inventory changes."""
        old_status = self.get_object().status
        order = serializer.save()
        
        # Update inventory when order status changes to confirmed
        if old_status != Order.Status.CONFIRMED and order.status == Order.Status.CONFIRMED:
            self._update_inventory_for_order(order)
    
    def _update_inventory_for_order(self, order):
        """Update inventory for all items in the order, and handle allergens for menu items."""
        for item in order.items.all():
            if not item.inventory_updated:
                item.consume_ingredients()
            # Propagate allergen warnings to kitchen display
            if item.menu_item and item.assigned_customer:
                customer_allergens = item.assigned_customer.allergens.all()
                if customer_allergens.exists():
                    item.allergens.set(customer_allergens)
                    item.save()
    
    @action(detail=True, methods=['post'])
    def confirm_order(self, request, pk=None):
        """Confirm an order and update inventory."""
        order = self.get_object()
        
        if order.status != Order.Status.DRAFT:
            return Response(
                {'error': 'Only draft orders can be confirmed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check ingredient availability for menu items
        unavailable_items = []
        for item in order.items.filter(item_type='menu_item'):
            if item.menu_item:
                unavailable = item.menu_item.check_ingredient_availability(order.branch)
                if unavailable:
                    unavailable_items.append({
                        'item_name': item.menu_item.name,
                        'unavailable_ingredients': unavailable
                    })
        
        if unavailable_items:
            return Response({
                'error': 'Some items are not available due to insufficient ingredients',
                'unavailable_items': unavailable_items
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Update order status
        order.status = Order.Status.CONFIRMED
        order.save()
        
        # Update inventory
        self._update_inventory_for_order(order)
        
        return Response({
            'message': 'Order confirmed and inventory updated',
            'order': OrderSerializer(order).data
        })
    
    @action(detail=True, methods=['post'])
    def process_kitchen(self, request, pk=None):
        """Process order items in kitchen and update inventory."""
        order = self.get_object()
        item_ids = request.data.get('item_ids', [])
        
        if not item_ids:
            return Response(
                {'error': 'No items specified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        processed_items = []
        for item_id in item_ids:
            try:
                item = order.items.get(id=item_id)
                if item.status == OrderItem.Status.PENDING:
                    item.status = OrderItem.Status.PREPARING
                    item.kitchen_status = OrderItem.Status.PREPARING
                    item.save()
                    
                    # Consume ingredients when preparation starts
                    if not item.inventory_updated:
                        item.consume_ingredients()
                    
                    processed_items.append(item)
            except OrderItem.DoesNotExist:
                continue
        
        return Response({
            'message': f'{len(processed_items)} items moved to preparation',
            'processed_items': OrderItemSerializer(processed_items, many=True).data
        })
    
    @action(detail=True, methods=['post'])
    def mark_ready(self, request, pk=None):
        """Mark order items as ready."""
        order = self.get_object()
        item_ids = request.data.get('item_ids', [])
        
        if not item_ids:
            return Response(
                {'error': 'No items specified'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ready_items = []
        for item_id in item_ids:
            try:
                item = order.items.get(id=item_id)
                if item.status in [OrderItem.Status.PENDING, OrderItem.Status.PREPARING]:
                    item.status = OrderItem.Status.READY
                    item.kitchen_status = OrderItem.Status.READY
                    item.save()
                    ready_items.append(item)
            except OrderItem.DoesNotExist:
                continue
        
        return Response({
            'message': f'{len(ready_items)} items marked as ready',
            'ready_items': OrderItemSerializer(ready_items, many=True).data
        })
        
    @action(detail=True, methods=['post'])
    def split_order(self, request, pk=None):
        order = self.get_object()
        item_ids = request.data.get('item_ids', [])
        new_customer_ids = request.data.get('new_customer_ids', [])
        new_table_ids = request.data.get('new_table_ids', [])
        if not item_ids:
            return Response({"error": "No items specified for splitting"}, status=status.HTTP_400_BAD_REQUEST)
        new_customers = Customer.objects.filter(id__in=new_customer_ids) if new_customer_ids else order.customers.all()
        new_tables = Table.objects.filter(id__in=new_table_ids) if new_table_ids else order.tables.all()
        try:
            with transaction.atomic():
                new_order = Order.objects.create(
                    branch=order.branch,
                    order_type=order.order_type,
                    service_type=order.service_type,
                    delivery_address=order.delivery_address,
                )
                new_order.customers.set(new_customers)
                new_order.tables.set(new_tables)
                items_to_move = order.items.filter(id__in=item_ids)
                for item in items_to_move:
                    item.order = new_order
                    item.save()
                order.calculate_totals()
                new_order.calculate_totals()
                order.save()
                new_order.save()
                return Response({
                    "message": "Order split successfully",
                    "original_order": OrderSerializer(order).data,
                    "new_order": OrderSerializer(new_order).data
                })
        except Exception as e:
            return Response({"error": f"Failed to split order: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['post'])
    def update_item(self, request, pk=None):
        """Update an order item."""
        order = self.get_object()
        item_id = request.data.get('item_id')
        updates = request.data.get('updates', {})
        
        if not item_id:
            return Response(
                {'error': 'Item ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Update item
        item = order.update_item(item_id, **updates)
        
        return Response({
            'message': 'Item updated successfully',
            'item': OrderItemSerializer(item).data
        })

    @action(detail=True, methods=['post'])
    def remove_item(self, request, pk=None):
        """Remove an item from the order."""
        order = self.get_object()
        item_id = request.data.get('item_id')
        
        if not item_id:
            return Response(
                {'error': 'Item ID is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Remove item
        order.remove_item(item_id)
        
        return Response({'message': 'Item removed successfully'})

    @action(detail=True, methods=['post'])
    def apply_discount(self, request, pk=None):
        """Apply a discount to the order."""
        order = self.get_object()
        amount = request.data.get('amount')
        discount_type = request.data.get('discount_type', 'fixed')
        
        if not amount:
            return Response(
                {'error': 'Discount amount is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        # Apply discount
        order.apply_discount(amount, discount_type)
        
        return Response({
            'message': 'Discount applied successfully',
            'order': OrderSerializer(order).data
        })

    @action(detail=True, methods=['get'])
    def kitchen_display_data(self, request, pk=None):
        """Get data formatted for kitchen display system, including allergen warnings."""
        order = self.get_object()
        data = order.get_kitchen_display_data()
        # Add allergen warnings for each item/customer
        for item in order.items.all():
            if item.allergens.exists():
                data.setdefault('allergen_warnings', []).append({
                    'item': item.get_item_name(),
                    'allergens': [a.name for a in item.allergens.all()],
                    'customers': [c.full_name for c in order.customers.all() if a in c.allergens.all()]
                })
        return Response(data)

    @action(detail=True, methods=['post'])
    def process_payment(self, request, pk=None):
        """Process payment for an existing order."""
        try:
            order = self.get_object()
            payment_method = request.data.get('method')
            payment_details = request.data.get('payment_details', {})
            notes = request.data.get('notes', '')
            reference = request.data.get('reference', '')

            # Validate required fields
            if not payment_method:
                return Response(
                    {'error': 'Payment method is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # For manual payments, require payment reference
            manual_payment_methods = ['mpesa-manual', 'bank_transfer', 'paypal', 'stripe', 'razorpay', 'flutterwave', 'paystack', 'square']
            if payment_method in manual_payment_methods and not reference:
                return Response(
                    {'error': f'Payment reference is required for {payment_method} payments'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Extract amount from payment details
            amount = None
            if payment_method == 'cash':
                amount = payment_details.get('amount')
            elif payment_method == 'mpesa-manual':
                amount = payment_details.get('amount_paid')
            else:
                # For other payment methods, use order total
                amount = order.total_amount

            if not amount or amount <= 0:
                return Response(
                    {'error': 'Valid payment amount is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Validate payment amount
            if amount > order.total_amount:
                return Response(
                    {'error': 'Payment amount cannot exceed order total'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Create payment
            payment = Payment.objects.create(
                order=order,
                amount=amount,
                method=payment_method,
                transaction_reference=reference,
                notes=notes,
                created_by=request.user,
                last_modified_by=request.user
            )

            # Process payment through gateway if applicable
            gateway = PaymentGatewayFactory.get_gateway(payment_method)
            if gateway and payment_method not in ['cash']:
                try:
                    result = gateway.initialize_payment(amount, reference, {
                        'phone_number': payment_details.get('phone_number'),
                        'currency': 'KES',
                        'description': f'Payment for order {order.order_number}'
                    })
                    
                    if not result.get('success'):
                        payment.status = Payment.Status.FAILED
                        payment.save()
                        return Response(
                            {'error': result.get('error', 'Payment processing failed')},
                            status=status.HTTP_400_BAD_REQUEST
                        )
                    
                    payment.transaction_reference = result.get('reference', reference)
                    payment.save()
                except Exception as e:
                    payment.status = Payment.Status.FAILED
                    payment.save()
                    return Response(
                        {'error': f'Payment gateway error: {str(e)}'},
                        status=status.HTTP_400_BAD_REQUEST
                    )

            # Update order payment status
            order.update_payment_status()

            # Create payment history
            history_service = PaymentHistoryService(payment)
            history_service.create_history_record(
                history_type=PaymentHistory.HistoryType.PAYMENT,
                details={
                    'amount': float(amount),
                    'method': payment_method,
                    'status': payment.status,
                    'reference': reference
                }
            )

            return Response({
                'message': 'Payment processed successfully',
                'payment': PaymentSerializer(payment).data,
                'order': OrderSerializer(order).data
            })
            
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {'error': f'Payment processing failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class OrderItemViewSet(viewsets.ModelViewSet):
    """ViewSet for managing order items."""
    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        'order',
        'item_type',
        'status',
        'kitchen_status'
    ]
    ordering_fields = ['created_at', 'status']

    def perform_create(self, serializer):
        item = serializer.save(created_by=self.request.user)
        # If allergens are provided, update related customer's allergens
        if item.assigned_customer and item.allergens.exists():
            for allergen in item.allergens.all():
                item.assigned_customer.allergens.add(allergen)
            item.assigned_customer.save()

    def perform_update(self, serializer):
        item = serializer.save()
        item._update_totals()
        if item.order:
            item.order.calculate_totals()
            item.order.save()
        # If allergens are updated, update related customer's allergens
        if item.assigned_customer and item.allergens.exists():
            for allergen in item.allergens.all():
                item.assigned_customer.allergens.add(allergen)
            item.assigned_customer.save()

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update item status."""
        item = self.get_object()
        status = request.data.get('status')
        
        if not status or status not in dict(OrderItem.Status.choices):
            return Response(
                {'error': 'Invalid status'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        item.status = status
        item.save()
        
        # Update kitchen status if item is ready
        if status == OrderItem.Status.READY:
            item.kitchen_status = OrderItem.Status.READY
            item.save()
            
        return Response({'message': 'Status updated successfully'})
    
    @action(detail=True, methods=['post'])
    def consume_ingredients(self, request, pk=None):
        """Manually consume ingredients for this item."""
        item = self.get_object()
        
        if item.inventory_updated:
            return Response(
                {'error': 'Ingredients already consumed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        item.consume_ingredients()
        
        return Response({
            'message': 'Ingredients consumed successfully',
            'consumed_ingredients': item.ingredients_consumed
        })

    @action(detail=True, methods=['get', 'post'])
    def modifiers(self, request, pk=None):
        """List all modifiers for this order item or create a new one."""
        order_item = self.get_object()
        
        if request.method == 'GET':
            # List all modifiers for this order item
            modifiers = order_item.modifiers.all()
            serializer = OrderItemModifierSerializer(modifiers, many=True)
            return Response(serializer.data)
            
        elif request.method == 'POST':
            # Create a new modifier for this order item
            serializer = OrderItemModifierSerializer(data=request.data)
            if serializer.is_valid():
                with transaction.atomic():
                    modifier = serializer.save(order_item=order_item)
                    # Update order totals
                    order_item._update_totals()
                    order_item.save()
                    order_item.order.calculate_totals()
                    order_item.order.save()
                return Response(serializer.data, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
