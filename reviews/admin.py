from django.contrib import admin
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'get_customer', 'get_service', 'rating', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['service_request__customer__username', 'service_request__service__title', 'comment']
    readonly_fields = ['created_at']
    ordering = ['-created_at']

    def get_customer(self, obj):
        return obj.service_request.customer.username
    get_customer.short_description = 'Customer'

    def get_service(self, obj):
        return obj.service_request.service.title
    get_service.short_description = 'Service'
