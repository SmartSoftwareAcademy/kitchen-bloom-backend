from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging
from .models import Order, OrderItem, Payment
from django.conf import settings
from django.db import models

# Set up logger
logger = logging.getLogger(__name__)


def send_order_update(order, action):
    """Send order update to WebSocket consumers if enabled."""
    if not getattr(settings, 'KDS_WEBSOCKETS_ENABLED', False):
        return
    from .serializers import OrderSerializer
    try:
        channel_layer = get_channel_layer()
        order_data = OrderSerializer(order).data
        
        # Send to order group
        async_to_sync(channel_layer.group_send)(
            'orders',
            {
                'type': 'order_update',
                'action': action,
                'order': order_data
            }
        )
        
        # Send to specific order group
        async_to_sync(channel_layer.group_send)(
            f'order_{order.id}',
            {
                'type': 'order_update',
                'action': action,
                'order': order_data
            }
        )
        logger.debug(f"WebSocket order update sent: {action} for order {order.id}")
    except Exception as e:
        logger.error(f"WebSocket error in send_order_update: {e}")
        pass  # Ignore all errors if channel layer/redis is not running

def send_order_item_update(order_item, action):
    """Send order item update to WebSocket consumers if enabled."""
    if not getattr(settings, 'KDS_WEBSOCKETS_ENABLED', False):
        return
    from .serializers import OrderItemSerializer
    try:
        channel_layer = get_channel_layer()
        item_data = OrderItemSerializer(order_item).data
        
        # Send to order group
        async_to_sync(channel_layer.group_send)(
            'orders',
            {
                'type': 'order_item_update',
                'action': action,
                'order_item': item_data
            }
        )
        
        # Send to specific order group
        async_to_sync(channel_layer.group_send)(
            f'order_{order_item.order.id}',
            {
                'type': 'order_item_update',
                'action': action,
                'order_item': item_data
            }
        )
        logger.debug(f"WebSocket order item update sent: {action} for item {order_item.id}")
    except Exception as e:
        logger.error(f"WebSocket error in send_order_item_update: {e}")
        pass  # Ignore all errors if channel layer/redis is not running

def send_payment_update(payment, action):
    """Send payment update to WebSocket consumers if enabled."""
    if not getattr(settings, 'KDS_WEBSOCKETS_ENABLED', False):
        return
    from .serializers import PaymentSerializer
    
    channel_layer = get_channel_layer()
    payment_data = PaymentSerializer(payment).data
    
    # Send to order group (since payment affects order status)
    async_to_sync(channel_layer.group_send)(
        'orders',
        {
            'type': 'payment_update',
            'action': action,
            'payment': payment_data
        }
    )
    
    # Send to specific order group
    async_to_sync(channel_layer.group_send)(
        f'order_{payment.order.id}',
        {
            'type': 'payment_update',
            'action': action,
            'payment': payment_data
        }
    )
    
    # Send to specific payment group
    async_to_sync(channel_layer.group_send)(
        f'payment_{payment.id}',
        {
            'type': 'payment_update',
            'action': action,
            'payment': payment_data
        }
    )
    logger.debug(f"WebSocket payment update sent: {action} for payment {payment.id}")

@receiver(post_save, sender=Order)
def order_post_save(sender, instance, created, **kwargs):
    """Send WebSocket update when an order is created or updated."""
    if getattr(instance, '_skip_ws', False):
        return
    action = 'created' if created else 'updated'
    logger.info(f"Order {action}: {instance.order_number} (ID: {instance.id}) - Status: {instance.status}")
    send_order_update(instance, action)

@receiver(post_save, sender=OrderItem)
def order_item_post_save(sender, instance, created, **kwargs):
    """Send WebSocket update when an order item is created or updated."""
    if getattr(instance, '_skip_ws', False):
        return
    action = 'created' if created else 'updated'
    logger.info(f"Order item {action}: {instance.get_item_name()} (ID: {instance.id}) - Status: {instance.status}")
    send_order_item_update(instance, action)
    # Also send order update since order totals might have changed
    send_order_update(instance.order, 'updated')

@receiver(post_delete, sender=OrderItem)
def order_item_post_delete(sender, instance, **kwargs):
    """Send WebSocket update when an order item is deleted."""
    order = instance.order
    logger.info(f"Order item deleted: {instance.get_item_name()} (ID: {instance.id})")
    send_order_item_update(instance, 'deleted')
    # Also send order update since order totals might have changed
    send_order_update(order, 'updated')

@receiver(post_save, sender=Payment)
def payment_post_save(sender, instance, created, **kwargs):
    """Send WebSocket update when a payment is created or updated."""
    action = 'created' if created else 'updated'
    logger.info(f"Payment {action}: {instance.id} - Amount: {instance.amount} - Status: {instance.status}")
    send_payment_update(instance, action)

@receiver(post_delete, sender=Payment)
def payment_post_delete(sender, instance, **kwargs):
    """Send WebSocket update when a payment is deleted."""
    logger.info(f"Payment deleted: {instance.id} - Amount: {instance.amount}")
    send_payment_update(instance, 'deleted')

@receiver(post_save, sender=Payment)
def handle_payment_added(sender, instance, created, **kwargs):
    """Handle order status updates when a payment is added."""
    logger.debug(f"handle_payment_added signal triggered: payment_id={instance.id}, created={created}, status={instance.status}")
    
    if created and instance.status == 'completed':
        logger.info(f"Processing new completed payment: {instance.id} for order {instance.order.order_number}")
        
        order = instance.order
        
        # Calculate total payments for this order
        total_payments = order.payments.filter(status='completed').aggregate(
            total=models.Sum('amount')
        )['total'] or 0
        
        logger.info(f"Total payments for order {order.order_number}: {total_payments} (Order total: {order.total_amount})")
        
        # Update order payment status
        if total_payments >= order.total_amount:
            old_status = order.status
            old_payment_status = order.payment_status
            
            order.payment_status = 'paid'
            order.status = 'completed'
            
            logger.info(f"Order {order.order_number} status updated: {old_status} -> {order.status}, Payment: {old_payment_status} -> {order.payment_status}")
        elif total_payments > 0:
            old_payment_status = order.payment_status
            order.payment_status = 'partially_paid'
            logger.info(f"Order {order.order_number} payment status updated: {old_payment_status} -> {order.payment_status}")
        
        order.save()
        
        # If order is completed, update order items to served status
        if order.status == 'completed':
            logger.info(f"Order {order.order_number} completed, updating order items to served status")
            for item in order.items.all():
                logger.debug(f"Processing order item: {item.get_item_name()} (ID: {item.id}) - Current status: {item.status}")
                if item.status not in ['cancelled', 'served']:
                    old_item_status = item.status
                    item.status = 'served'
                    item.save()
                    logger.info(f"Order item {item.id} status updated: {old_item_status} -> {item.status}")
                else:
                    logger.debug(f"Order item {item.id} already in final status: {item.status}")
    else:
        logger.debug(f"handle_payment_added signal conditions not met: created={created}, status={instance.status}")

@receiver(post_save, sender=Payment)
def handle_payment_completion(sender, instance, created, **kwargs):
    """Handle order and order item status updates when payment is completed."""
    if instance.status == 'completed' and not created:
        logger.info(f"Payment status changed to completed: {instance.id}")
        
        # Get the previous status
        try:
            old_instance = Payment.objects.get(pk=instance.pk)
            if old_instance.status != 'completed':
                logger.info(f"Payment status changed from {old_instance.status} to completed")
                
                order = instance.order
                
                # Update order status to completed if payment covers the full amount
                if instance.amount >= order.total_amount and order.status != 'completed':
                    old_status = order.status
                    order.status = 'completed'
                    order.payment_status = 'paid'
                    order.save()
                    logger.info(f"Order {order.order_number} status updated: {old_status} -> {order.status}, Payment: {old_instance.payment_status} -> {order.payment_status}")
                
                # Update order items to served status to trigger inventory consumption
                logger.info(f"Updating order items to served status for order {order.order_number}")
                for item in order.items.all():
                    if item.status not in ['cancelled', 'served']:
                        old_item_status = item.status
                        item.status = 'served'
                        item.save()
                        logger.info(f"Order item {item.id} status updated: {old_item_status} -> {item.status}")
        except Payment.DoesNotExist:
            logger.warning(f"Payment {instance.id} not found when processing completion")

@receiver(post_save, sender=Order)
def create_inventory_transactions_for_order(sender, instance, created, **kwargs):
    """Create inventory transactions when orders are completed."""
    if instance.status == 'completed' and not created:
        logger.info(f"Processing completed order for inventory: {instance.order_number}")
        
        # Get the previous status
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            if old_instance.status != 'completed':
                logger.info(f"Order status changed from {old_instance.status} to completed")
                
                # Create inventory transactions for all items
                for item in instance.items.all():
                    logger.info(f"Processing order item: {item.get_item_name()} (ID: {item.id}) - Status: {item.status}, Inventory Updated: {item.inventory_updated}")
                    
                    if not item.inventory_updated:
                        logger.info(f"Consuming ingredients for order item: {item.get_item_name()} (ID: {item.id})")
                        try:
                            item.consume_ingredients()
                            logger.info(f"Successfully consumed ingredients for order item: {item.id}")
                        except Exception as e:
                            logger.error(f"Error consuming ingredients for order item {item.id}: {e}")
                    else:
                        logger.debug(f"Order item {item.id} already has inventory updated")
            else:
                logger.debug(f"Order {instance.order_number} status was already completed")
        except Order.DoesNotExist:
            logger.warning(f"Order {instance.id} not found when processing completion")
        except Exception as e:
            logger.error(f"Error processing completed order {instance.order_number}: {e}")

@receiver(post_save, sender=OrderItem)
def create_inventory_transaction_for_order_item(sender, instance, created, **kwargs):
    """Create inventory transactions when order items are served."""
    logger.debug(f"create_inventory_transaction_for_order_item signal triggered: item_id={instance.id}, status={instance.status}, created={created}")
    
    if instance.status == 'served' and not created:
        logger.info(f"Processing served order item for inventory: {instance.get_item_name()} (ID: {instance.id})")
        
        # Get the previous status
        try:
            old_instance = OrderItem.objects.get(pk=instance.pk)
            logger.debug(f"Previous status: {old_instance.status}, Current status: {instance.status}, Inventory updated: {instance.inventory_updated}")
            
            if old_instance.status != 'served' and not instance.inventory_updated:
                logger.info(f"Order item status changed from {old_instance.status} to served")
                logger.info(f"Consuming ingredients for order item: {instance.get_item_name()} (ID: {instance.id})")
                
                # Log item details
                logger.debug(f"Item type: {instance.item_type}")
                if instance.item_type == 'menu_item' and instance.menu_item:
                    logger.debug(f"Menu item: {instance.menu_item.name}")
                    if hasattr(instance.menu_item, 'recipe'):
                        logger.debug(f"Recipe exists: {instance.menu_item.recipe is not None}")
                        if instance.menu_item.recipe:
                            logger.debug(f"Recipe ingredients count: {instance.menu_item.recipe.ingredients.count()}")
                elif instance.item_type == 'product' and instance.product:
                    logger.debug(f"Product: {instance.product.name}")
                
                try:
                    instance.consume_ingredients()
                    logger.info(f"Successfully consumed ingredients for order item: {instance.id}")
                except Exception as e:
                    logger.error(f"Error consuming ingredients for order item {instance.id}: {e}")
                    import traceback
                    logger.error(f"Traceback: {traceback.format_exc()}")
            else:
                logger.debug(f"Order item {instance.id} already has inventory updated or status not changed")
        except OrderItem.DoesNotExist:
            logger.warning(f"Order item {instance.id} not found when processing served status")
        except Exception as e:
            logger.error(f"Error processing served order item {instance.id}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
    else:
        logger.debug(f"Signal conditions not met: status={instance.status}, created={created}")

@receiver(post_save, sender=Order)
def handle_order_refund(sender, instance, created, **kwargs):
    """Handle inventory returns when orders are refunded."""
    if instance.payment_status in ['refunded', 'partial_refund'] and not created:
        logger.info(f"Processing refund for order: {instance.order_number}")
        
        # Get the previous payment status
        try:
            old_instance = Order.objects.get(pk=instance.pk)
            if old_instance.payment_status not in ['refunded', 'partial_refund']:
                logger.info(f"Order payment status changed from {old_instance.payment_status} to {instance.payment_status}")
                
                # Create inventory return transactions
                logger.info(f"Creating return transactions for order {instance.order_number}")
                instance._create_return_transactions()
                logger.info(f"Successfully created return transactions for order {instance.order_number}")
        except Order.DoesNotExist:
            logger.warning(f"Order {instance.id} not found when processing refund")
