from typing import Dict, Optional, Any
from datetime import datetime
import hashlib
import base64
import requests
from django.conf import settings
from . import PaymentGateway


class MpesaGateway(PaymentGateway):
    """M-Pesa payment gateway implementation."""
    
    def __init__(self):
        self.base_url = settings.MPESA_API_BASE_URL
        self.consumer_key = settings.MPESA_CONSUMER_KEY
        self.consumer_secret = settings.MPESA_CONSUMER_SECRET
        self.shortcode = settings.MPESA_SHORTCODE
        self.passkey = settings.MPESA_PASSKEY
        
    def _generate_password(self, timestamp: str) -> str:
        """Generate M-Pesa password for authentication."""
        password = f"{self.shortcode}{self.passkey}{timestamp}"
        return base64.b64encode(password.encode()).decode()
    
    def _get_timestamp(self) -> str:
        """Get current timestamp in M-Pesa format."""
        return datetime.now().strftime("%Y%m%d%H%M%S")
    
    def _generate_access_token(self) -> str:
        """Generate access token for M-Pesa API."""
        auth_url = f"{self.base_url}/oauth/v1/generate?grant_type=client_credentials"
        response = requests.get(
            auth_url,
            auth=(self.consumer_key, self.consumer_secret)
        )
        response.raise_for_status()
        return response.json()['access_token']
    
    def initialize_payment(self, amount: float, reference: str, metadata: Dict) -> Dict:
        """Initialize M-Pesa payment request."""
        timestamp = self._get_timestamp()
        password = self._generate_password(timestamp)
        
        access_token = self._generate_access_token()
        
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": metadata.get('phone_number'),
            "PartyB": self.shortcode,
            "PhoneNumber": metadata.get('phone_number'),
            "CallBackURL": settings.MPESA_CALLBACK_URL,
            "AccountReference": reference,
            "TransactionDesc": metadata.get('description', 'Payment')
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/mpesa/stkpush/v1/processrequest",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return {
                'success': True,
                'data': response.json(),
                'reference': response.json().get('MerchantRequestID')
            }
        except requests.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def verify_payment(self, reference: str) -> Dict:
        """Verify M-Pesa payment status."""
        access_token = self._generate_access_token()
        
        payload = {
            "BusinessShortCode": self.shortcode,
            "Password": self._generate_password(self._get_timestamp()),
            "Timestamp": self._get_timestamp(),
            "MerchantRequestID": reference
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/mpesa/stkpushquery/v1/query",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            
            result = response.json()
            return {
                'success': True,
                'data': result,
                'status': result.get('ResultCode') == 0
            }
        except requests.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def refund_payment(self, reference: str, amount: Optional[float] = None) -> Dict:
        """Process M-Pesa refund."""
        access_token = self._generate_access_token()
        
        payload = {
            "Initiator": settings.MPESA_INITIATOR_NAME,
            "SecurityCredential": settings.MPESA_SECURITY_CREDENTIAL,
            "CommandID": "TransactionReversal",
            "TransactionID": reference,
            "Amount": amount,
            "ReceiverParty": self.shortcode,
            "ReceiverIdentifierType": "4",
            "ResultURL": settings.MPESA_CALLBACK_URL,
            "QueueTimeOutURL": settings.MPESA_CALLBACK_URL,
            "Remarks": "Refund",
            "Occasion": ""
        }
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                f"{self.base_url}/mpesa/reversal/v1/request",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            return {
                'success': True,
                'data': response.json()
            }
        except requests.RequestException as e:
            return {
                'success': False,
                'error': str(e),
                'data': None
            }
    
    def get_payment_status(self, reference: str) -> str:
        """Get payment status from M-Pesa."""
        result = self.verify_payment(reference)
        if result['success']:
            if result['data'].get('ResultCode') == 0:
                return "completed"
            elif result['data'].get('ResultCode') == 1032:
                return "pending"
            else:
                return "failed"
        return "unknown"
