from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import (
    EmailConfig, SMSSettings, Address, TaxSettings, POSSettings, 
    ReceiptSettings, NotificationSettings, PaymentGatewaySettings
)

User = get_user_model()


class EmailConfigSerializer(serializers.ModelSerializer):
    """Serializer for EmailConfig model."""
    class Meta:
        model = EmailConfig
        fields = [
            'id', 'provider', 'email_host', 'email_port', 'email_host_user',
            'email_host_password', 'email_use_tls', 'email_use_ssl',
            'fail_silently', 'email_from', 'email_from_name',
            'email_subject', 'email_body'
        ]
        extra_kwargs = {
            'email_host_password': {'write_only': True}
        }


class SMSSettingsSerializer(serializers.ModelSerializer):
    """Serializer for SMSSettings model."""
    class Meta:
        model = SMSSettings
        fields = [
            'id', 'provider', 'is_active', 'twilio_account_sid',
            'twilio_auth_token', 'twilio_phone_number',
            'africastalking_username', 'africastalking_api_key',
            'africastalking_sender_id'
        ]
        extra_kwargs = {
            'twilio_auth_token': {'write_only': True},
            'africastalking_api_key': {'write_only': True}
        }


class AddressSerializer(serializers.ModelSerializer):
    """Serializer for Address model."""
    class Meta:
        model = Address
        fields = [
            'id', 'address_type', 'address_line1', 'address_line2',
            'city', 'state', 'postal_code', 'country', 'is_primary',
            'notes', 'latitude', 'longitude', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class TaxSettingsSerializer(serializers.ModelSerializer):
    """Serializer for TaxSettings model."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = TaxSettings
        fields = [
            'id', 'enabled', 'use_for_pos', 'default_rate', 'tax_name',
            'tax_description', 'tax_inclusive', 'round_tax',
            'allow_multiple_rates', 'created_by_name', 'updated_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by_name', 'updated_by_name']


class POSSettingsSerializer(serializers.ModelSerializer):
    """Serializer for POSSettings model."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = POSSettings
        fields = [
            'id', 'require_customer', 'allow_anonymous_orders',
            'allow_hold_orders', 'allow_discounts', 'allow_void',
            'allow_refunds', 'max_discount_percent', 'require_discount_reason',
            'default_payment_method', 'allow_split_payments',
            'require_payment_confirmation', 'auto_print_receipt',
            'show_tax_breakdown', 'show_qr_code', 'enable_kds',
            'auto_assign_orders', 'created_by_name', 'updated_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by_name', 'updated_by_name']


class ReceiptSettingsSerializer(serializers.ModelSerializer):
    """Serializer for ReceiptSettings model."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = ReceiptSettings
        fields = [
            'id', 'header_text', 'footer_text', 'show_logo',
            'show_tax_breakdown', 'show_qr_code', 'show_barcode',
            'paper_width', 'font_size', 'alignment', 'show_order_number',
            'show_date_time', 'show_cashier', 'show_customer',
            'show_payment_method', 'show_terms', 'terms_text',
            'show_return_policy', 'return_policy_text',
            'created_by_name', 'updated_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by_name', 'updated_by_name']


class NotificationSettingsSerializer(serializers.ModelSerializer):
    """Serializer for NotificationSettings model."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    class Meta:
        model = NotificationSettings
        fields = [
            'id', 'email_notifications', 'alert_email', 'sms_notifications',
            'alert_phone', 'push_notifications', 'low_stock_alerts',
            'low_stock_threshold', 'order_notifications',
            'payment_notifications', 'refund_notifications',
            'system_maintenance', 'security_alerts', 'backup_notifications',
            'created_by_name', 'updated_by_name', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at', 'created_by_name', 'updated_by_name']


class PaymentGatewaySettingsSerializer(serializers.ModelSerializer):
    """Serializer for PaymentGatewaySettings model."""
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    gateway_display_name = serializers.CharField(source='get_gateway_name_display', read_only=True)
    
    class Meta:
        model = PaymentGatewaySettings
        fields = [
            'id', 'gateway_name', 'gateway_display_name', 'is_active',
            'is_default', 'api_key', 'secret_key', 'webhook_url',
            'mpesa_consumer_key', 'mpesa_consumer_secret', 'mpesa_passkey',
            'mpesa_shortcode', 'mpesa_environment', 'card_processor',
            'paypal_client_id', 'paypal_secret', 'paypal_environment',
            'stripe_publishable_key', 'stripe_secret_key', 'stripe_webhook_secret',
            'transaction_fee_percent', 'transaction_fee_fixed',
            'minimum_amount', 'maximum_amount', 'display_name',
            'description', 'icon', 'created_by_name', 'updated_by_name',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'created_at', 'updated_at', 'created_by_name', 'updated_by_name',
            'gateway_display_name'
        ]
        extra_kwargs = {
            'secret_key': {'write_only': True},
            'mpesa_consumer_secret': {'write_only': True},
            'mpesa_passkey': {'write_only': True},
            'paypal_secret': {'write_only': True},
            'stripe_secret_key': {'write_only': True},
            'stripe_webhook_secret': {'write_only': True}
        }


class PaymentGatewaySettingsListSerializer(serializers.ModelSerializer):
    """Simplified serializer for listing payment gateways."""
    gateway_display_name = serializers.CharField(source='get_gateway_name_display', read_only=True)
    
    class Meta:
        model = PaymentGatewaySettings
        fields = [
            'id', 'gateway_name', 'gateway_display_name', 'is_active',
            'is_default', 'display_name', 'description', 'icon',
            'transaction_fee_percent', 'transaction_fee_fixed',
            'minimum_amount', 'maximum_amount'
        ]


class SettingsOverviewSerializer(serializers.Serializer):
    """Serializer for settings overview."""
    tax_settings = TaxSettingsSerializer()
    pos_settings = POSSettingsSerializer()
    receipt_settings = ReceiptSettingsSerializer()
    notification_settings = NotificationSettingsSerializer()
    payment_gateways = PaymentGatewaySettingsListSerializer(many=True)
    email_config = EmailConfigSerializer()
    sms_settings = SMSSettingsSerializer()


class LogoUploadSerializer(serializers.Serializer):
    """Serializer for logo upload."""
    logo = serializers.ImageField(required=True)
    
    def validate_logo(self, value):
        """Validate logo file."""
        # Check file size (max 5MB)
        if value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("Logo file size must be less than 5MB.")
        
        # Check file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if value.content_type not in allowed_types:
            raise serializers.ValidationError("Only JPEG, PNG, GIF, and WebP images are allowed.")
        
        return value 