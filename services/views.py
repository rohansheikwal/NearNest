from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import redirect_to_login
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Avg, Count, Q
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from .models import Service, ServiceCategory
from .forms import ServiceForm, ServiceSearchForm
from accounts.models import Profile


def _deduplicate_services(services):
    """Keep one newest listing for each real provider/category identity."""
    selected = []
    seen = set()
    for service in services:
        key = (service.provider_id, service.category_id)
        if key in seen:
            continue
        seen.add(key)
        selected.append(service)
    return selected


def service_list(request):
    """Explore Services page with search, filter, sort, and pagination."""
    form = ServiceSearchForm(request.GET or None)
    services = Service.objects.filter(is_active=True).select_related(
        'provider', 'provider__profile', 'category'
    )

    q = request.GET.get('q', '').strip()
    category_id = request.GET.get('category', '')
    city = request.GET.get('city', '').strip()
    area = request.GET.get('area', '').strip()
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    sort = request.GET.get('sort', 'newest')

    if q:
        services = services.filter(
            Q(title__icontains=q) | Q(description__icontains=q) |
            Q(category__name__icontains=q) | Q(provider__profile__full_name__icontains=q)
        )
    if category_id:
        try:
            services = services.filter(category_id=int(category_id))
        except (ValueError, TypeError):
            pass
    if city:
        services = services.filter(city__icontains=city)
    if area:
        services = services.filter(area__icontains=area)
    if min_price:
        try:
            services = services.filter(price__gte=float(min_price))
        except ValueError:
            pass
    if max_price:
        try:
            services = services.filter(price__lte=float(max_price))
        except ValueError:
            pass

    if sort == 'rating':
        services = services.annotate(avg_r=Avg('servicerequest__review__rating'))
    services = services.order_by('-updated_at', '-created_at', '-id')
    services = _deduplicate_services(services)
    if sort == 'price_asc':
        services.sort(key=lambda service: service.price)
    elif sort == 'price_desc':
        services.sort(key=lambda service: service.price, reverse=True)
    elif sort == 'rating':
        services.sort(key=lambda service: service.avg_r or 0, reverse=True)
    paginator = Paginator(services, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    pagination_params = request.GET.copy()
    pagination_params.pop('page', None)

    categories = ServiceCategory.objects.filter(is_active=True)
    has_filters = any([q, category_id, city, area, min_price, max_price])

    # Saved services for the current user
    saved_ids = set()
    if request.user.is_authenticated and request.user.profile.is_customer:
        from bookings.models import SavedService
        saved_ids = set(SavedService.objects.filter(customer=request.user).values_list('service_id', flat=True))

    context = {
        'page_obj': page_obj,
        'form': form,
        'categories': categories,
        'has_filters': has_filters,
        'total_count': len(services) if has_filters else None,
        'saved_ids': saved_ids,
        'current_q': q,
        'current_sort': sort,
        'pagination_query': pagination_params.urlencode(),
    }
    return render(request, 'services/service_list.html', context)


def service_detail(request, pk):
    service = get_object_or_404(Service, pk=pk, is_active=True)
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    from reviews.models import Review
    reviews = Review.objects.filter(service_request__service=service).select_related(
        'service_request__customer__profile'
    ).order_by('-created_at')
    avg_rating = reviews.aggregate(avg=Avg('rating'))['avg']
    related = Service.objects.filter(
        category=service.category, is_active=True
    ).exclude(pk=pk)[:4]

    is_saved = False
    can_review = False
    reviewable_request_pk = None
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.is_customer:
        from bookings.models import SavedService, ServiceRequest
        is_saved = SavedService.objects.filter(customer=request.user, service=service).exists()
        reviewable_qs = ServiceRequest.objects.filter(
            customer=request.user, service=service,
            status=ServiceRequest.STATUS_COMPLETED
        ).exclude(review__isnull=False)
        can_review = reviewable_qs.exists()
        if can_review:
            reviewable_request_pk = reviewable_qs.first().pk

    context = {
        'service': service,
        'reviews': reviews,
        'avg_rating': avg_rating,
        'review_count': reviews.count(),
        'related_services': related,
        'is_saved': is_saved,
        'can_review': can_review,
        'reviewable_request_pk': reviewable_request_pk,
    }
    return render(request, 'services/service_detail.html', context)


def category_view(request, slug):
    category = get_object_or_404(ServiceCategory, slug=slug, is_active=True)
    services = Service.objects.filter(category=category, is_active=True).select_related(
        'provider', 'provider__profile'
    ).order_by('-created_at')
    paginator = Paginator(services, 12)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'services/category.html', {
        'category': category,
        'page_obj': page_obj,
    })


# ==================== PROVIDER VIEWS ====================

def require_provider(view_func):
    """Decorator to require provider role."""
    @login_required
    def wrapper(request, *args, **kwargs):
        if not hasattr(request.user, 'profile') or not request.user.profile.is_provider:
            messages.error(request, "This section is for service providers only.")
            return redirect('core:home')
        return view_func(request, *args, **kwargs)
    return wrapper


@require_provider
def provider_dashboard(request):
    from bookings.models import ServiceRequest
    from reviews.models import Review
    from django.db.models import Avg

    my_services = Service.objects.filter(provider=request.user).order_by('-created_at')
    my_service_ids = my_services.values_list('id', flat=True)
    all_requests = ServiceRequest.objects.filter(service__in=my_service_ids).select_related(
        'customer__profile', 'service'
    ).order_by('-created_at')
    rating_data = Review.objects.filter(service_request__service__in=my_service_ids).aggregate(
        avg=Avg('rating'), count=Count('id')
    )
    context = {
        'my_services': my_services,
        'all_requests': all_requests,
        'pending_requests': all_requests.filter(status=ServiceRequest.STATUS_PENDING),
        'accepted_requests': all_requests.filter(status=ServiceRequest.STATUS_ACCEPTED),
        'inprogress_requests': all_requests.filter(status=ServiceRequest.STATUS_INPROGRESS),
        'completed_requests': all_requests.filter(status=ServiceRequest.STATUS_COMPLETED),
        'recent_requests': all_requests[:5],
        'avg_rating': rating_data['avg'],
        'review_count': rating_data['count'],
        'active_services_count': my_services.filter(is_active=True).count(),
        'total_services_count': my_services.count(),
    }
    return render(request, 'dashboards/provider_dashboard.html', context)


@require_provider
def service_create(request):
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES)
        if form.is_valid():
            service = form.save(commit=False)
            service.provider = request.user
            service.save()
            messages.success(request, f'Service "{service.title}" created successfully!')
            return redirect('services:provider_dashboard')
    else:
        form = ServiceForm()
        # Pre-fill city/area from provider profile
        profile = request.user.profile
        form.initial = {'city': profile.city, 'area': profile.area}
    return render(request, 'services/service_form.html', {'form': form, 'action': 'Create'})


@require_provider
def service_edit(request, pk):
    service = get_object_or_404(Service, pk=pk, provider=request.user)
    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            form.save()
            messages.success(request, f'Service "{service.title}" updated successfully!')
            return redirect('services:provider_dashboard')
    else:
        form = ServiceForm(instance=service)
    return render(request, 'services/service_form.html', {'form': form, 'service': service, 'action': 'Edit'})


@require_provider
def service_delete(request, pk):
    service = get_object_or_404(Service, pk=pk, provider=request.user)
    if request.method == 'POST':
        title = service.title
        service.delete()
        messages.success(request, f'Service "{title}" has been deleted.')
        return redirect('services:provider_dashboard')
    return render(request, 'services/service_confirm_delete.html', {'service': service})


@require_provider
def provider_requests(request):
    from bookings.models import ServiceRequest
    my_service_ids = Service.objects.filter(provider=request.user).values_list('id', flat=True)
    base_requests = ServiceRequest.objects.filter(service__in=my_service_ids).select_related(
        'customer__profile', 'service'
    ).order_by('-created_at')

    total_count = base_requests.count()

    # Pre-calculate counts for all statuses
    status_counts = {
        'pending': base_requests.filter(status=ServiceRequest.STATUS_PENDING).count(),
        'accepted': base_requests.filter(status=ServiceRequest.STATUS_ACCEPTED).count(),
        'inprogress': base_requests.filter(status=ServiceRequest.STATUS_INPROGRESS).count(),
        'completed': base_requests.filter(status=ServiceRequest.STATUS_COMPLETED).count(),
        'rejected': base_requests.filter(status=ServiceRequest.STATUS_REJECTED).count(),
        'cancelled': base_requests.filter(status=ServiceRequest.STATUS_CANCELLED).count(),
    }

    status_filter = request.GET.get('status', '').strip().lower()
    if status_filter and status_filter in status_counts:
        filtered_requests = base_requests.filter(status=status_filter)
    else:
        status_filter = ''
        filtered_requests = base_requests

    # Build structured tabs with accurate counts
    tabs = [
        {
            'val': '',
            'label': 'All',
            'count': total_count,
            'is_active': not status_filter,
        }
    ]
    for val, label in ServiceRequest.STATUS_CHOICES:
        tabs.append({
            'val': val,
            'label': label,
            'count': status_counts.get(val, 0),
            'is_active': status_filter == val,
        })

    context = {
        'all_requests': filtered_requests,
        'total_count': total_count,
        'status_filter': status_filter,
        'status_counts': status_counts,
        'tabs': tabs,
    }
    return render(request, 'services/provider_requests.html', context)


@require_provider
@require_POST
def update_request_status(request, request_id):
    from bookings.models import ServiceRequest
    my_service_ids = Service.objects.filter(provider=request.user).values_list('id', flat=True)
    service_request = get_object_or_404(ServiceRequest, pk=request_id, service__in=my_service_ids)
    new_status = request.POST.get('status')
    valid_transitions = {
        ServiceRequest.STATUS_PENDING: [ServiceRequest.STATUS_ACCEPTED, ServiceRequest.STATUS_REJECTED],
        ServiceRequest.STATUS_ACCEPTED: [ServiceRequest.STATUS_INPROGRESS],
        ServiceRequest.STATUS_INPROGRESS: [ServiceRequest.STATUS_COMPLETED],
    }
    current = service_request.status
    if new_status in valid_transitions.get(current, []):
        service_request.status = new_status
        provider_response = request.POST.get('provider_response')
        if provider_response is not None:
            service_request.provider_response = provider_response.strip()
        service_request.save(update_fields=['status', 'provider_response', 'updated_at'])
        messages.success(request, f'Request status updated to {service_request.get_status_display()}.')
    else:
        messages.error(request, "Invalid status transition.")
    return redirect(request.POST.get('next', 'services:provider_requests'))


@require_provider
def provider_reviews(request):
    from reviews.models import Review
    from django.db.models import Avg
    my_service_ids = Service.objects.filter(provider=request.user).values_list('id', flat=True)
    reviews = Review.objects.filter(service_request__service__in=my_service_ids).select_related(
        'service_request__customer__profile', 'service_request__service'
    ).order_by('-created_at')
    avg = reviews.aggregate(avg=Avg('rating'))['avg']
    return render(request, 'services/provider_reviews.html', {
        'reviews': reviews,
        'avg_rating': avg,
    })


@require_provider
def toggle_service_active(request, pk):
    if request.method == 'POST':
        service = get_object_or_404(Service, pk=pk, provider=request.user)
        service.is_active = not service.is_active
        service.save()
        status = 'activated' if service.is_active else 'deactivated'
        messages.success(request, f'Service "{service.title}" has been {status}.')
    return redirect('services:provider_dashboard')
