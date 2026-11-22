from django.db import models
from django.contrib.auth.models import User
from services.models import Service


class ServiceRequest(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_REJECTED = 'rejected'
    STATUS_INPROGRESS = 'inprogress'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_INPROGRESS, 'In Progress'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    # Status badge colors
    STATUS_CLASSES = {
        STATUS_PENDING: 'badge-warning',
        STATUS_ACCEPTED: 'badge-info',
        STATUS_REJECTED: 'badge-danger',
        STATUS_INPROGRESS: 'badge-primary',
        STATUS_COMPLETED: 'badge-success',
        STATUS_CANCELLED: 'badge-secondary',
    }

    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='service_requests')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='servicerequest')
    requested_date = models.DateField()
    requested_time = models.TimeField(null=True, blank=True)
    service_location = models.TextField(help_text="General address or area for the service")
    work_description = models.TextField(help_text="Describe the work you need done")
    notes = models.TextField(blank=True, help_text="Any additional notes for the provider")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    provider_response = models.TextField(blank=True, help_text="Provider's response or notes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Service Request'
        verbose_name_plural = 'Service Requests'
        ordering = ['-created_at']

    def __str__(self):
        return f"Request #{self.pk} - {self.service.title} by {self.customer.username}"

    @property
    def get_status_badge_class(self):
        return self.STATUS_CLASSES.get(self.status, 'badge-secondary')

    @property
    def can_be_cancelled(self):
        """Customer can cancel pending or accepted requests."""
        return self.status in [self.STATUS_PENDING, self.STATUS_ACCEPTED]

    @property
    def has_review(self):
        return hasattr(self, 'review')


class SavedService(models.Model):
    customer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_services')
    service = models.ForeignKey(Service, on_delete=models.CASCADE, related_name='saved_by')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Saved Service'
        verbose_name_plural = 'Saved Services'
        unique_together = [['customer', 'service']]
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.customer.username} saved {self.service.title}"
