from django.contrib import admin
from .models import ServiceRequest, SavedService


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'service', 'status', 'requested_date', 'created_at']
    list_filter = ['status', 'requested_date']
    search_fields = ['customer__username', 'service__title', 'work_description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    raw_id_fields = ['customer', 'service']

    fieldsets = (
        ('Request Info', {
            'fields': ('customer', 'service', 'status')
        }),
        ('Schedule & Location', {
            'fields': ('requested_date', 'requested_time', 'service_location')
        }),
        ('Details', {
            'fields': ('work_description', 'notes', 'provider_response')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SavedService)
class SavedServiceAdmin(admin.ModelAdmin):
    list_display = ['customer', 'service', 'created_at']
    search_fields = ['customer__username', 'service__title']
    raw_id_fields = ['customer', 'service']
