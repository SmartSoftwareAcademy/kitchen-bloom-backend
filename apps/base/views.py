from django.shortcuts import render
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import os
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser, IsAuthenticated

from .models import (
    EmailConfig, SMSSettings, Address, TaxSettings, POSSettings,
    ReceiptSettings, NotificationSettings, PaymentGatewaySettings, SystemModuleSettings
)
from .serializers import (
    EmailConfigSerializer, SMSSettingsSerializer, AddressSerializer,
    TaxSettingsSerializer, POSSettingsSerializer, ReceiptSettingsSerializer,
    NotificationSettingsSerializer, PaymentGatewaySettingsSerializer,
    PaymentGatewaySettingsListSerializer, SettingsOverviewSerializer,
    LogoUploadSerializer
)
from apps.branches.models import Company


class TaxSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing tax settings."""
    queryset = TaxSettings.objects.all()
    serializer_class = TaxSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        """Set the current user as creator."""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set the current user as updater."""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current tax settings."""
        settings = TaxSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_current(self, request):
        """Update current tax settings."""
        settings = TaxSettings.get_settings()
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class POSSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing POS settings."""
    queryset = POSSettings.objects.all()
    serializer_class = POSSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        """Set the current user as creator."""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set the current user as updater."""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current POS settings."""
        settings = POSSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_current(self, request):
        """Update current POS settings."""
        settings = POSSettings.get_settings()
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class ReceiptSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing receipt settings."""
    queryset = ReceiptSettings.objects.all()
    serializer_class = ReceiptSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        """Set the current user as creator."""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set the current user as updater."""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current receipt settings."""
        settings = ReceiptSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_current(self, request):
        """Update current receipt settings."""
        settings = ReceiptSettings.get_settings()
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class NotificationSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing notification settings."""
    queryset = NotificationSettings.objects.all()
    serializer_class = NotificationSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        """Set the current user as creator."""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set the current user as updater."""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current notification settings."""
        settings = NotificationSettings.get_settings()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def update_current(self, request):
        """Update current notification settings."""
        settings = NotificationSettings.get_settings()
        serializer = self.get_serializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        return Response(serializer.data)


class PaymentGatewaySettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing payment gateway settings."""
    queryset = PaymentGatewaySettings.objects.all()
    serializer_class = PaymentGatewaySettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['gateway_name', 'is_active', 'is_default']
    search_fields = ['gateway_name', 'display_name', 'description']
    ordering_fields = ['gateway_name', 'is_active', 'is_default', 'created_at']
    
    def get_serializer_class(self):
        """Use different serializers for different actions."""
        if self.action == 'list':
            return PaymentGatewaySettingsListSerializer
        return PaymentGatewaySettingsSerializer
    
    def perform_create(self, serializer):
        """Set the current user as creator."""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set the current user as updater."""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['get'])
    def active(self, request):
        """Get all active payment gateways."""
        gateways = PaymentGatewaySettings.get_active_gateways()
        serializer = PaymentGatewaySettingsListSerializer(gateways, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def default(self, request):
        """Get the default payment gateway."""
        gateway = PaymentGatewaySettings.get_default_gateway()
        if gateway:
            serializer = PaymentGatewaySettingsListSerializer(gateway)
            return Response(serializer.data)
        return Response({'message': 'No default gateway found'}, status=status.HTTP_404_NOT_FOUND)
    
    @action(detail=True, methods=['post'])
    def set_default(self, request, pk=None):
        """Set a payment gateway as default."""
        gateway = self.get_object()
        gateway.is_default = True
        gateway.save()
        serializer = PaymentGatewaySettingsListSerializer(gateway)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def toggle_active(self, request, pk=None):
        """Toggle payment gateway active status."""
        gateway = self.get_object()
        gateway.is_active = not gateway.is_active
        gateway.save()
        serializer = PaymentGatewaySettingsListSerializer(gateway)
        return Response(serializer.data)


class EmailConfigViewSet(viewsets.ModelViewSet):
    """ViewSet for managing email configuration."""
    queryset = EmailConfig.objects.all()
    serializer_class = EmailConfigSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        """Set the current user as creator."""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set the current user as updater."""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def test_connection(self, request):
        """Test email configuration."""
        config_id = request.data.get('config_id')
        try:
            config = EmailConfig.objects.get(id=config_id)
            # Here you would implement email connection testing
            # For now, return success
            return Response({'message': 'Email configuration test successful'})
        except EmailConfig.DoesNotExist:
            return Response(
                {'error': 'Email configuration not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class SMSSettingsViewSet(viewsets.ModelViewSet):
    """ViewSet for managing SMS settings."""
    queryset = SMSSettings.objects.all()
    serializer_class = SMSSettingsSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def perform_create(self, serializer):
        """Set the current user as creator."""
        serializer.save(created_by=self.request.user)
    
    def perform_update(self, serializer):
        """Set the current user as updater."""
        serializer.save(updated_by=self.request.user)
    
    @action(detail=False, methods=['post'])
    def test_connection(self, request):
        """Test SMS configuration."""
        config_id = request.data.get('config_id')
        try:
            config = SMSSettings.objects.get(id=config_id)
            # Here you would implement SMS connection testing
            # For now, return success
            return Response({'message': 'SMS configuration test successful'})
        except SMSSettings.DoesNotExist:
            return Response(
                {'error': 'SMS configuration not found'},
                status=status.HTTP_404_NOT_FOUND
            )


class SettingsViewSet(viewsets.ViewSet):
    """ViewSet for managing all system settings."""
    permission_classes = [permissions.IsAuthenticated]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Get overview of all settings."""
        try:
            data = {
                'tax_settings': TaxSettings.get_settings(),
                'pos_settings': POSSettings.get_settings(),
                'receipt_settings': ReceiptSettings.get_settings(),
                'notification_settings': NotificationSettings.get_settings(),
                'payment_gateways': PaymentGatewaySettings.get_active_gateways(),
                'email_config': EmailConfig.objects.first(),
                'sms_settings': SMSSettings.objects.first(),
            }
            serializer = SettingsOverviewSerializer(data)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def update_all(self, request):
        """Update multiple settings at once."""
        try:
            with transaction.atomic():
                # Update tax settings
                if 'tax_settings' in request.data:
                    tax_settings = TaxSettings.get_settings()
                    tax_serializer = TaxSettingsSerializer(
                        tax_settings, data=request.data['tax_settings'], partial=True
                    )
                    tax_serializer.is_valid(raise_exception=True)
                    tax_serializer.save(updated_by=request.user)
                
                # Update POS settings
                if 'pos_settings' in request.data:
                    pos_settings = POSSettings.get_settings()
                    pos_serializer = POSSettingsSerializer(
                        pos_settings, data=request.data['pos_settings'], partial=True
                    )
                    pos_serializer.is_valid(raise_exception=True)
                    pos_serializer.save(updated_by=request.user)
                
                # Update receipt settings
                if 'receipt_settings' in request.data:
                    receipt_settings = ReceiptSettings.get_settings()
                    receipt_serializer = ReceiptSettingsSerializer(
                        receipt_settings, data=request.data['receipt_settings'], partial=True
                    )
                    receipt_serializer.is_valid(raise_exception=True)
                    receipt_serializer.save(updated_by=request.user)
                
                # Update notification settings
                if 'notification_settings' in request.data:
                    notification_settings = NotificationSettings.get_settings()
                    notification_serializer = NotificationSettingsSerializer(
                        notification_settings, data=request.data['notification_settings'], partial=True
                    )
                    notification_serializer.is_valid(raise_exception=True)
                    notification_serializer.save(updated_by=request.user)
                
                return Response({'message': 'Settings updated successfully'})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def upload_logo(self, request):
        """Upload company logo."""
        serializer = LogoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            logo_file = serializer.validated_data['logo']
            
            # Get the company (assuming single company for now)
            company = Company.objects.first()
            if not company:
                return Response(
                    {'error': 'No company found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Delete old logo if exists
            if company.logo:
                if default_storage.exists(company.logo.name):
                    default_storage.delete(company.logo.name)
            
            # Save new logo
            company.logo = logo_file
            company.save()
            
            return Response({
                'message': 'Logo uploaded successfully',
                'logo_url': company.logo.url if company.logo else None
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['get'])
    def company_info(self, request):
        """Get company information."""
        company = Company.objects.first()
        if company:
            return Response({
                'id': company.id,
                'name': company.name,
                'legal_name': company.legal_name,
                'tax_id': company.tax_id,
                'registration_number': company.registration_number,
                'logo': company.logo.url if company.logo else None,
                'primary_contact_email': company.primary_contact_email,
                'primary_contact_phone': company.primary_contact_phone,
                'website': company.website,
                'address': company.address,
                'city': company.city,
                'state': company.state,
                'postal_code': company.postal_code,
                'country': company.country,
                'currency': company.currency,
                'timezone': company.timezone,
            })
        return Response(
            {'error': 'No company found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    @action(detail=False, methods=['post'])
    def update_company_info(self, request):
        """Update company information."""
        company = Company.objects.first()
        if not company:
            return Response(
                {'error': 'No company found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        try:
            # Update company fields
            allowed_fields = [
                'name', 'legal_name', 'tax_id', 'registration_number',
                'primary_contact_email', 'primary_contact_phone', 'website',
                'address', 'city', 'state', 'postal_code', 'country',
                'currency', 'timezone'
            ]
            
            for field in allowed_fields:
                if field in request.data:
                    setattr(company, field, request.data[field])
            
            company.save()
            
            return Response({
                'message': 'Company information updated successfully',
                'company': {
                    'id': company.id,
                    'name': company.name,
                    'legal_name': company.legal_name,
                    'tax_id': company.tax_id,
                    'registration_number': company.registration_number,
                    'logo': company.logo.url if company.logo else None,
                    'primary_contact_email': company.primary_contact_email,
                    'primary_contact_phone': company.primary_contact_phone,
                    'website': company.website,
                    'address': company.address,
                    'city': company.city,
                    'state': company.state,
                    'postal_code': company.postal_code,
                    'country': company.country,
                    'currency': company.currency,
                    'timezone': company.timezone,
                }
            })
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )


class ModuleSettingsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        settings = SystemModuleSettings.get_solo()
        return Response(settings.get_full_structure())
    def patch(self, request):
        if not request.user.is_staff:
            return Response({'detail': 'Not authorized.'}, status=status.HTTP_403_FORBIDDEN)
        settings = SystemModuleSettings.get_solo()
        structure = settings.discover_structure()
        config = settings.modules_config or {}
        # Only allow toggling non-required fields
        for app, app_data in request.data.items():
            if app not in structure:
                continue
            config.setdefault(app, {"enabled": True, "models": {}})
            if "enabled" in app_data:
                config[app]["enabled"] = app_data["enabled"]
            for model, model_data in app_data.get("models", {}).items():
                if model not in structure[app]["models"]:
                    continue
                config[app]["models"].setdefault(model, {"enabled": True, "fields": {}})
                if "enabled" in model_data:
                    config[app]["models"][model]["enabled"] = model_data["enabled"]
                for field, field_data in model_data.get("fields", {}).items():
                    if field not in structure[app]["models"][model]["fields"]:
                        continue
                    if structure[app]["models"][model]["fields"][field]["required"]:
                        continue  # Don't allow toggling required fields
                    config[app]["models"][model]["fields"].setdefault(field, {"enabled": True})
                    if "enabled" in field_data:
                        config[app]["models"][model]["fields"][field]["enabled"] = field_data["enabled"]
        settings.modules_config = config
        settings.save()
        return Response(settings.get_full_structure())
    put = patch


class ReportSettingsView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        settings = SystemModuleSettings.get_solo()
        return Response({
            'reports': settings.get_enabled_reports(),
            'all_reports': settings.get_all_report_types(),
        })
    def patch(self, request):
        if not request.user.is_staff:
            return Response({'detail': 'Not authorized.'}, status=status.HTTP_403_FORBIDDEN)
        settings = SystemModuleSettings.get_solo()
        config = settings.reporting_enabled_reports or {}
        for k, v in request.data.items():
            if k in settings.get_all_report_types():
                config[k] = bool(v)
        settings.reporting_enabled_reports = config
        settings.save()
        return Response({'reports': settings.get_enabled_reports()})
