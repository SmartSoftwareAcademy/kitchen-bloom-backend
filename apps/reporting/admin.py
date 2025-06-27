from django.contrib import admin, messages
from django.utils.translation import gettext_lazy as _

from .models import (
    Report, ReportSchedule, ReportFilter, ReportExecutionLog
)


class ReportFilterInline(admin.TabularInline):
    model = ReportFilter
    extra = 1
    fields = ('filter_name', 'filter_value')


class ReportScheduleInline(admin.TabularInline):
    model = ReportSchedule
    extra = 1
    fields = ('frequency', 'format', 'is_active', 'next_run')
    readonly_fields = ('next_run',)



class ReportExecutionLogInline(admin.TabularInline):
    model = ReportExecutionLog
    extra = 0
    fields = ('started_at', 'status', 'duration', 'file_size')
    readonly_fields = ('started_at', 'status', 'duration', 'file_size')
    can_delete = False
    max_num = 5
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def duration(self, obj):
        return f"{obj.duration:.2f}s" if obj.duration else "N/A"
    duration.short_description = _('Duration')


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'is_active', 'created_at', 'created_by')
    list_filter = ('report_type', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'report_type', 'is_active')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [ReportFilterInline, ReportScheduleInline, ReportExecutionLogInline]
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class ReportFilterInlineForSchedule(admin.TabularInline):
    model = ReportFilter
    extra = 0
    fields = ('filter_name', 'filter_value')
    readonly_fields = ('filter_name', 'filter_value')
    can_delete = False
    show_change_link = True
    fk_name = 'report'  # This inline is only used in ReportAdmin


@admin.register(ReportSchedule)
class ReportScheduleAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'frequency', 'is_active', 'last_run', 'next_run')
    list_filter = ('frequency', 'is_active', 'format')
    search_fields = ('report__name',)
    readonly_fields = ('last_run', 'next_run', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('report', 'frequency', 'format', 'is_active')
        }),
        ('Schedule', {
            'fields': ('last_run', 'next_run')
        }),
        ('Recipients', {
            'fields': ('recipients',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    filter_horizontal = ('recipients',)
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if 'frequency' in form.changed_data:
            obj.update_schedule()
    
    def run_now(self, request, queryset):
        from .tasks import generate_report_async
        
        count = 0
        for schedule in queryset:
            generate_report_async.delay(
                report_id=schedule.report.id,
                user_id=request.user.id,
                schedule_id=schedule.id
            )
            count += 1
        
        messages.success(
            request,
            f"Scheduled {count} report{'s' if count != 1 else ''} for generation."
        )
    run_now.short_description = _("Run selected schedules now")
    
    actions = [run_now]


@admin.register(ReportExecutionLog)
class ReportExecutionLogAdmin(admin.ModelAdmin):
    list_display = ('report', 'status', 'started_at', 'completed_at', 'duration_display', 'file_size_display')
    list_filter = ('status', 'started_at')
    search_fields = ('report__name', 'error_message')
    readonly_fields = (
        'report', 'scheduled_run', 'started_at', 'completed_at', 'status',
        'error_message', 'file_path', 'file_size', 'created_by', 'duration'
    )
    fieldsets = (
        ('Execution Details', {
            'fields': ('report', 'scheduled_run', 'status', 'error_message')
        }),
        ('Timing', {
            'fields': ('started_at', 'completed_at', 'duration')
        }),
        ('Output', {
            'fields': ('file_path', 'file_size')
        }),
        ('Metadata', {
            'fields': ('created_by',),
            'classes': ('collapse',)
        }),
    )
    
    def duration_display(self, obj):
        return f"{obj.duration:.2f}s" if obj.duration else "N/A"
    duration_display.short_description = _('Duration')
    
    def file_size_display(self, obj):
        if not obj.file_size:
            return "N/A"
        size_kb = obj.file_size / 1024
        if size_kb < 1024:
            return f"{size_kb:.1f} KB"
        return f"{size_kb/1024:.1f} MB"
    file_size_display.short_description = _('File Size')
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


# Register models with default admin
admin.site.register(ReportFilter)
