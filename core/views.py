from datetime import timedelta
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.mail import EmailMessage
from django.conf import settings
from django.utils import timezone
from django.db.models import Count, Q
from services.models import Service, ServiceCategory
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from .models import ContactMessage, Notification, send_notification
from .forms import ContactForm

logger = logging.getLogger(__name__)


def _one_service_per_provider_category(services, limit=None):
    """Keep the newest complete active listing for each provider/category pair."""
    selected = []
    seen = set()
    for service in services:
        key = (service.provider_id, service.category_id)
        if key in seen:
            continue
        seen.add(key)
        selected.append(service)
        if limit and len(selected) >= limit:
            break
    return selected


def home(request):
    featured_queryset = Service.objects.filter(is_active=True, is_featured=True).select_related(
        'provider__profile', 'category'
    ).order_by('-updated_at', '-created_at', '-id')
    recent_queryset = Service.objects.filter(is_active=True).select_related(
        'provider__profile', 'category'
    ).order_by('-created_at')[:8]
    featured_services = _one_service_per_provider_category(featured_queryset, limit=6)
    recent_services = _one_service_per_provider_category(recent_queryset, limit=8)
    categories = ServiceCategory.objects.filter(is_active=True).annotate(
        active_service_count=Count('services', filter=Q(services__is_active=True))
    ).order_by('order')[:10]

    # Handle homepage search form redirect
    if request.GET.get('q') or request.GET.get('city'):
        q = request.GET.get('q', '')
        city = request.GET.get('city', '')
        params = []
        if q:
            params.append(f'q={q}')
        if city:
            params.append(f'city={city}')
        return redirect(f'/services/?{"&".join(params)}')

    saved_ids = set()
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.is_customer:
        from bookings.models import SavedService
        saved_ids = set(SavedService.objects.filter(customer=request.user).values_list('service_id', flat=True))

    context = {
        'featured_services': featured_services,
        'recent_services': recent_services,
        'categories': categories,
        'has_featured': bool(featured_services),
        'has_recent': bool(recent_services),
        'saved_ids': saved_ids,
    }
    return render(request, 'core/home.html', context)


def about(request):
    return render(request, 'core/about.html')


def how_it_works(request):
    return render(request, 'core/how_it_works.html')


def become_provider(request):
    return render(request, 'core/become_provider.html')


def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']

            # Prevent duplicate submissions (same email, subject, message within 2 minutes)
            two_mins_ago = timezone.now() - timedelta(minutes=2)
            if ContactMessage.objects.filter(
                email__iexact=email,
                subject__iexact=subject,
                message__iexact=message,
                created_at__gte=two_mins_ago
            ).exists():
                messages.warning(
                    request,
                    "You have already submitted this exact message recently. Please wait a moment before sending again."
                )
                return redirect('core:contact')

            # Determine recipient admin email from configuration
            admin_email = (
                getattr(settings, 'ADMIN_EMAIL', None)
                or getattr(settings, 'CONTACT_NOTIFICATION_EMAIL', None)
                or getattr(settings, 'EMAIL_HOST_USER', None)
                or 'admin@localhost'
            )

            email_subject = f"[NearNest Contact] {subject}"
            email_body = (
                f"You have received a new message from the NearNest Contact Form.\n\n"
                f"--------------------------------------------------\n"
                f"Sender Details:\n"
                f"--------------------------------------------------\n"
                f"Name:    {name}\n"
                f"Email:   {email}\n"
                f"Subject: {subject}\n\n"
                f"--------------------------------------------------\n"
                f"Message:\n"
                f"--------------------------------------------------\n"
                f"{message}\n\n"
                f"--------------------------------------------------\n"
                f"This message was sent via NearNest Contact Us form.\n"
                f"You can reply directly to this email to respond to {name}."
            )

            try:
                email_msg = EmailMessage(
                    subject=email_subject,
                    body=email_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    to=[admin_email],
                    reply_to=[email],
                )
                email_msg.send(fail_silently=False)

                # Persist message to database
                form.save()

                messages.success(
                    request,
                    "Thank you! Your message has been sent successfully. We will get back to you soon."
                )
            except Exception as ex:
                logger.error("Failed to send contact notification email: %s", ex)
                messages.error(
                    request,
                    "Sorry, an error occurred while delivering your message. Please check your email configuration or try again later."
                )

            return redirect('core:contact')
    else:
        form = ContactForm()
        if request.user.is_authenticated:
            profile = request.user.profile
            form.initial = {
                'name': profile.get_display_name(),
                'email': request.user.email,
            }
    return render(request, 'core/contact.html', {'form': form})


def faq(request):
    return render(request, 'core/faq.html')


def privacy_policy(request):
    return render(request, 'core/privacy_policy.html')


def terms_of_service(request):
    return render(request, 'core/terms_of_service.html')


@login_required
def notifications_list(request):
    notifications = request.user.notifications.all()
    paginator = Paginator(notifications, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'core/notifications.html', {
        'page_obj': page_obj,
        'unread_count': request.user.notifications.filter(is_read=False).count(),
    })


@login_required
def mark_notification_read(request, pk):
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
        return JsonResponse({'success': True, 'unread_count': request.user.notifications.filter(is_read=False).count()})

    if notification.target_url:
        return redirect(notification.target_url)
    return redirect('core:notifications_list')


@login_required
def mark_all_notifications_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.headers.get('Accept') == 'application/json':
        return JsonResponse({'success': True, 'unread_count': 0})
    messages.success(request, "All notifications marked as read.")
    return redirect('core:notifications_list')


@login_required
def notifications_api(request):
    notifications = request.user.notifications.all()[:8]
    data = []
    for n in notifications:
        data.append({
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'target_url': n.target_url,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%d %b, %I:%M %p'),
        })
    return JsonResponse({
        'unread_count': request.user.notifications.filter(is_read=False).count(),
        'notifications': data,
    })


def error_403(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def error_404(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    return render(request, 'errors/500.html', status=500)
