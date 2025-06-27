from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django import forms
from .models import User, Role, OTP, UserSession


class UserAdminForm(forms.ModelForm):
    class Meta:
        model = User
        fields = '__all__'
        widgets = {
            'password': forms.PasswordInput(render_value=True),
        }

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_permissions_count', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('permissions',)
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'
    
    def get_permissions_count(self, obj):
        return obj.permissions.count()
    get_permissions_count.short_description = 'Permissions Count'


class UserAdmin(BaseUserAdmin):
    form = UserAdminForm
    add_form = UserCreationForm
    change_password_form = UserChangeForm
    
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active', 'last_login', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'is_verified', 'role')
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('first_name', 'last_name', 'phone_number')}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified', 
                     'groups', 'user_permissions'),
        }),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
        (_('Role'), {'fields': ('role',)}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'is_staff', 'is_active'),
        }),
    )
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-date_joined',)
    readonly_fields = ('last_login', 'date_joined')
    filter_horizontal = ('groups', 'user_permissions')
    date_hierarchy = 'date_joined'
    list_per_page = 25


@admin.register(OTP)
class OTPAdmin(admin.ModelAdmin):
    list_display = ('user', 'otp_type', 'is_used', 'expires_at', 'created_at')
    list_filter = ('otp_type', 'is_used', 'created_at')
    search_fields = ('user__email', 'otp')
    readonly_fields = ('created_at', 'expires_at')
    date_hierarchy = 'created_at'
    list_per_page = 25


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'ip_address', 'last_activity', 'is_active')
    list_filter = ('is_active', 'last_activity')
    search_fields = ('user__email', 'ip_address', 'session_key')
    readonly_fields = ('session_key', 'user_agent', 'ip_address', 'last_activity')
    date_hierarchy = 'last_activity'
    list_per_page = 25


# Register the User model with the custom UserAdmin
admin.site.register(User, UserAdmin)
