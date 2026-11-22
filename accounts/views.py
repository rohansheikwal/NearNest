from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.conf import settings
from django.http import HttpResponseRedirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib import messages
from django.contrib.auth.models import User
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from .forms import (
    CustomerRegistrationForm,
    ProviderRegistrationForm,
    CustomLoginForm,
    ProfileEditForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
)
from .models import Profile
from services.models import Service
from bookings.models import ServiceRequest


def register_customer(request):
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.is_customer:
        return redirect('core:home')
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            if hasattr(request, 'switch_portal'):
                request.switch_portal('customer')
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f"Welcome to Neighborly, {user.profile.get_display_name()}! Your customer account is ready.")
            return redirect('core:home')
    else:
        form = CustomerRegistrationForm()
    return render(request, 'accounts/register_customer.html', {'form': form, 'role': 'customer'})


def register_provider(request):
    if request.user.is_authenticated and hasattr(request.user, 'profile') and request.user.profile.is_provider:
        return redirect('services:provider_dashboard')
    if request.method == 'POST':
        form = ProviderRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            if hasattr(request, 'switch_portal'):
                request.switch_portal('provider')
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            messages.success(request, f"Welcome to Neighborly, {user.profile.get_display_name()}! Your provider account is ready. Start by creating your first service.")
            return redirect('services:provider_dashboard')
    else:
        form = ProviderRegistrationForm()
    return render(request, 'accounts/register_provider.html', {'form': form, 'role': 'provider'})


def user_login(request):
    current_portal = getattr(request, 'portal', 'customer')
    if request.user.is_authenticated:
        is_provider = hasattr(request.user, 'profile') and request.user.profile.is_provider
        if current_portal == 'provider' and is_provider:
            return redirect('services:provider_dashboard')
        elif current_portal == 'customer' and not is_provider:
            return redirect('core:home')

    if request.method == 'POST':
        form = CustomLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            target_portal = 'provider' if (hasattr(user, 'profile') and user.profile.is_provider) else 'customer'
            if hasattr(request, 'switch_portal'):
                request.switch_portal(target_portal)
            login(request, user)
            next_url = request.GET.get('next', '') or request.POST.get('next', '')
            if next_url and url_has_allowed_host_and_scheme(
                next_url,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_url)
            if target_portal == 'provider':
                return redirect('services:provider_dashboard')
            return redirect('core:home')
        else:
            messages.error(request, "Invalid username or password. Please try again.")
    else:
        form = CustomLoginForm()
    return render(request, 'accounts/login.html', {'form': form})


def user_logout(request):
    portal = request.GET.get('portal') or getattr(request, 'portal', 'customer')
    if hasattr(request, 'switch_portal'):
        request.switch_portal(portal)
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('core:home')


@login_required
def profile_view(request):
    profile = request.user.profile
    return render(request, 'accounts/profile.html', {'profile': profile})


@login_required
def profile_edit(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileEditForm(request.POST, request.FILES, instance=profile, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            portal_query = '?portal=provider' if request.portal == 'provider' else ''
            return redirect(f"{reverse('accounts:profile')}{portal_query}")
    else:
        form = ProfileEditForm(instance=profile, user=request.user)
    return render(request, 'accounts/profile_edit.html', {'form': form, 'profile': profile})


@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed successfully.")
            portal_query = '?portal=provider' if request.portal == 'provider' else ''
            return redirect(f"{reverse('accounts:profile')}{portal_query}")
    else:
        form = PasswordChangeForm(request.user)
    for field in form.fields.values():
        field.widget.attrs['class'] = 'form-control'
    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
def customer_dashboard(request):
    if not request.user.profile.is_customer:
        messages.error(request, "Access denied.")
        return redirect('core:home')
    requests_qs = ServiceRequest.objects.filter(customer=request.user).select_related(
        'service', 'service__provider', 'service__provider__profile'
    ).order_by('-created_at')
    from bookings.models import SavedService
    saved_services = SavedService.objects.filter(customer=request.user).select_related(
        'service', 'service__category', 'service__provider__profile'
    )
    context = {
        'all_requests': requests_qs,
        'pending_requests': requests_qs.filter(status=ServiceRequest.STATUS_PENDING),
        'accepted_requests': requests_qs.filter(status=ServiceRequest.STATUS_ACCEPTED),
        'inprogress_requests': requests_qs.filter(status=ServiceRequest.STATUS_INPROGRESS),
        'completed_requests': requests_qs.filter(status=ServiceRequest.STATUS_COMPLETED),
        'recent_requests': requests_qs[:5],
        'saved_services': saved_services,
        'total_requests': requests_qs.count(),
    }
    return render(request, 'dashboards/customer_dashboard.html', context)


def provider_public_profile(request, username):
    provider_user = get_object_or_404(User, username=username)
    if not hasattr(provider_user, 'profile') or not provider_user.profile.is_provider:
        from django.http import Http404
        raise Http404("Provider not found")
    profile = provider_user.profile
    services = Service.objects.filter(provider=provider_user, is_active=True).select_related('category')
    from reviews.models import Review
    from django.db.models import Avg, Count
    rating_data = Review.objects.filter(service_request__service__provider=provider_user).aggregate(
        avg=Avg('rating'), count=Count('id')
    )
    context = {
        'provider_profile': profile,
        'services': services,
        'avg_rating': rating_data['avg'],
        'review_count': rating_data['count'],
    }
    return render(request, 'accounts/provider_public_profile.html', context)


class CustomPasswordResetView(auth_views.PasswordResetView):
    form_class = CustomPasswordResetForm
    template_name = 'accounts/password_reset.html'
    email_template_name = 'accounts/password_reset_email.txt'
    subject_template_name = 'accounts/password_reset_subject.txt'
    success_url = reverse_lazy('accounts:password_reset_done')

    def form_valid(self, form):
        opts = {
            'use_https': self.request.is_secure(),
            'token_generator': self.token_generator,
            'from_email': self.from_email,
            'email_template_name': self.email_template_name,
            'subject_template_name': self.subject_template_name,
            'request': self.request,
            'html_email_template_name': self.html_email_template_name,
            'extra_email_context': self.extra_email_context,
            'domain_override': self.request.get_host(),
        }
        form.save(**opts)
        email = form.cleaned_data.get('email')
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user and settings.EMAIL_BACKEND.endswith('console.EmailBackend'):
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            self.request.session['dev_reset_url'] = reverse('accounts:password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
            self.request.session['dev_reset_email'] = email
        return HttpResponseRedirect(self.get_success_url())


class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'accounts/password_reset_done.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['dev_reset_url'] = self.request.session.pop('dev_reset_url', None)
        context['dev_reset_email'] = self.request.session.pop('dev_reset_email', None)
        context['is_console_backend'] = settings.EMAIL_BACKEND.endswith('console.EmailBackend')
        return context
