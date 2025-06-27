from abc import ABC, abstractmethod
from typing import Dict, Optional
from django.conf import settings

class PaymentGateway(ABC):
    """Base interface for payment gateways."""
    
    @abstractmethod
    def initialize_payment(self, amount: float, reference: str, metadata: Dict) -> Dict:
        """Initialize a payment request."""
        pass
        
    @abstractmethod
    def verify_payment(self, reference: str) -> Dict:
        """Verify payment status."""
        pass
        
    @abstractmethod
    def refund_payment(self, reference: str, amount: Optional[float] = None) -> Dict:
        """Process a refund."""
        pass
        
    @abstractmethod
    def get_payment_status(self, reference: str) -> str:
        """Get payment status."""
        pass
