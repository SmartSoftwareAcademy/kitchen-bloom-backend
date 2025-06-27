"""
URL configuration for Kitchen Bloom POS + KDS project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include, re_path
from django.views.generic import TemplateView, RedirectView
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework import permissions
from django.http import JsonResponse

# Admin Site Config
admin.site.site_header = 'Kitchen Bloom Admin'
admin.site.site_title = 'Kitchen Bloom Admin Portal'
admin.site.index_title = 'Welcome to Kitchen Bloom Admin Portal'

from django.http import JsonResponse


def currencies_view(request):
    from django.conf import settings
    return JsonResponse({
        'supported_currencies': getattr(settings, 'SUPPORTED_CURRENCIES', ['KES']),
        'default_currency': getattr(settings, 'DEFAULT_CURRENCY', 'KES'),
    })

# API URL Patterns
api_patterns = [
    # Authentication & User Management
    path('auth/', include('apps.accounts.urls')),
    # System Settings & Configuration
    path('base/', include('apps.base.urls')),
    # Add other apps here
    path('accounting/', include('apps.accounting.urls')),
    path('branches/', include('apps.branches.urls')),
    path('crm/', include('apps.crm.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('kds/', include('apps.kds.urls')),
    path('loyalty/', include('apps.loyalty.urls')),
    path('payroll/', include('apps.payroll.urls')),
    path('reporting/', include('apps.reporting.urls')),
    path('sales/', include('apps.sales.urls')),
    path('tables/', include('apps.tables.urls')),
    path('currencies/', currencies_view, name='currencies'),
]

def currencies_view(request):
    return JsonResponse({
        'supported_currencies': getattr(settings, 'SUPPORTED_CURRENCIES', ['KES']),
        'default_currency': getattr(settings, 'DEFAULT_CURRENCY', 'KES'),
    })

urlpatterns = [
    # Root URL redirects to admin
    path('', RedirectView.as_view(url='/admin/', permanent=False)),
    
    # Django Admin
    path('admin/', admin.site.urls),
    
    # i18n URL patterns
    path('i18n/', include('django.conf.urls.i18n')),
    
    # API
    path('api/v1/', include(api_patterns)),
    
    # API Schema and Documentation
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    
    # Swagger UI - For API testing and documentation
    path('api/docs/', SpectacularSwaggerView.as_view(
        url_name='schema',
        permission_classes=[permissions.IsAuthenticated]
    ), name='swagger-ui'),
    
    # ReDoc - Alternative API documentation
    path('api/redoc/', SpectacularRedocView.as_view(
        url_name='schema',
        permission_classes=[permissions.IsAuthenticated]
    ), name='redoc'),
    
    # Health check endpoint
    path('health/', include('health_check.urls')),
]

# Serve media files in development (MUST come before catch-all)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Catch-all for frontend (handled by Vue.js) - MUST come last
urlpatterns += [
    re_path(r'^.*$', TemplateView.as_view(template_name='index.html'), name='frontend'),
]

# Debug toolbar
if 'debug_toolbar' in settings.INSTALLED_APPS:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns
