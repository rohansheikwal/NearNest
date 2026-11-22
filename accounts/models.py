from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


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
