"""
Tests for OTP and authentication views.
"""
import logging
from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APIClient

from ..models import User, OTP

logger = logging.getLogger(__name__)


@override_settings(
    CELERY_TASK_ALWAYS_EAGER=True,
    CELERY_TASK_EAGER_PROPAGATES=True,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class OTPViewsTestCase(TestCase):
    """Test cases for OTP and authentication views."""
    
    def setUp(self):
        """Set up test data."""
        self.client = APIClient()
        
        # Create test user
        self.user_data = {
            'email': 'test@example.com',
            'phone_number': '+1234567890',
            'first_name': 'Test',
            'last_name': 'User',
            'password': 'testpass123',
            'is_verified': False,
            'is_active': True
        }
        self.user = User.objects.create_user(**self.user_data)
        
        # URLs
        self.request_otp_url = reverse('request_otp')
        self.verify_otp_url = reverse('verify_otp')
        self.password_reset_url = reverse('password_reset')
    
    def test_request_otp_email_verification(self):
        """Test requesting OTP for email verification."""
        data = {
            'email': self.user.email,
            'otp_type': OTP.EMAIL_VERIFICATION
        }
        
        response = self.client.post(self.request_otp_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'Verification code sent successfully.')
        
        # Verify OTP was created
        otp = OTP.objects.filter(user=self.user, otp_type=OTP.EMAIL_VERIFICATION).first()
        self.assertIsNotNone(otp)
        self.assertFalse(otp.is_used)
        self.assertGreater(otp.expires_at, timezone.now())
    
    def test_verify_otp_email_verification(self):
        """Test verifying OTP for email verification."""
        # Create an OTP
        otp = OTP.objects.create(
            user=self.user,
            otp_type=OTP.EMAIL_VERIFICATION,
            code='123456',
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        
        data = {
            'email': self.user.email,
            'otp_code': '123456',
            'otp_type': OTP.EMAIL_VERIFICATION
        }
        
        response = self.client.post(self.verify_otp_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'Verification successful.')
        self.assertTrue(response.data['verified'])
        
        # Verify user is now verified
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
        
        # Verify OTP is marked as used
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)
    
    def test_request_password_reset(self):
        """Test requesting password reset OTP."""
        data = {
            'email': self.user.email,
            'otp_type': OTP.PASSWORD_RESET
        }
        
        response = self.client.post(self.request_otp_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify OTP was created
        otp = OTP.objects.filter(user=self.user, otp_type=OTP.PASSWORD_RESET).first()
        self.assertIsNotNone(otp)
        self.assertFalse(otp.is_used)
    
    def test_reset_password_with_otp(self):
        """Test resetting password with OTP."""
        # Create a password reset OTP
        otp = OTP.objects.create(
            user=self.user,
            otp_type=OTP.PASSWORD_RESET,
            code='123456',
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        
        # First request with just email to get OTP (already tested)
        
        # Now reset password with OTP and new password
        data = {
            'email': self.user.email,
            'otp_code': '123456',
            'new_password': 'newsecurepass123',
            'confirm_password': 'newsecurepass123'
        }
        
        response = self.client.post(self.password_reset_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['detail'], 'Password has been reset successfully.')
        
        # Verify password was changed
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('newsecurepass123'))
        
        # Verify OTP is marked as used
        otp.refresh_from_db()
        self.assertTrue(otp.is_used)
    
    def test_invalid_otp_verification(self):
        """Test verifying with invalid OTP."""
        # Create an OTP
        OTP.objects.create(
            user=self.user,
            otp_type=OTP.EMAIL_VERIFICATION,
            code='123456',
            expires_at=timezone.now() + timedelta(minutes=15)
        )
        
        # Try with wrong code
        data = {
            'email': self.user.email,
            'otp_code': '999999',  # Wrong code
            'otp_type': OTP.EMAIL_VERIFICATION
        }
        
        response = self.client.post(self.verify_otp_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
    
    def test_expired_otp_verification(self):
        """Test verifying with expired OTP."""
        # Create an expired OTP
        otp = OTP.objects.create(
            user=self.user,
            otp_type=OTP.EMAIL_VERIFICATION,
            code='123456',
            expires_at=timezone.now() - timedelta(minutes=1)  # Expired
        )
        
        data = {
            'email': self.user.email,
            'otp_code': '123456',
            'otp_type': OTP.EMAIL_VERIFICATION
        }
        
        response = self.client.post(self.verify_otp_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('detail', response.data)
        self.assertIn('expired', response.data['detail'].lower())
    
    def test_max_attempts_exceeded(self):
        """Test that OTP becomes invalid after max attempts."""
        # Create an OTP with 1 attempt remaining
        otp = OTP.objects.create(
            user=self.user,
            otp_type=OTP.EMAIL_VERIFICATION,
            code='123456',
            expires_at=timezone.now() + timedelta(minutes=15),
            max_attempts=3,
            attempts_remaining=1
        )
        
        # First attempt with wrong code
        data = {
            'email': self.user.email,
            'otp_code': '999999',  # Wrong code
            'otp_type': OTP.EMAIL_VERIFICATION
        }
        
        response = self.client.post(self.verify_otp_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Verify OTP is now invalid (no attempts left)
        otp.refresh_from_db()
        self.assertEqual(otp.attempts_remaining, 0)
        self.assertFalse(otp.is_valid)
