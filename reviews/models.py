from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
from bookings.models import ServiceRequest


class Review(models.Model):
    service_request = models.OneToOneField(
        ServiceRequest, on_delete=models.CASCADE, related_name='review'
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['-created_at']

    def clean(self):
        if self.service_request_id:
            request = self.service_request
            if request.status != ServiceRequest.STATUS_COMPLETED:
                raise ValidationError('Reviews are allowed only for completed requests.')
            if request.customer_id == request.service.provider_id:
                raise ValidationError('Providers cannot review their own services.')
        if not self.comment or not self.comment.strip():
            raise ValidationError({'comment': 'Review text cannot be empty.'})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Review by {self.service_request.customer.username} for {self.service_request.service.title} ({self.rating}/5)"

    @property
    def service(self):
        return self.service_request.service

    @property
    def customer(self):
        return self.service_request.customer
