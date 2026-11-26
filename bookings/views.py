import json
from datetime import date, datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from core.models import send_notification, Notification
from services.models import Service, DAY_NAMES
from .models import ServiceRequest, SavedService, BookingMessage
from .forms import ServiceRequestForm


def get_service_availability_dict(service):
    schedule = service.get_availability_schedule()
    booked_slots = service.get_booked_slots()

    serializable_days = {}
    for d, d_val in schedule.get('days', {}).items():
        if d_val.get('available'):
            serializable_days[str(d)] = {
                'available': True,
                'start_time': d_val['start_time'].strftime('%H:%M'),
                'end_time': d_val['end_time'].strftime('%H:%M'),
                'start_str': d_val['start_str'],
                'end_str': d_val['end_str'],
            }
        else:
            serializable_days[str(d)] = {'available': False}

    provider_name = (
        service.provider.profile.get_display_name()
        if hasattr(service.provider, 'profile')
        else service.provider.username
    )

    return {
        'service_id': service.pk,
        'service_title': service.title,
        'provider_id': service.provider_id,
        'provider_name': provider_name,
        'duration_hours': service.duration_hours or 1,
        'has_availability': schedule.get('has_availability', False),
        'summary': schedule.get('summary', ''),
        'available_weekday_indices': schedule.get('available_weekday_indices', []),
        'available_days_display': schedule.get('available_days_display', ''),
        'start_time_str': schedule.get('start_time_str', ''),
        'end_time_str': schedule.get('end_time_str', ''),
        'days': serializable_days,
        'booked_slots': booked_slots,
    }


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
    service = get_object_or_404(
        Service.objects.select_related('provider__profile', 'category'),
        pk=service_pk,
        is_active=True
    )
    if service.provider == request.user:
        messages.error(request, "You cannot request your own service.")
        return redirect('services:service_detail', pk=service_pk)

    if request.method == 'POST':
        form = ServiceRequestForm(request.POST, service=service)
        if form.is_valid():
            with transaction.atomic():
                date_val = form.cleaned_data['requested_date']
                time_val = form.cleaned_data.get('requested_time')
                date_ok, date_msg = service.is_date_available(date_val)
                if not date_ok:
                    form.add_error('requested_date', date_msg)
                    return render(request, 'bookings/request_form.html', {
                        'form': form,
                        'service': service,
                        'schedule': service.get_availability_schedule(),
                        'availability_json': json.dumps(get_service_availability_dict(service)),
                    })
                if time_val:
                    time_ok, time_msg = service.is_time_available(date_val, time_val)
                    if not time_ok:
                        form.add_error('requested_time', time_msg)
                        return render(request, 'bookings/request_form.html', {
                            'form': form,
                            'service': service,
                            'schedule': service.get_availability_schedule(),
                            'availability_json': json.dumps(get_service_availability_dict(service)),
                        })

                service_request = form.save(commit=False)
                service_request.customer = request.user
                service_request.service = service
                service_request.status = ServiceRequest.STATUS_PENDING
                service_request.save()

                # Notify provider of new booking
                try:
                    send_notification(
                        user=service.provider,
                        title="New Booking Request! 🔔",
                        message=f"{request.user.profile.get_display_name()} requested '{service.title}' for {service_request.requested_date.strftime('%d %b, %Y')}.",
                        target_url=reverse('bookings:request_detail', args=[service_request.pk]),
                        notification_type=Notification.TYPE_BOOKING_NEW
                    )
                except Exception:
                    pass

                messages.success(request, f'Your request for "{service.title}" has been sent! The provider will respond shortly.')
                return redirect('bookings:request_detail', pk=service_request.pk)
    else:
        form = ServiceRequestForm(service=service)

    schedule = service.get_availability_schedule()
    return render(request, 'bookings/request_form.html', {
        'form': form,
        'service': service,
        'schedule': schedule,
        'availability_json': json.dumps(get_service_availability_dict(service)),
    })


def service_availability_api(request, service_pk):
    service = get_object_or_404(
        Service.objects.select_related('provider__profile'),
        pk=service_pk,
        is_active=True
    )
    data = get_service_availability_dict(service)

    date_param = request.GET.get('date', '').strip()
    if date_param:
        try:
            d_parts = [int(p) for p in date_param.split('-')]
            check_date = date(d_parts[0], d_parts[1], d_parts[2])
            is_avail, err_msg = service.is_date_available(check_date)
            date_info = {
                'date': date_param,
                'is_available': is_avail,
                'error': err_msg,
                'weekday': check_date.weekday(),
                'weekday_name': DAY_NAMES[check_date.weekday()],
            }
            if is_avail:
                day_data = data['days'].get(str(check_date.weekday()), {})
                st = day_data.get('start_time')
                et = day_data.get('end_time')
                dur = service.duration_hours or 1
                if st and et:
                    closing_t = datetime.strptime(et, '%H:%M').time()
                    closing_dt = datetime.combine(check_date, closing_t)
                    max_start = (closing_dt - timedelta(hours=dur)).time()
                    date_info['start_time'] = st
                    date_info['end_time'] = et
                    date_info['max_start_time'] = max_start.strftime('%H:%M')
                    date_info['start_str'] = day_data.get('start_str')
                    date_info['end_str'] = day_data.get('end_str')
                    date_info['max_start_str'] = max_start.strftime('%I:%M %p')

            date_info['conflicts'] = [s for s in data['booked_slots'] if s['date'] == date_param]
            data['date_info'] = date_info
        except Exception:
            data['date_info'] = {'error': 'Invalid date format'}

    return JsonResponse(data)


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
        'booking_messages': service_request.messages.select_related('sender__profile').all(),
    })


@login_required
@require_POST
def send_booking_message(request, pk):
    service_request = get_object_or_404(
        ServiceRequest.objects.select_related('customer__profile', 'service__provider__profile'),
        pk=pk
    )
    if request.user != service_request.customer and request.user != service_request.service.provider:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    text = request.POST.get('message', '').strip()
    if not text:
        return JsonResponse({'success': False, 'error': 'Message cannot be empty.'}, status=400)

    msg = BookingMessage.objects.create(
        service_request=service_request,
        sender=request.user,
        message=text
    )

    is_customer = (request.user == service_request.customer)
    recipient = service_request.service.provider if is_customer else service_request.customer
    sender_name = request.user.profile.get_display_name() if hasattr(request.user, 'profile') else request.user.username

    try:
        send_notification(
            user=recipient,
            title=f"New message from {sender_name}",
            message=f"Request #{service_request.pk}: {text[:80]}",
            target_url=reverse('bookings:request_detail', args=[service_request.pk]),
            notification_type=Notification.TYPE_CHAT_MESSAGE
        )
    except Exception:
        pass

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
        return JsonResponse({
            'success': True,
            'id': msg.id,
            'sender_name': sender_name,
            'is_me': True,
            'message': msg.message,
            'created_at': timezone.localtime(msg.created_at).strftime('%d %b, %I:%M %p')
        })

    messages.success(request, "Message sent.")
    return redirect('bookings:request_detail', pk=pk)


@login_required
def get_booking_messages(request, pk):
    service_request = get_object_or_404(ServiceRequest, pk=pk)
    if request.user != service_request.customer and request.user != service_request.service.provider:
        return JsonResponse({'success': False, 'error': 'Unauthorized'}, status=403)

    msgs = service_request.messages.select_related('sender__profile').all()
    data = []
    for m in msgs:
        sender_name = m.sender.profile.get_display_name() if hasattr(m.sender, 'profile') else m.sender.username
        data.append({
            'id': m.id,
            'sender_id': m.sender_id,
            'sender_name': sender_name,
            'is_me': (m.sender_id == request.user.id),
            'message': m.message,
            'created_at': timezone.localtime(m.created_at).strftime('%d %b, %I:%M %p')
        })
    return JsonResponse({'success': True, 'messages': data})


@require_customer
@require_POST
def cancel_request(request, pk):
    service_request = get_object_or_404(ServiceRequest, pk=pk, customer=request.user)
    if service_request.can_be_cancelled:
        service_request.status = ServiceRequest.STATUS_CANCELLED
        service_request.save(update_fields=['status', 'updated_at'])

        # Notify provider
        try:
            send_notification(
                user=service_request.service.provider,
                title="Booking Cancelled ❌",
                message=f"{request.user.profile.get_display_name()} cancelled booking request #{service_request.pk}.",
                target_url=reverse('bookings:request_detail', args=[service_request.pk]),
                notification_type=Notification.TYPE_BOOKING_STATUS
            )
        except Exception:
            pass

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
