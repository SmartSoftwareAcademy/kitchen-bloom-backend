from typing import Dict, Optional
from . import PaymentGateway
from .mpesa import MpesaGateway
from .card import CardGateway
from django.conf import settings

class PaymentGatewayFactory:
    """Factory for creating payment gateway instances."""
    
    @staticmethod
    def get_gateway(payment_method: str) -> Optional[PaymentGateway]:
        """Get appropriate payment gateway for the given method."""
        if payment_method in ['mpesa', 'mpesa-stk', 'mpesa-manual']:
            return MpesaGateway()
        elif payment_method == 'card':
            return CardGateway()
        elif payment_method == 'cash':
            # Cash payments don't need a gateway
            return None
        return None
    
    @staticmethod
    def get_available_gateways() -> Dict[str, str]:
        """Get dictionary of available payment methods and their display names."""
        gateways = {
            'cash': 'Cash Payment',
            'card': 'Credit/Debit Card'
        }
        
        # Only include M-Pesa if settings are configured
        if all([
            hasattr(settings, 'MPESA_API_BASE_URL'),
            hasattr(settings, 'MPESA_CONSUMER_KEY'),
            hasattr(settings, 'MPESA_CONSUMER_SECRET'),
            hasattr(settings, 'MPESA_SHORTCODE'),
            hasattr(settings, 'MPESA_PASSKEY')
        ]):
            gateways['mpesa'] = 'M-Pesa'
            gateways['mpesa-stk'] = 'M-Pesa STK Push'
            gateways['mpesa-manual'] = 'M-Pesa Manual'
        
        return gateways
