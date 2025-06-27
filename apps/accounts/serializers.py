from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import OTP, Role, UserSession
from django.contrib.auth.models import Permission

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ['id', 'name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

class PermissionSerializer(serializers.ModelSerializer):
    """Serializer for the Permission model."""
    content_type_name = serializers.SerializerMethodField()
    
    class Meta:
        model = Permission
        fields = ['id', 'name', 'codename', 'content_type', 'content_type_name']
        read_only_fields = ['id', 'name', 'codename', 'content_type', 'content_type_name']
    
    def get_content_type_name(self, obj):
        """Get the human-readable content type name."""
        return f"{obj.content_type.app_label}.{obj.content_type.model}"

class RolePermissionSerializer(serializers.Serializer):
    """Serializer for updating role permissions."""
    permission_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=True
    )
    
    def validate_permission_ids(self, value):
        """Validate that all permission IDs exist."""
        if not value:
            return value
            
        existing_ids = set(Permission.objects.filter(
            id__in=value
        ).values_list('id', flat=True))
        
        invalid_ids = set(value) - existing_ids
        if invalid_ids:
            raise serializers.ValidationError(
                f"Invalid permission IDs: {', '.join(map(str, invalid_ids))}"
            )
            
        return value

class UserSerializer(serializers.ModelSerializer):
    role= RoleSerializer(read_only=True)
    role_id = serializers.PrimaryKeyRelatedField(
        queryset=Role.objects.all(),
        source='role',
        write_only=True,
        required=False
    )
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'first_name', 'last_name',
            'is_active', 'is_verified', 'role', 'role_id', 'date_joined',
            'last_login', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'is_verified', 'date_joined', 'last_login',
            'created_at', 'updated_at'
        ]
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'is_active': {'read_only': True},
        }
    
    def create(self, validated_data):
        """Create and return a user with encrypted password."""
        password = validated_data.pop('password', None)
        user = User(**validated_data)
        if password:
            user.set_password(password)
        user.save()
        return user
    
    def update(self, instance, validated_data):
        """Update and return user."""
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        return super().update(instance, validated_data)

class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'first_name', 'last_name',
            'is_verified', 'date_joined', 'last_login'
        ]
        read_only_fields = ['id', 'email', 'is_verified', 'date_joined', 'last_login']

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        min_length=8,
        max_length=128
    )
    confirm_password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    
    class Meta:
        model = User
        fields = [
            'email', 'password', 'confirm_password',
            'first_name', 'last_name', 'phone_number'
        ]
        extra_kwargs = {
            'first_name': {'required': True},
            'last_name': {'required': True},
        }
    
    def validate(self, data):
        if data['password'] != data.pop('confirm_password'):
            raise serializers.ValidationError({"password": "Passwords don't match"})
        return data
    
    def create(self, validated_data):
        validated_data.pop('confirm_password', None)
        return User.objects.create_user(**validated_data)

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        style={'input_type': 'password'},
        trim_whitespace=False,
        write_only=True
    )
    token = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)
    
    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        
        if email and password:
            user = authenticate(
                request=self.context.get('request'),
                email=email,
                password=password
            )
            
            if not user:
                msg = _('Unable to log in with provided credentials.')
                raise serializers.ValidationError(msg, code='authorization')
            
            if not user.is_active:
                msg = _('User account is disabled.')
                raise serializers.ValidationError(msg, code='authorization')
            
            if not user.is_verified:
                msg = _('Please verify your email address.')
                raise serializers.ValidationError(msg, code='verification')
            
        else:
            msg = _('Must include "email" and "password".')
            raise serializers.ValidationError(msg, code='authorization')
        
        data['user'] = user
        return data

class OTPSerializer(serializers.ModelSerializer):
    class Meta:
        model = OTP
        fields = ['id', 'otp', 'otp_type', 'is_used', 'expires_at', 'created_at']
        read_only_fields = ['id', 'is_used', 'expires_at', 'created_at']

class RequestOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)
    otp_type = serializers.ChoiceField(choices=OTP.OTP_TYPE_CHOICES)
    
    def validate(self, data):
        email = data.get('email')
        phone_number = data.get('phone_number')
        otp_type = data.get('otp_type')
        
        if not email and not phone_number:
            raise serializers.ValidationError({
                'non_field_errors': ['Either email or phone number is required.']
            })
        
        if otp_type == OTP.EMAIL_VERIFICATION and not email:
            raise serializers.ValidationError({
                'email': ['Email is required for email verification.']
            })
            
        if otp_type == OTP.PHONE_VERIFICATION and not phone_number:
            raise serializers.ValidationError({
                'phone_number': ['Phone number is required for phone verification.']
            })
            
        return data

class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    phone_number = serializers.CharField(required=False)
    otp = serializers.CharField(required=True)
    otp_type = serializers.ChoiceField(choices=OTP.OTP_TYPE_CHOICES)
    
    def validate(self, data):
        email = data.get('email')
        phone_number = data.get('phone_number')
        otp = data.get('otp')
        otp_type = data.get('otp_type')
        
        if not email and not phone_number:
            raise serializers.ValidationError({
                'non_field_errors': ['Either email or phone number is required.']
            })
        
        try:
            if email:
                user = User.objects.get(email=email, is_active=True)
                otp_obj = OTP.objects.filter(
                    user=user,
                    otp=otp,
                    otp_type=otp_type,
                    is_used=False,
                    expires_at__gt=timezone.now()
                ).first()
            else:
                user = User.objects.get(phone_number=phone_number, is_active=True)
                otp_obj = OTP.objects.filter(
                    user=user,
                    otp=otp,
                    otp_type=otp_type,
                    is_used=False,
                    expires_at__gt=timezone.now()
                ).first()
                
            if not otp_obj:
                raise serializers.ValidationError({
                    'otp': ['Invalid or expired OTP.']
                })
                
            data['otp_obj'] = otp_obj
            data['user'] = user
            
        except User.DoesNotExist:
            raise serializers.ValidationError({
                'non_field_errors': ['User not found.']
            })
            
        return data

class PasswordResetSerializer(serializers.Serializer):
    email = serializers.EmailField(required=True)
    otp = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True,
        style={'input_type': 'password'},
        min_length=8,
        max_length=128
    )
    confirm_password = serializers.CharField(
        required=True,
        style={'input_type': 'password'}
    )
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': "Passwords don't match."
            })
            
        try:
            user = User.objects.get(email=data['email'], is_active=True)
            otp = OTP.objects.filter(
                user=user,
                otp=data['otp'],
                otp_type=OTP.PASSWORD_RESET,
                is_used=False,
                expires_at__gt=timezone.now()
            ).first()
            
            if not otp:
                raise serializers.ValidationError({
                    'otp': ['Invalid or expired OTP.']
                })
                
            data['otp_obj'] = otp
            data['user'] = user
            
        except User.DoesNotExist:
            raise serializers.ValidationError({
                'email': ['User not found.']
            })
            
        return data

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        required=True,
        style={'input_type': 'password'},
        write_only=True
    )
    new_password = serializers.CharField(
        required=True,
        style={'input_type': 'password'},
        min_length=8,
        max_length=128,
        write_only=True
    )
    confirm_password = serializers.CharField(
        required=True,
        style={'input_type': 'password'},
        write_only=True
    )
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is not correct.")
        return value
    
    def validate(self, data):
        if data['new_password'] != data['confirm_password']:
            raise serializers.ValidationError({
                'confirm_password': "Passwords don't match."
            })
        return data

class TokenRefreshSerializer(serializers.Serializer):
    """
    Serializer for token refresh endpoint.
    """
    refresh = serializers.CharField(required=True)
    access = serializers.CharField(read_only=True)

    def validate(self, attrs):
        from rest_framework_simplejwt.tokens import RefreshToken
        from rest_framework_simplejwt.exceptions import TokenError
        from django.utils.translation import gettext_lazy as _
        from django.conf import settings

        refresh = attrs.get('refresh')

        try:
            refresh_token = RefreshToken(refresh)
            data = {'access': str(refresh_token.access_token)}
            
            # Add refresh token to the response if rotation is enabled
            if getattr(settings, 'JWT_ROTATE_REFRESH_TOKENS', False):
                refresh_token.set_jti()
                refresh_token.set_exp()
                data['refresh'] = str(refresh_token)
            
            return data
            
        except TokenError:
            raise serializers.ValidationError({
                'refresh': _('Token is invalid or expired')
            })

class UserSessionSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSession
        fields = ['id', 'user_agent', 'ip_address', 'last_activity', 'is_active', 'created_at', 'updated_at']
        read_only_fields = ['id', 'user_agent', 'ip_address', 'last_activity', 'is_active', 'created_at', 'updated_at']
