import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import Order, OrderItem, Payment
from .serializers import OrderSerializer, OrderItemSerializer, PaymentSerializer


class OrderConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time order updates."""
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.order_group_name = 'orders'
        
        # Join order group
        await self.channel_layer.group_add(
            self.order_group_name,
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave order group
        await self.channel_layer.group_discard(
            self.order_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle WebSocket message from client."""
        try:
            text_data_json = json.loads(text_data)
            message_type = text_data_json.get('type')
            
            if message_type == 'subscribe':
                # Subscribe to specific order updates
                order_id = text_data_json.get('order_id')
                if order_id:
                    await self.channel_layer.group_add(
                        f'order_{order_id}',
                        self.channel_name
                    )
        except json.JSONDecodeError:
            pass
    
    # Receive message from order group
    async def order_update(self, event):
        """Send order update to WebSocket."""
        await self.send(text_data=json.dumps(event))
    
    # Receive message from order item group
    async def order_item_update(self, event):
        """Send order item update to WebSocket."""
        await self.send(text_data=json.dumps(event))
    
    async def payment_update(self, event):
        """Send payment update to WebSocket."""
        await self.send(text_data=json.dumps(event))
    
    @staticmethod
    @database_sync_to_async
    def get_order_data(order_id):
        """Get order data for WebSocket."""
        try:
            order = Order.objects.get(id=order_id)
            return OrderSerializer(order).data
        except Order.DoesNotExist:
            return None
    
    @staticmethod
    @database_sync_to_async
    def get_order_item_data(item_id):
        """Get order item data for WebSocket."""
        try:
            item = OrderItem.objects.get(id=item_id)
            return OrderItemSerializer(item).data
        except OrderItem.DoesNotExist:
            return None
    
    @staticmethod
    @database_sync_to_async
    def get_payment_data(payment_id):
        """Get payment data for WebSocket."""
        try:
            payment = Payment.objects.get(id=payment_id)
            return PaymentSerializer(payment).data
        except Payment.DoesNotExist:
            return None
