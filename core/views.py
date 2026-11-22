from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Count, Q
from services.models import Service, ServiceCategory
from .models import ContactMessage
from .forms import ContactForm


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
            form.save()
            messages.success(request, "Thank you! Your message has been received. We'll review it shortly.")
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


def error_403(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def error_404(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def error_500(request):
    return render(request, 'errors/500.html', status=500)
