from django.contrib.auth.models import User
from django.db import models


class ContactMessage(models.Model):
    name = models.CharField(max_length=150)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Contact Message'
        verbose_name_plural = 'Contact Messages'
        ordering = ['-created_at']

    def __str__(self):
        return f"Message from {self.name} — {self.subject}"


class Notification(models.Model):
    TYPE_BOOKING_NEW = 'booking_new'
    TYPE_BOOKING_STATUS = 'booking_status'
    TYPE_CHAT_MESSAGE = 'chat_message'
    TYPE_REVIEW = 'review'
    TYPE_SYSTEM = 'system'

    TYPE_CHOICES = [
        (TYPE_BOOKING_NEW, 'New Booking'),
        (TYPE_BOOKING_STATUS, 'Booking Status Update'),
        (TYPE_CHAT_MESSAGE, 'New Message'),
        (TYPE_REVIEW, 'New Review'),
        (TYPE_SYSTEM, 'System Notification'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=30, choices=TYPE_CHOICES, default=TYPE_SYSTEM)
    target_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.user.username}: {self.title}"


def send_notification(user, title, message, target_url='', notification_type=Notification.TYPE_SYSTEM):
    """Helper to create an in-app notification safely."""
    if not user or not user.is_authenticated:
        return None
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        target_url=target_url,
        notification_type=notification_type,
    )
