from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from services.models import Service
from .models import ServiceRequest, SavedService
from .forms import ServiceRequestForm


def require_customer(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.is_customer:
            messages.error(request, "This action is for customers only.")
            return redirect('core:home')
        return view_func(request, *args, **kwargs)
    return wrapper


@require_customer
def request_service(request, service_pk):
    service = get_object_or_404(Service, pk=service_pk, is_active=True)
    if service.provider == request.user:
        messages.error(request, "You cannot request your own service.")
        return redirect('services:service_detail', pk=service_pk)

    if request.method == 'POST':
        form = ServiceRequestForm(request.POST)
        if form.is_valid():
            service_request = form.save(commit=False)
            service_request.customer = request.user
            service_request.service = service
            service_request.status = ServiceRequest.STATUS_PENDING
            service_request.save()
            messages.success(request, f'Your request for "{service.title}" has been sent! The provider will respond shortly.')
            return redirect('bookings:request_detail', pk=service_request.pk)
    else:
        form = ServiceRequestForm()

    return render(request, 'bookings/request_form.html', {
        'form': form,
        'service': service,
    })


@login_required
def request_detail(request, pk):
    if not hasattr(request.user, 'profile'):
        messages.error(request, "Your account profile is not available.")
        return redirect('core:home')

    if request.user.profile.is_customer:
        service_request = get_object_or_404(
            ServiceRequest.objects.select_related(
                'customer__profile', 'service__provider__profile', 'service__category'
            ),
            pk=pk,
            customer=request.user,
        )
    elif request.user.profile.is_provider:
        service_request = get_object_or_404(
            ServiceRequest.objects.select_related(
                'customer__profile', 'service__provider__profile', 'service__category'
            ),
            pk=pk,
            service__provider=request.user,
        )
    else:
        messages.error(request, "You do not have permission to view this request.")
        return redirect('core:home')

    return render(request, 'bookings/request_detail.html', {
        'service_request': service_request,
        'has_review': service_request.has_review,
        'is_provider_view': request.user == service_request.service.provider,
    })


@require_customer
@require_POST
def cancel_request(request, pk):
    service_request = get_object_or_404(ServiceRequest, pk=pk, customer=request.user)
    if service_request.can_be_cancelled:
        service_request.status = ServiceRequest.STATUS_CANCELLED
        service_request.save(update_fields=['status', 'updated_at'])
        messages.success(request, "Your request has been cancelled.")
    else:
        messages.error(request, f"This request cannot be cancelled in its current status: {service_request.get_status_display()}.")
    return redirect('bookings:my_requests')


@require_customer
def my_requests(request):
    status_filter = request.GET.get('status', '')
    requests = ServiceRequest.objects.filter(customer=request.user).select_related(
        'service', 'service__provider__profile', 'service__category'
    ).order_by('-created_at')
    if status_filter:
        requests = requests.filter(status=status_filter)
    return render(request, 'bookings/my_requests.html', {
        'requests': requests,
        'status_filter': status_filter,
        'status_choices': ServiceRequest.STATUS_CHOICES,
    })


@login_required
@require_POST
def toggle_save_service(request, service_pk):
    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('accept', '')
        or not request.META.get('HTTP_REFERER')
    )
    if not request.user.profile.is_customer:
        if is_ajax:
            return JsonResponse({'error': 'Customers only'}, status=403)
        messages.error(request, "This action is for customers only.")
        return redirect('services:service_detail', pk=service_pk)
    service = get_object_or_404(Service, pk=service_pk)
    saved, created = SavedService.objects.get_or_create(customer=request.user, service=service)
    if not created:
        saved.delete()
        if is_ajax:
            return JsonResponse({'saved': False, 'message': 'Removed from saved services'})
        messages.info(request, "Removed from saved services.")
        return redirect(request.META.get('HTTP_REFERER', 'services:service_detail'))
    if is_ajax:
        return JsonResponse({'saved': True, 'message': 'Saved to your list'})
    messages.success(request, "Saved to your list.")
    return redirect(request.META.get('HTTP_REFERER', 'services:service_detail'))


@require_customer
def saved_services(request):
    saved = SavedService.objects.filter(customer=request.user).select_related(
        'service', 'service__category', 'service__provider__profile'
    ).order_by('-created_at')
    return render(request, 'bookings/saved_services.html', {'saved_services': saved})


@require_customer
def remove_saved_service(request, pk):
    saved = get_object_or_404(SavedService, pk=pk, customer=request.user)
    if request.method == 'POST':
        saved.delete()
        messages.success(request, "Service removed from your saved list.")
    return redirect('bookings:saved_services')
