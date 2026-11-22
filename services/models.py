from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify
from django.urls import reverse


class ServiceCategory(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=100, blank=True, help_text="Lucide icon name e.g. 'wrench'")
    image = models.ImageField(upload_to='categories/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = 'Service Category'
        verbose_name_plural = 'Service Categories'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('services:category', kwargs={'slug': self.slug})

    @property
    def service_count(self):
        return self.services.filter(is_active=True).count()


class Service(models.Model):
    UNIT_HOUR = 'hour'
    UNIT_VISIT = 'visit'
    UNIT_DAY = 'day'
    UNIT_PROJECT = 'project'
    UNIT_CHOICES = [
        (UNIT_HOUR, 'Per Hour'),
        (UNIT_VISIT, 'Per Visit'),
        (UNIT_DAY, 'Per Day'),
        (UNIT_PROJECT, 'Per Project'),
    ]

    provider = models.ForeignKey(User, on_delete=models.CASCADE, related_name='services')
    category = models.ForeignKey(ServiceCategory, on_delete=models.SET_NULL, null=True, related_name='services')
    title = models.CharField(max_length=200)
    description = models.TextField()
    image = models.ImageField(upload_to='services/', blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    pricing_unit = models.CharField(max_length=20, choices=UNIT_CHOICES, default=UNIT_VISIT)
    city = models.CharField(max_length=100)
    area = models.CharField(max_length=100, blank=True)
    availability = models.TextField(blank=True, help_text="e.g. Mon–Sat, 9 AM–6 PM")
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Service'
        verbose_name_plural = 'Services'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} by {self.provider.username}"

    def get_absolute_url(self):
        return reverse('services:service_detail', kwargs={'pk': self.pk})

    def get_average_rating(self):
        from reviews.models import Review
        from django.db.models import Avg
        result = Review.objects.filter(service_request__service=self).aggregate(avg=Avg('rating'))
        return round(result['avg'], 1) if result['avg'] else None

    def get_review_count(self):
        from reviews.models import Review
        return Review.objects.filter(service_request__service=self).count()

    def get_price_display(self):
        return f"₹{self.price:,.0f} {self.get_pricing_unit_display()}"

    def get_location_display(self):
        parts = [p for p in [self.area, self.city] if p]
        return ', '.join(parts) if parts else 'Location not specified'
