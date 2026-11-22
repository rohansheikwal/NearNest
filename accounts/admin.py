from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from .models import Profile, PasswordResetOTP


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ['role', 'full_name', 'profile_image', 'bio', 'skills', 'city', 'area', 'phone']


class UserAdmin(BaseUserAdmin):
    inlines = (ProfileInline,)
    list_display = ['username', 'email', 'get_role', 'get_city', 'is_staff', 'date_joined']
    list_filter = ['profile__role', 'is_staff', 'is_active']

    def get_role(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.get_role_display()
        return '-'
    get_role.short_description = 'Role'

    def get_city(self, obj):
        if hasattr(obj, 'profile'):
            return obj.profile.city
        return '-'
    get_city.short_description = 'City'


admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'role', 'full_name', 'city', 'area', 'phone', 'created_at']
    list_filter = ['role', 'city']
    search_fields = ['user__username', 'user__email', 'full_name', 'city']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']


@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ['email', 'user', 'created_at', 'expires_at', 'attempts', 'is_used']
    list_filter = ['is_used', 'created_at']
    search_fields = ['email', 'user__username']
    readonly_fields = ['created_at', 'expires_at', 'otp_hash', 'reset_token', 'token_expires_at']
    ordering = ['-created_at']
