from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from apps.sales.models import Payment
from apps.sales.gateways.factory import PaymentGatewayFactory

class PaymentVerificationService:
    """Service for verifying payment status."""
    
    def __init__(self, payment: Payment):
        self.payment = payment
        
    def verify(self) -> bool:
        """Verify payment status with payment gateway."""
        gateway = PaymentGatewayFactory.get_gateway(self.payment.method)
        
        if gateway is None:
            # Cash payments or unsupported methods
            return True
            
        try:
            result = gateway.verify_payment(self.payment.transaction_reference)
            
            # Update payment status based on verification result
            if result.get('status', False):
                self.payment.status = Payment.Status.COMPLETED
            else:
                self.payment.status = Payment.Status.FAILED
            self.payment.save()
            
            return result.get('status', False)
            
        except Exception as e:
            self.payment.status = Payment.Status.FAILED
            self.payment.save()
            raise ValidationError(_(f"Payment verification failed: {str(e)}"))
