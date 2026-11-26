from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from bookings.models import ServiceRequest
from .models import Review
from .forms import ReviewForm


@login_required
def submit_review(request, request_pk):
    service_request = get_object_or_404(
        ServiceRequest, pk=request_pk, customer=request.user,
        status=ServiceRequest.STATUS_COMPLETED
    )
    # Prevent double review
    if service_request.has_review:
        messages.info(request, "You have already reviewed this service.")
        return redirect('bookings:request_detail', pk=request_pk)

    # Prevent provider from reviewing their own service through a customer account
    if service_request.service.provider == request.user:
        messages.error(request, "You cannot review your own service.")
        return redirect('core:home')

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.service_request = service_request
            review.save()

            # Notify provider of new review
            try:
                from core.models import send_notification, Notification
                from django.urls import reverse
                customer_name = request.user.profile.get_display_name() if hasattr(request.user, 'profile') else request.user.username
                send_notification(
                    user=service_request.service.provider,
                    title=f"New {review.rating}★ Review! ⭐",
                    message=f"{customer_name} left a {review.rating}-star review for '{service_request.service.title}'.",
                    target_url=reverse('services:provider_reviews'),
                    notification_type=Notification.TYPE_REVIEW
                )
            except Exception:
                pass

            messages.success(request, "Thank you for your review!")
            return redirect('bookings:request_detail', pk=request_pk)
    else:
        form = ReviewForm()

    return render(request, 'reviews/review_form.html', {
        'form': form,
        'service_request': service_request,
        'service': service_request.service,
    })
