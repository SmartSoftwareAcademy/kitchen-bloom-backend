from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenVerifyView
import mfa
import mfa.TrustedDevice
from . import views

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r'users', views.UserViewSet, basename='user')
router.register(r'roles', views.RoleViewSet, basename='role')
router.register(r'permissions', views.PermissionViewSet, basename='permission')

# The API URLs are now determined automatically by the router
urlpatterns = [
    # Include router URLs first
    path('', include(router.urls)),
    path('mfa/', include('mfa.urls')),
    path('devices/add', mfa.TrustedDevice.add, name="mfa_add_new_trusted_device"), # This short link to add new trusted device 
    path('login/', views.LoginView.as_view(), name='login'),
    path('logout/', views.LogoutViewSet.as_view({'post': 'logout'}), name='logout'),
    path('change-password/', views.ChangePasswordViewSet.as_view({'post': 'change_password'}), name='change-password'),
    path('otp/request/', views.RequestOTPSerializer, name='request-otp'),
    path('otp/verify/', views.VerifyOTPSerializer, name='verify-otp'),
    path('password/reset/', views.PasswordResetView.as_view(), name='password-reset'),
    path('token/refresh/', views.TokenRefreshView.as_view(), name='token-refresh'),
    ]
