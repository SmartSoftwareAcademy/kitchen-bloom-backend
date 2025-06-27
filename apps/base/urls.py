from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    TaxSettingsViewSet, POSSettingsViewSet, ReceiptSettingsViewSet,
    NotificationSettingsViewSet, PaymentGatewaySettingsViewSet,
    EmailConfigViewSet, SMSSettingsViewSet, SettingsViewSet,
    ModuleSettingsView, ReportSettingsView
)

router = DefaultRouter()
router.register(r'tax-settings', TaxSettingsViewSet, basename='tax-settings')
router.register(r'pos-settings', POSSettingsViewSet, basename='pos-settings')
router.register(r'receipt-settings', ReceiptSettingsViewSet, basename='receipt-settings')
router.register(r'notification-settings', NotificationSettingsViewSet, basename='notification-settings')
router.register(r'payment-gateways', PaymentGatewaySettingsViewSet, basename='payment-gateways')
router.register(r'email-config', EmailConfigViewSet, basename='email-config')
router.register(r'sms-settings', SMSSettingsViewSet, basename='sms-settings')
router.register(r'settings', SettingsViewSet, basename='settings')

urlpatterns = [
    path('', include(router.urls)),
    path('settings/modules/', ModuleSettingsView.as_view(), name='module-settings'),
    path('settings/reports/', ReportSettingsView.as_view(), name='report-settings'),
] 