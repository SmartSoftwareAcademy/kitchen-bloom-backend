import logging
from datetime import timedelta
from django.contrib.auth import logout
from django.conf import settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from rest_framework_simplejwt.tokens import RefreshToken, TokenError

from rest_framework import status, viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny

from .models import OTP, UserSession, Role
from .serializers import *
from apps.base.utils import *

User = get_user_model()
logger = logging.getLogger(__name__)


class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.filter(is_active=True).select_related('role')
    serializer_class = UserSerializer
    lookup_field = 'id'
    lookup_value_regex = r'[0-9a-f-]+'  # For UUID
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return UserRegistrationSerializer
        return self.serializer_class
        
    
    @action(detail=False, methods=['get'],url_path='profile')
    def profile(self, request):
        """Get current user profile."""
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
    
    @profile.mapping.patch
    def update_profile(self, request):
        """Update current user profile."""
        serializer = UserSerializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
    
    #make public 
    @action(detail=False, methods=['get'],url_path='sessions', permission_classes=[permissions.AllowAny])
    def sessions(self, request):
        """Get active user sessions."""
        sessions = UserSession.objects.filter(
            user=request.user, is_active=True
        ).order_by('-last_activity')
        serializer = self.get_serializer(sessions, many=True)
        return Response(serializer.data)
    

class LoginView(APIView):
    """
    API View to handle user login and return JWT tokens.
    Supports both email/password and biometric authentication.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = LoginSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        # Get the authenticated user
        user = serializer.validated_data['user']
        
        # Check if user is active
        if not user.is_active:
            return Response(
                {'detail': 'Account is disabled.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if email is verified if required
        # do not block users from login if not verified but alllow them to verify email after login from their profile
        
        # Create or update user session
        session = request.session
        session_key = session.session_key
        if not session_key:
            session.create()
            session_key = session.session_key
        
        # Get user agent and IP
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]  # Limit length
        ip_address = request.META.get('REMOTE_ADDR')
        
        # Create or update session in database
        UserSession.objects.update_or_create(
            session_key=session_key,
            defaults={
                'user': user,
                'user_agent': user_agent,
                'ip_address': ip_address,
                'is_active': True,
                'last_activity': timezone.now()
            }
        )
        
        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        # Update last login time
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        # Get user data with role information
        user_data = UserSerializer(user).data
        
        response_data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': user_data,
            'permissions': list(user.get_all_permissions()) if hasattr(user, 'get_all_permissions') else []
        }
        
        return Response(response_data, status=status.HTTP_200_OK)

class LogoutViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=['post'],url_path='logout')
    def logout(self, request):
        """Logout user by invalidating the current session."""
        try:
            session_key = request.session.session_key
            if session_key:
                UserSession.objects.filter(session_key=session_key).update(is_active=False)
            request.session.flush()
            logout(request)
            return Response({"detail": _("Successfully logged out.")})
        except Exception as e:
            logger.error(f"Error during logout: {str(e)}")
            return Response(
                {"detail": _("An error occurred while logging out.")},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ProfileViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UserProfileSerializer
    
    @action(detail=False, methods=['get'],url_path='profile')
    def profile(self, request):
        """Get current user profile."""
        # check if user email is verified
        if not request.user.is_verified:
            return Response(
                {'detail': _('Email is not verified.')},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    #verify email
    @action(detail=False, methods=['post'],url_path='verify-email')
    def verify_email(self, request):
        """Verify user email."""
        serializer = self.get_serializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.is_verified = True
        user.save()
        
        # Invalidate all sessions except the current one
        session_key = request.session.session_key
        UserSession.objects.filter(user=user).exclude(session_key=session_key).update(is_active=False)
        
        return Response({"detail": _("Email verified successfully.")})
    
    @profile.mapping.patch
    def update_profile(self, request):
        """Update current user profile."""
        serializer = self.get_serializer(
            request.user, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

class ChangePasswordViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]
    serializer_class = ChangePasswordSerializer
    
    @action(detail=False, methods=['post'],url_path='change-password')
    def change_password(self, request):
        """Change user password."""
        serializer = self.get_serializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        # Invalidate all sessions except the current one
        session_key = request.session.session_key
        UserSession.objects.filter(user=user).exclude(session_key=session_key).update(is_active=False)
        
        return Response({"detail": _("Password updated successfully.")})

class TokenRefreshView(generics.GenericAPIView):
    """
    Custom token refresh view that includes user data in the response.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = TokenRefreshSerializer
    
    def post(self, request, *args, **kwargs):
        refresh_token_str = request.data.get('refresh')
        
        if not refresh_token_str:
            return Response(
                {'detail': _('Refresh token is required.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            refresh = RefreshToken(refresh_token_str)
            
            # Create new access token
            access_token = str(refresh.access_token)
            
            # Get user from the new access token
            is_valid, user, user_message = verify_token(access_token)
            
            if not is_valid or not user:
                return Response(
                    {'detail': user_message or 'Invalid user'},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Generate new refresh token
            new_refresh = RefreshToken.for_user(user)
            
            response_data = {
                'tokens': {
                    'access': access_token,
                    'refresh': str(new_refresh),
                },
                'user': UserSerializer(user).data,
                'permissions': list(user.get_all_permissions()) if hasattr(user, 'get_all_permissions') else []
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error refreshing token: {str(e)}")
            return Response(
                {'detail': _('Invalid refresh token')},
                status=status.HTTP_401_UNAUTHORIZED
            )

class RequestOTPView(APIView):
    """
    Request an OTP for various verification purposes.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = RequestOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data.get('email')
        phone_number = serializer.validated_data.get('phone_number')
        otp_type = serializer.validated_data['otp_type']
        
        # Find user by email or phone
        user = None
        if email:
            try:
                user = User.objects.get(email=email, is_active=True)
            except User.DoesNotExist:
                if otp_type in [OTP.EMAIL_VERIFICATION, OTP.PASSWORD_RESET]:
                    return Response(
                        {'detail': _('No active account found with this email.')},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        elif phone_number:
            try:
                user = User.objects.get(phone_number=phone_number, is_active=True)
            except User.DoesNotExist:
                if otp_type == OTP.PHONE_VERIFICATION:
                    return Response(
                        {'detail': _('No active account found with this phone number.')},
                        status=status.HTTP_400_BAD_REQUEST
                    )
        
        # For new user registration, create a temporary user
        if not user and otp_type == OTP.EMAIL_VERIFICATION and email:
            user = User(email=email, is_active=False)
            user.save()
        
        if not user:
            return Response(
                {'detail': _('Invalid request. Please provide a valid email or phone number.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create and send OTP
        otp = create_otp(user=user, otp_type=otp_type)
        
        # Send OTP via appropriate channel
        if otp_type == OTP.EMAIL_VERIFICATION or (otp_type == OTP.PASSWORD_RESET and email):
            send_otp_email(user, otp, request)
        elif otp_type == OTP.PHONE_VERIFICATION or (otp_type == OTP.PASSWORD_RESET and phone_number):
            send_otp_sms(user, otp, request)
        
        # For security, don't reveal if the email/phone exists in the response
        return Response(
            {'detail': _('Verification code sent successfully.')},
            status=status.HTTP_200_OK
        )

class VerifyOTPView(APIView):
    """
    Verify an OTP code.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, *args, **kwargs):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data.get('email')
        phone_number = serializer.validated_data.get('phone_number')
        otp_code = serializer.validated_data['otp_code']
        otp_type = serializer.validated_data['otp_type']
        
        # Find user by email or phone
        user = None
        if email:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                pass
        elif phone_number:
            try:
                user = User.objects.get(phone_number=phone_number)
            except User.DoesNotExist:
                pass
        
        if not user:
            return Response(
                {'detail': _('Invalid verification code.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify OTP
        is_valid, otp = verify_otp(user, otp_code, otp_type)
        
        if not is_valid:
            return Response(
                {'detail': _('Invalid or expired verification code.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Mark OTP as used
        otp.is_used = True
        otp.used_at = timezone.now()
        otp.save()
        
        # For email verification, activate the user
        if otp_type == OTP.EMAIL_VERIFICATION and not user.is_active:
            user.is_active = True
            user.save()
        
        return Response({
            'detail': _('Verification successful.'),
            'is_new_user': not user.is_active,
            'user_id': str(user.id) if user.id else None
        })

class PasswordResetView(APIView):
    """
    Handle password reset with OTP verification.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetSerializer
    
    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        email = serializer.validated_data.get('email')
        phone_number = serializer.validated_data.get('phone_number')
        otp_code = serializer.validated_data.get('otp_code')
        new_password = serializer.validated_data.get('new_password')
        
        # Find user by email or phone
        user = None
        if email:
            try:
                user = User.objects.get(email=email, is_active=True)
            except User.DoesNotExist:
                pass
        elif phone_number:
            try:
                user = User.objects.get(phone_number=phone_number, is_active=True)
            except User.DoesNotExist:
                pass
        
        if not user:
            return Response(
                {'detail': _('No active account found with the provided credentials.')},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # If OTP code is provided, verify it
        if otp_code:
            is_valid, otp = verify_otp(user, otp_code, OTP.PASSWORD_RESET)
            if not is_valid:
                return Response(
                    {'detail': _('Invalid or expired verification code.')},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Mark OTP as used
            otp.is_used = True
            otp.used_at = timezone.now()
            otp.save()
            
            # Reset password
            user.set_password(new_password)
            user.save()
            
            return Response({
                'detail': _('Password has been reset successfully.')
            })
        
        # If no OTP code, send OTP
        otp = create_otp(user=user, otp_type=OTP.PASSWORD_RESET)
        
        # Send OTP via appropriate channel
        if email:
            send_otp_email(user, otp, request)
        elif phone_number:
            send_otp_sms(user, otp, request)
        
        return Response({
            'detail': _('Verification code sent to your registered email/phone.')
        })

class PermissionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint that allows permissions to be viewed.
    """
    queryset = Permission.objects.all()
    serializer_class = PermissionSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get_queryset(self):
        """Filter permissions based on query parameters."""
        queryset = super().get_queryset()
        
        # Filter by content type if provided
        content_type = self.request.query_params.get('content_type')
        if content_type:
            queryset = queryset.filter(content_type__model=content_type)
            
        # Search by name or codename
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) |
                Q(codename__icontains=search)
            )
            
        return queryset.select_related('content_type')
    
    @action(detail=False, methods=['get'])
    def content_types(self, request):
        """List all content types that have permissions."""
        from django.contrib.contenttypes.models import ContentType
        
        content_types = ContentType.objects.filter(
            permission__isnull=False
        ).distinct().order_by('app_label', 'model')
        
        data = [
            {
                'id': ct.id,
                'app_label': ct.app_label,
                'model': ct.model,
                'name': f"{ct.app_label}.{ct.model}"
            }
            for ct in content_types
        ]
        
        return Response(data)

class RoleViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows roles to be viewed or edited.
    """
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    
    def get_queryset(self):
        """Filter queryset based on user permissions."""
        queryset = super().get_queryset()
        
        # Regular users can only view their own role
        if not self.request.user.is_superuser and not self.request.user.is_staff:
            if self.request.user.role:
                queryset = queryset.filter(id=self.request.user.role.id)
            else:
                queryset = queryset.none()
                
        return queryset.prefetch_related('permissions')
    
    @action(detail=True, methods=['get', 'post'], url_path='permissions')
    def role_permissions(self, request, pk=None):
        """
        List or update permissions for a role.
        GET: List all permissions for the role
        POST: Update role permissions
        """
        role = self.get_object()
        
        if request.method == 'GET':
            permissions = role.permissions.all()
            serializer = PermissionSerializer(permissions, many=True)
            return Response(serializer.data)
            
        elif request.method == 'POST':
            serializer = RolePermissionSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            
            # Update role permissions
            permission_ids = serializer.validated_data['permission_ids']
            role.permissions.set(permission_ids)
            
            return Response(
                {'status': 'permissions updated'},
                status=status.HTTP_200_OK
            )
