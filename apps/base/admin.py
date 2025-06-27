from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import *
from django.utils.safestring import mark_safe
import json

# Note: We don't register the abstract base models directly with admin
# These admin classes are meant to be inherited by concrete model admins

class TimestampedModelAdmin(admin.ModelAdmin):
    """
    Admin class for models that inherit from TimestampedModel.
    To use, inherit from this class in your concrete model's admin.
    """
    readonly_fields = ('created_at', 'updated_at')
    list_display = ('__str__', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


class SoftDeleteModelAdmin(admin.ModelAdmin):
    """
    Admin class for models that inherit from SoftDeleteModel.
    To use, inherit from this class in your concrete model's admin.
    """
    list_display = ('__str__', 'is_deleted', 'deleted_at', 'deleted_by')
    list_filter = ('is_deleted', 'deleted_at')
    actions = ['hard_delete_selected']
    
    def get_queryset(self, request):
        """Return a QuerySet of all model instances, including soft-deleted ones."""
        # Check if the model has all_objects manager (from SoftDeleteModel)
        if hasattr(self.model, 'all_objects'):
            qs = self.model.all_objects.get_queryset()
        else:
            qs = super().get_queryset(request)
            
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs
    
    def hard_delete_selected(self, request, queryset):
        """Hard delete selected items (bypass soft delete)."""
        if not hasattr(queryset.first(), 'hard_delete'):
            self.message_user(
                request,
                "Hard delete not available - model doesn't have hard_delete method",
                level='ERROR'
            )
            return
            
        count = 0
        for obj in queryset:
            obj.hard_delete()
            count += 1
            
        self.message_user(
            request,
            f"Successfully hard deleted {count} item{'s' if count != 1 else ''}.",
            level='SUCCESS'
        )
    
    hard_delete_selected.short_description = "Hard delete selected items"


class StatusModelAdmin(admin.ModelAdmin):
    """
    Admin class for models that have a status field.
    To use, inherit from this class in your concrete model's admin.
    """
    list_display = ('__str__', 'status')
    list_filter = ('status',)
    list_editable = ('status',)


class NameDescriptionModelAdmin(admin.ModelAdmin):
    """
    Admin class for models that have name and description fields.
    To use, inherit from this class in your concrete model's admin.
    """
    list_display = ('name', 'description_short')
    search_fields = ('name', 'description')
    
    def description_short(self, obj):
        """Return a shortened version of the description for the list display."""
        if hasattr(obj, 'description') and obj.description:
            return f"{obj.description[:100]}..." if len(obj.description) > 100 else obj.description
        return ""
    description_short.short_description = 'Description'


class BaseNameDescriptionModelAdmin(TimestampedModelAdmin, NameDescriptionModelAdmin):
    """
    Admin class for models that inherit from BaseNameDescriptionModel.
    Combines functionality from TimestampedModelAdmin and NameDescriptionModelAdmin.
    To use, inherit from this class in your concrete model's admin.
    """
    list_display = ('name', 'description_short', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    list_filter = ('created_at', 'updated_at')


@admin.register(SMSSettings)
class SMSSettingsAdmin(admin.ModelAdmin):
    list_display = ('provider', 'is_active')
    fieldsets = (
        (None, {'fields': ('provider', 'is_active')}),
        ('Twilio Settings', {
            'fields': ('twilio_account_sid', 'twilio_auth_token', 'twilio_phone_number'),
            'classes': ('collapse',)
        }),
        ("Africa's Talking Settings", {
            'fields': ('africastalking_username', 'africastalking_api_key', 'africastalking_sender_id'),
            'classes': ('collapse',)
        }),
    )

@admin.register(EmailConfig)
class EmailConfigAdmin(admin.ModelAdmin):
    list_display = ('provider', 'email_host', 'email_port', 'email_host_user', 'email_use_tls', 'email_use_ssl', 'email_from', 'email_from_name', 'email_subject', 'email_body','email_host_password')
    fieldsets = (
        (None, {'fields': ('provider', 'email_host', 'email_port', 'email_host_user', 'email_use_tls', 'email_use_ssl', 'email_from', 'email_from_name', 'email_subject', 'email_body','email_host_password')}),
    )

@admin.register(SystemModuleSettings)
class SystemModuleSettingsAdmin(admin.ModelAdmin):
    readonly_fields = ("structure_preview",)
    fields = ("modules_config", "structure_preview")

    def has_add_permission(self, request):
        # Only allow editing the singleton
        return not SystemModuleSettings.objects.exists()
    def has_delete_permission(self, request, obj=None):
        return False
    def structure_preview(self, obj):
        structure = obj.get_full_structure()
        pretty = json.dumps(structure, indent=2)
        return mark_safe(f'<pre style="max-height:400px;overflow:auto">{pretty}</pre>')
    structure_preview.short_description = "Discovered Structure (read-only)"
    