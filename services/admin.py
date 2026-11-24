from django.contrib import admin
from django import forms
from .models import Service, ServiceCategory


class ServiceAdminForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'duration_hours' in self.fields:
            self.fields['duration_hours'].required = False
        if 'available_days' in self.fields:
            self.fields['available_days'].required = False
        if 'start_time' in self.fields:
            self.fields['start_time'].required = False
        if 'end_time' in self.fields:
            self.fields['end_time'].required = False

    def clean_provider(self):
        provider = self.cleaned_data['provider']
        if not hasattr(provider, 'profile') or not provider.profile.is_provider:
            raise forms.ValidationError('Services can only be assigned to provider accounts.')
        return provider


@admin.register(ServiceCategory)
class ServiceCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'icon', 'is_active', 'order', 'service_count']
    list_filter = ['is_active']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_active', 'order']
    ordering = ['order', 'name']

    def service_count(self, obj):
        return obj.services.filter(is_active=True).count()
    service_count.short_description = 'Active Services'


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    form = ServiceAdminForm
    list_display = ['title', 'provider', 'category', 'price', 'pricing_unit',
                    'city', 'is_active', 'is_featured', 'created_at']
    list_filter = ['is_active', 'is_featured', 'category', 'pricing_unit']
    search_fields = ['title', 'description', 'provider__username', 'city']
    readonly_fields = ['created_at', 'updated_at']
    list_editable = ['is_active', 'is_featured']
    ordering = ['-created_at']
    raw_id_fields = ['provider']

    fieldsets = (
        ('Basic Info', {
            'fields': ('provider', 'category', 'title', 'description', 'image')
        }),
        ('Pricing & Location', {
            'fields': ('price', 'pricing_unit', 'city', 'area', 'availability')
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
