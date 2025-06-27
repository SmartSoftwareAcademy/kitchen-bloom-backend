from ipaddress import ip_address, ip_network
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Union, Any
import logging
import random
import string

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail as django_send_mail
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.http import HttpRequest

from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.exceptions import InvalidToken

# Import OTP model here to avoid circular imports
from apps.accounts.models import OTP

from .models import EmailConfig, SMSSettings
from .modules.custom_email_backend import CustomEmailBackend

User = get_user_model()

logger = logging.getLogger(__name__)


def get_client_ip(request: HttpRequest) -> Optional[str]:
    """
    Get the client's IP address from the request.
    Handles proxies and various HTTP headers.
    
    Args:
        request: The HTTP request object
        
    Returns:
        str: The client's IP address or None if not found
    """
    # List of possible IP headers (in order of preference)
    ip_headers = [
        'HTTP_X_FORWARDED_FOR',
        'HTTP_X_REAL_IP',
        'REMOTE_ADDR',
    ]
    
    for header in ip_headers:
        if header in request.META:
            # HTTP_X_FORWARDED_FOR can contain multiple IPs, take the first one
            ip = request.META[header].split(',')[0].strip()
            if ip:
                return ip
    
    return None


def is_private_ip(ip: str) -> bool:
    """
    Check if an IP address is in a private range.
    
    Args:
        ip: The IP address to check
        
    Returns:
        bool: True if the IP is private, False otherwise
    """
    try:
        ip_addr = ip_address(ip)
        
        # Private IP ranges:
        # 10.0.0.0/8
        # 172.16.0.0/12
        # 192.168.0.0/16
        # 127.0.0.0/8 (localhost)
        # ::1 (IPv6 localhost)
        private_ranges = [
            ip_network('10.0.0.0/8'),
            ip_network('172.16.0.0/12'),
            ip_network('192.168.0.0/16'),
            ip_network('127.0.0.0/8'),
            ip_network('::1/128'),
        ]
        
        return any(ip_addr in private_net for private_net in private_ranges)
    except ValueError:
        return False


def get_absolute_uri(request: HttpRequest, path: str = '') -> str:
    """
    Get the absolute URI for a given path.
    
    Args:
        request: The HTTP request object
        path: The path to make absolute (default: '' for site root)
        
    Returns:
        str: The absolute URI
    """
    if path.startswith(('http://', 'https://', '//')):
        return path
    
    # Get the site domain from settings or request
    site_domain = getattr(settings, 'SITE_DOMAIN', None)
    if not site_domain and hasattr(request, 'get_host'):
        site_domain = request.get_host()
    
    # Ensure the domain has a scheme
    if site_domain and not site_domain.startswith(('http://', 'https://')):
        secure = getattr(settings, 'SECURE_SSL_REDIRECT', False)
        scheme = 'https' if secure or request.is_secure() else 'http'
        site_domain = f"{scheme}://{site_domain}"
    
    # Ensure the path starts with a single slash
    if path and not path.startswith('/'):
        path = f'/{path}'
    
    return f"{site_domain}{path}"


def format_currency(amount, currency=None):
    """
    Format a number as a currency string.
    
    Args:
        amount: The amount to format
        currency: The currency code (e.g., 'USD', 'KES'). Defaults to settings.DEFAULT_CURRENCY
        
    Returns:
        str: Formatted currency string
    """
    if currency is None:
        currency = getattr(settings, 'DEFAULT_CURRENCY', 'KES')
    
    if currency.upper() == 'KES':
        return f"KSh {amount:,.2f}"
    elif currency.upper() == 'USD':
        return f"$ {amount:,.2f}"
    else:
        return f"{currency} {amount:,.2f}"


def generate_random_string(length=32, allowed_chars=None):
    """
    Generate a cryptographically secure random string.
    
    Args:
        length: Length of the string to generate
        allowed_chars: String of allowed characters. If None, uses alphanumeric chars.
        
    Returns:
        str: Random string of the specified length
    """
    import secrets
    
    if allowed_chars is None:
        allowed_chars = string.ascii_letters + string.digits
    
    return ''.join(secrets.choice(allowed_chars) for _ in range(length))


def send_email(request, subject, message, recipient_list, attachments=None):
    """
    Send an email using Django's email backend.
    
    Args:
        subject: Email subject
        message: Plain text message
        recipient_list: List of recipient email addresses
        attachments: Attachment files (optional)
        
    Returns:
        int: Number of successfully sent emails (1 for success, 0 for failure)
    """
    ## load email config from db
    email_config = EmailConfig.objects.first()
    if not email_config:    
        return 0
    
    # send email
    try:
        CustomEmailBackend(request=request,subject=subject,body=message,to=recipient_list, attachments=attachments).send_email()        
        return True
    except Exception as e:
        # Log the error and re-raise or handle as needed
        logger.error(f"Failed to send email: {str(e)}")
        raise


def get_tokens_for_user(user: User) -> Dict[str, str]:
    """
    Generate access and refresh tokens for the given user.
    
    Args:
        user: The user instance to generate tokens for
        
    Returns:
        dict: Dictionary containing 'access' and 'refresh' tokens
    """
    refresh = RefreshToken.for_user(user)
    
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'user_id': str(user.id),
        'email': user.email,
        'role': user.role.name if user.role else None,
    }


def verify_token(token: str) -> Tuple[bool, Union[User, None], str]:
    """
    Verify a JWT token and return the associated user if valid.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        tuple: (is_valid, user, message)
    """
    from rest_framework_simplejwt.tokens import AccessToken
    
    try:
        # Decode the token
        access_token = AccessToken(token)
        
        # Get the user ID from the token
        user_id = access_token['user_id']
        
        # Get the user
        try:
            user = User.objects.get(id=user_id, is_active=True)
            return True, user, "Token is valid"
        except User.DoesNotExist:
            return False, None, "User not found or inactive"
            
    except TokenError as e:
        return False, None, f"Invalid token: {str(e)}"
    except Exception as e:
        return False, None, f"Token verification failed: {str(e)}"


def refresh_token(refresh_token_str: str) -> Tuple[bool, Dict[str, str], str]:
    """
    Refresh an access token using a refresh token.
    
    Args:
        refresh_token_str: The refresh token string
        
    Returns:
        Tuple[bool, Dict[str, str], str]: (success, tokens, message)
    """
    try:
        refresh = RefreshToken(refresh_token_str)
        tokens = {
            'access': str(refresh.access_token),
            'refresh': str(refresh)
        }
        return True, tokens, ""
    except Exception as e:
        logger.error("Error refreshing token: %s", str(e))
        return False, {}, f"Token refresh failed: {str(e)}"


def generate_otp_code(length=6):
    """
    Generate a secure random OTP code.
    
    Args:
        length: Length of the OTP code (default: 6)
        
    Returns:
        str: Generated OTP code
    """
    import random
    import string
    
    # Use a secure random source
    return ''.join(random.SystemRandom().choice(string.digits) for _ in range(length))


def create_otp(user, otp_type, expiry_minutes=15, max_attempts=3):
    """
    Create a new OTP for the user.
    
    Args:
        user: User instance
        otp_type: Type of OTP (from OTP.OTP_TYPE_CHOICES)
        expiry_minutes: OTP expiry time in minutes (default: 15)
        max_attempts: Maximum number of attempts allowed (default: 3)
        
    Returns:
        OTP: The created OTP instance
    """
    from datetime import datetime, timedelta
    from django.utils import timezone
    from apps.accounts.models import OTP
    
    # Invalidate any existing OTPs of the same type
    OTP.objects.filter(user=user, otp_type=otp_type, is_used=False).update(is_used=True)
    
    # Create new OTP
    otp = OTP.objects.create(
        user=user,
        otp=generate_otp_code(),
        otp_type=otp_type,
        expires_at=timezone.now() + timedelta(minutes=expiry_minutes),
        max_attempts=max_attempts,
        attempts_remaining=max_attempts
    )
    
    return otp


def verify_otp(user, otp_code, otp_type):
    """
    Verify an OTP code for a user.
    
    Args:
        user: User instance
        otp_code: The OTP code to verify
        otp_type: Type of OTP (from OTP.OTP_TYPE_CHOICES)
        
    Returns:
        tuple: (is_valid, otp_instance, error_message)
    """
    from django.utils import timezone
    from apps.accounts.models import OTP
    
    try:
        otp = OTP.objects.get(
            user=user,
            otp=otp_code,
            otp_type=otp_type,
            is_used=False,
            expires_at__gt=timezone.now(),
            attempts_remaining__gt=0
        )
        
        # Mark OTP as used
        otp.is_used = True
        otp.verified_at = timezone.now()
        otp.save(update_fields=['is_used', 'verified_at', 'updated_at'])
        
        return True, otp, None
        
    except OTP.DoesNotExist:
        # Decrement attempts for any active OTPs of this type
        otps = OTP.objects.filter(
            user=user,
            otp_type=otp_type,
            is_used=False,
            expires_at__gt=timezone.now(),
            attempts_remaining__gt=0
        )
        
        for otp in otps:
            otp.attempts_remaining -= 1
            otp.save(update_fields=['attempts_remaining', 'updated_at'])
        
        return False, None, _("Invalid or expired OTP code")


def send_otp_email(user, otp, request=None):
    """
    Send OTP code via email.
    
    Args:
        user: User instance
        otp: OTP instance
        request: HttpRequest for building absolute URLs
        
    Returns:
        bool: True if email was sent successfully, False otherwise
    """
    subject = _("Your Verification Code")
    
    # Customize message based on OTP type
    if otp.otp_type == OTP.EMAIL_VERIFICATION:
        message = _(
            f"Your email verification code is: {otp.otp}\n"
            f"This code will expire in 15 minutes."
        )
    elif otp.otp_type == OTP.PASSWORD_RESET:
        message = _(
            f"Your password reset code is: {otp.otp}\n"
            f"This code will expire in 15 minutes.\n\n"
            f"If you didn't request this, please ignore this email."
        )
    else:
        message = _(
            f"Your verification code is: {otp.otp}\n"
            f"This code will expire in 15 minutes."
        )
    
    return send_email(request, subject, message, [user.email])


def send_otp_sms(user, otp, request=None):
    """
    Send OTP code via SMS.
    
    Args:
        user: User instance
        otp: OTP instance
        request: HttpRequest for building absolute URLs
        
    Returns:
        bool: True if SMS was sent successfully, False otherwise
    """
    if not user.phone_number:
        return False
    
    # Customize message based on OTP type
    if otp.otp_type == OTP.PHONE_VERIFICATION:
        message = _(
            f"Your phone verification code is: {otp.otp}. "
            f"Expires in 15 min."
        )
    elif otp.otp_type == OTP.LOGIN_VERIFICATION:
        message = _(
            f"Your login code is: {otp.otp}. "
            f"Expires in 15 min."
        )
    else:
        message = _(
            f"Your verification code is: {otp.otp}. "
            f"Expires in 15 min."
        )
    
    return send_sms(user.phone_number, message)


def send_sms(phone_number, message):
    """
    Send SMS using provider configured in database settings
    Returns True on success, False on failure
    """
    try:
        # Get SMS settings from database
        sms_settings = SMSSettings.objects.filter(is_active=True).first()
        
        if not sms_settings:
            logger.error("No active SMS settings found in database")
            return False

        # Clean phone number format
        phone_number = ''.join(filter(str.isdigit, phone_number))
        if not phone_number.startswith('+'):
            phone_number = '+' + phone_number

        # Send via Twilio
        if sms_settings.provider == 'twilio':
            from twilio.rest import Client
            client = Client(sms_settings.twilio_account_sid, 
                            sms_settings.twilio_auth_token)
            
            try:
                message = client.messages.create(
                    body=message,
                    from_=sms_settings.twilio_phone_number,
                    to=phone_number
                )
                logger.info(f"Twilio SMS sent to {phone_number}. SID: {message.sid}")
                return True
            except Exception as e:
                logger.error(f"Twilio error: {str(e)}")
                return False

        # Send via Africa's Talking
        elif sms_settings.provider == 'africastalking':
            import africastalking
            
            africastalking.initialize(
                username=sms_settings.africastalking_username,
                api_key=sms_settings.africastalking_api_key
            )
            
            try:
                sms = africastalking.SMS
                response = sms.send(
                    message, 
                    [phone_number],
                    sender_id=sms_settings.africastalking_sender_id
                )
                recipients = response['SMSMessageData']['Recipients']
                if recipients and recipients[0]['statusCode'] == 101:
                    logger.info(f"Africa's Talking SMS sent to {phone_number}")
                    return True
                logger.error(f"Africa's Talking error: {response}")
                return False
            except Exception as e:
                logger.error(f"Africa's Talking error: {str(e)}")
                return False

        else:
            logger.error(f"Unknown SMS provider: {sms_settings.provider}")
            return False

    except Exception as e:
        logger.exception("Unexpected error in send_sms")
        return False
     
    
    
    
    
