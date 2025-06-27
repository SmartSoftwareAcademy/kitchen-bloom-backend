from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.db import models
from apps.sales.models import Payment, PaymentHistory


class PaymentHistoryService:
    """Service for managing payment history."""
    
    def __init__(self, payment: Payment):
        self.payment = payment
        
    def create_history_record(self, history_type: str, details: dict):
        """Create a payment history record."""
        return PaymentHistory.objects.create(
            payment=self.payment,
            history_type=history_type,
            details=details
        )
    
    def get_payment_history(self):
        """Get complete payment history."""
        return PaymentHistory.objects.filter(
            payment=self.payment
        ).order_by('-created_at')
    
    def get_latest_status_change(self):
        """Get the latest status change record."""
        return self.get_payment_history().filter(
            history_type=PaymentHistory.HistoryType.STATUS_CHANGE
        ).first()
