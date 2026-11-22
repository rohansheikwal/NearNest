import hashlib
import secrets
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class PasswordResetOTP(models.Model):
    MAX_ATTEMPTS = 5
    EXPIRY_MINUTES = 5
    COOLDOWN_SECONDS = 60

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset_otps')
    email = models.EmailField(db_index=True)
    otp_hash = models.CharField(max_length=64)  # SHA-256 hash of the 6-digit OTP
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.PositiveSmallIntegerField(default=0)
    is_used = models.BooleanField(default=False)
    reset_token = models.CharField(max_length=64, blank=True, null=True, unique=True)
    token_expires_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        verbose_name = 'Password Reset OTP'
        verbose_name_plural = 'Password Reset OTPs'
        ordering = ['-created_at']

    def __str__(self):
        return f"OTP for {self.email} ({self.created_at.strftime('%Y-%m-%d %H:%M:%S')})"

    @classmethod
    def hash_otp(cls, otp_str):
        return hashlib.sha256(otp_str.strip().encode('utf-8')).hexdigest()

    def verify_otp(self, entered_otp):
        """Verify entered OTP. Returns (is_valid: bool, error_msg: str)."""
        if self.is_used:
            return False, "This OTP has already been used. Please request a new one."
        if timezone.now() > self.expires_at:
            return False, "This OTP has expired. Please request a new one."
        if self.attempts >= self.MAX_ATTEMPTS:
            return False, "Maximum verification attempts exceeded. Please request a new OTP."

        hashed_input = self.hash_otp(entered_otp)
        if secrets.compare_digest(self.otp_hash, hashed_input):
            return True, ""

        self.attempts += 1
        self.save(update_fields=['attempts'])
        remaining = max(0, self.MAX_ATTEMPTS - self.attempts)
        if remaining > 0:
            return False, f"Invalid OTP. You have {remaining} attempt(s) remaining."
        return False, "Maximum verification attempts exceeded. Please request a new OTP."

    @property
    def is_expired(self):
        return timezone.now() > self.expires_at


class Profile(models.Model):
    ROLE_CUSTOMER = 'customer'
    ROLE_PROVIDER = 'provider'
    ROLE_CHOICES = [
        (ROLE_CUSTOMER, 'Customer'),
        (ROLE_PROVIDER, 'Service Provider'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CUSTOMER)
    full_name = models.CharField(max_length=150, blank=True)
    profile_image = models.ImageField(upload_to='profiles/', blank=True, null=True)
    bio = models.TextField(blank=True, help_text="Brief bio or introduction")
    skills = models.TextField(blank=True, help_text="Skills and specialties (provider only)")
    city = models.CharField(max_length=100, blank=True)
    area = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Profile'
        verbose_name_plural = 'Profiles'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def is_customer(self):
        return self.role == self.ROLE_CUSTOMER

    @property
    def is_provider(self):
        return self.role == self.ROLE_PROVIDER

    def get_display_name(self):
        return self.full_name or self.user.get_full_name() or self.user.username

    def get_location_display(self):
        parts = [p for p in [self.area, self.city] if p]
        return ', '.join(parts) if parts else 'Location not specified'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()
