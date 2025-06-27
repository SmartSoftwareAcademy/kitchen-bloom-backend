from typing import Dict, Optional, Any
import stripe
from django.conf import settings
from . import PaymentGateway


class CardGateway(PaymentGateway):
    """Stripe card payment gateway implementation."""
    
    def __init__(self):
        stripe.api_key = settings.STRIPE_SECRET_KEY
        self.webhook_secret = settings.STRIPE_WEBHOOK_SECRET
        
    def _create_payment_intent(self, amount: float, currency: str) -> Dict:
        """Create Stripe PaymentIntent."""
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(amount * 100),  # Convert to cents
                currency=currency.lower(),
                payment_method_types=['card'],
                metadata={'integration_check': 'accept_a_payment'}
            )
            return {
                'success': True,
                'client_secret': intent.client_secret,
                'id': intent.id
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def initialize_payment(self, amount: float, reference: str, metadata: Dict) -> Dict:
        """Initialize card payment."""
        currency = metadata.get('currency', 'USD')
        result = self._create_payment_intent(amount, currency)
        
        if result['success']:
            return {
                'success': True,
                'data': result,
                'reference': result['id']
            }
        return result
    
    def verify_payment(self, reference: str) -> Dict:
        """Verify card payment status."""
        try:
            intent = stripe.PaymentIntent.retrieve(reference)
            return {
                'success': True,
                'data': intent,
                'status': intent.status == 'succeeded'
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def refund_payment(self, reference: str, amount: Optional[float] = None) -> Dict:
        """Process card refund."""
        try:
            refund = stripe.Refund.create(
                payment_intent=reference,
                amount=int(amount * 100) if amount else None  # Convert to cents
            )
            return {
                'success': True,
                'data': refund
            }
        except stripe.error.StripeError as e:
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def get_payment_status(self, reference: str) -> str:
        """Get payment status from Stripe."""
        result = self.verify_payment(reference)
        if result['success']:
            status = result['data'].status
            if status == 'succeeded':
                return "completed"
            elif status in ['requires_payment_method', 'requires_confirmation']:
                return "pending"
            else:
                return "failed"
        return "unknown"
    
    def handle_webhook(self, payload: Dict, signature: str) -> Dict:
        """Handle Stripe webhook events."""
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            
            if event.type == 'payment_intent.succeeded':
                intent = event.data.object
                return {
                    'type': 'payment_intent.succeeded',
                    'data': intent,
                    'reference': intent.id
                }
            elif event.type == 'payment_intent.payment_failed':
                intent = event.data.object
                return {
                    'type': 'payment_intent.payment_failed',
                    'data': intent,
                    'reference': intent.id
                }
            
            return {'type': 'unknown'}
            
        except stripe.error.SignatureVerificationError:
            return {'error': 'Invalid signature'}
        except Exception as e:
            return {'error': str(e)}
