import logging
import secrets
from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.tokens import default_token_generator
from django.contrib import messages
from django.contrib.auth.models import User
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_encode
from django.utils.encoding import force_bytes
from .forms import (
    CustomerRegistrationForm,
    ProviderRegistrationForm,
    CustomLoginForm,
    ProfileEditForm,
    CustomPasswordResetForm,
    CustomSetPasswordForm,
    ForgotPasswordRequestForm,
    OTPVerificationForm,
    ResetPasswordConfirmForm,
)
from .models import Profile, PasswordResetOTP

logger = logging.getLogger(__name__)
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


def _mask_email(email):
    """Return masked email like ro***al@gmail.com for display."""
    if not email or '@' not in email:
        return email
    local, domain = email.split('@', 1)
    if len(local) <= 2:
        masked_local = local[0] + '*'
    elif len(local) <= 4:
        masked_local = local[0] + '*' * (len(local) - 2) + local[-1]
    else:
        masked_local = local[:2] + '*' * (len(local) - 4) + local[-2:]
    return f"{masked_local}@{domain}"


def _send_otp_email(user, email):
    """Generate 6-digit OTP, store hashed, and send NearNest branded email."""
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = timezone.now() + timedelta(minutes=PasswordResetOTP.EXPIRY_MINUTES)
    otp_hash = PasswordResetOTP.hash_otp(otp_code)

    # Invalidate previous unused OTPs for this email
    PasswordResetOTP.objects.filter(email__iexact=email, is_used=False).update(is_used=True)

    # Create new OTP record
    PasswordResetOTP.objects.create(
        user=user,
        email=email,
        otp_hash=otp_hash,
        expires_at=expires_at,
    )

    user_name = user.profile.get_display_name() if hasattr(user, 'profile') else (user.get_full_name() or user.username)
    context = {
        'user_name': user_name,
        'user_email': email,
        'otp': otp_code,
        'expires_time': expires_at.strftime('%I:%M %p'),
    }

    html_content = render_to_string('accounts/password_reset_otp_email.html', context)
    text_content = render_to_string('accounts/password_reset_otp_email.txt', context)

    subject = "Your NearNest Password Reset Verification Code"
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_content,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email],
    )
    msg.attach_alternative(html_content, "text/html")
    msg.send(fail_silently=False)
    return True


def password_reset_request(request):
    """Step 1: Enter email and send 6-digit OTP."""
    if request.user.is_authenticated:
        return redirect('core:home')

    if request.method == 'POST':
        form = ForgotPasswordRequestForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            user = User.objects.filter(email__iexact=email, is_active=True).first()

            # Check 60-second cooldown
            last_otp = PasswordResetOTP.objects.filter(email__iexact=email).order_by('-created_at').first()
            if last_otp:
                elapsed = (timezone.now() - last_otp.created_at).total_seconds()
                if elapsed < PasswordResetOTP.COOLDOWN_SECONDS:
                    remaining = int(PasswordResetOTP.COOLDOWN_SECONDS - elapsed)
                    messages.warning(request, f"Please wait {remaining} seconds before requesting a new OTP.")
                    request.session['reset_email'] = email
                    return redirect('accounts:password_reset_verify_otp')

            try:
                _send_otp_email(user, email)
                request.session['reset_email'] = email
                messages.success(request, f"A 6-digit verification code has been sent to {email}.")
                return redirect('accounts:password_reset_verify_otp')
            except Exception as ex:
                logger.error("Failed to send password reset OTP: %s", ex)
                messages.error(request, "Unable to send verification email. Please check your email configuration or try again later.")
    else:
        form = ForgotPasswordRequestForm()

    return render(request, 'accounts/password_reset.html', {'form': form})


def password_reset_verify_otp(request):
    """Step 2: Enter and verify 6-digit OTP."""
    if request.user.is_authenticated:
        return redirect('core:home')

    email = request.session.get('reset_email')
    if not email:
        messages.info(request, "Please enter your email to request an OTP.")
        return redirect('accounts:password_reset')

    otp_record = PasswordResetOTP.objects.filter(email__iexact=email).order_by('-created_at').first()
    if not otp_record:
        messages.error(request, "No active OTP request found. Please request a new code.")
        return redirect('accounts:password_reset')

    elapsed = (timezone.now() - otp_record.created_at).total_seconds()
    cooldown_remaining = max(0, int(PasswordResetOTP.COOLDOWN_SECONDS - elapsed))

    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            entered_otp = form.cleaned_data['otp']
            is_valid, error_msg = otp_record.verify_otp(entered_otp)
            if not is_valid:
                messages.error(request, error_msg)
            else:
                otp_record.is_used = True
                otp_record.reset_token = secrets.token_urlsafe(32)
                otp_record.token_expires_at = timezone.now() + timedelta(minutes=10)
                otp_record.save(update_fields=['is_used', 'reset_token', 'token_expires_at'])

                request.session['reset_token'] = otp_record.reset_token
                messages.success(request, "OTP verified successfully! Please enter your new password.")
                return redirect('accounts:password_reset_set_password')
    else:
        form = OTPVerificationForm()

    context = {
        'form': form,
        'email': email,
        'masked_email': _mask_email(email),
        'cooldown_remaining': cooldown_remaining,
    }
    return render(request, 'accounts/password_reset_verify_otp.html', context)


def password_reset_resend_otp(request):
    """Resend a new 6-digit OTP with 60-second cooldown."""
    if request.method != 'POST':
        return redirect('accounts:password_reset_verify_otp')

    email = request.session.get('reset_email')
    if not email:
        messages.error(request, "Session expired. Please enter your email again.")
        return redirect('accounts:password_reset')

    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if not user:
        messages.error(request, "Account not found. Please start over.")
        return redirect('accounts:password_reset')

    last_otp = PasswordResetOTP.objects.filter(email__iexact=email).order_by('-created_at').first()
    if last_otp:
        elapsed = (timezone.now() - last_otp.created_at).total_seconds()
        if elapsed < PasswordResetOTP.COOLDOWN_SECONDS:
            remaining = int(PasswordResetOTP.COOLDOWN_SECONDS - elapsed)
            messages.warning(request, f"Please wait {remaining} seconds before requesting a new code.")
            return redirect('accounts:password_reset_verify_otp')

    try:
        _send_otp_email(user, email)
        messages.success(request, "A new 6-digit verification code has been sent to your email.")
    except Exception as ex:
        logger.error("Failed to resend OTP: %s", ex)
        messages.error(request, "Failed to send verification code. Please try again later.")

    return redirect('accounts:password_reset_verify_otp')


def password_reset_set_password(request):
    """Step 3: Reset password with validation and show/hide functionality."""
    if request.user.is_authenticated:
        return redirect('core:home')

    reset_token = request.session.get('reset_token')
    if not reset_token:
        messages.error(request, "Unauthorized or expired reset session. Please request a new OTP.")
        return redirect('accounts:password_reset')

    otp_record = PasswordResetOTP.objects.filter(
        reset_token=reset_token,
        token_expires_at__gte=timezone.now(),
    ).select_related('user').first()

    if not otp_record or not otp_record.user.is_active:
        messages.error(request, "Password reset session has expired. Please verify your OTP again.")
        request.session.pop('reset_token', None)
        return redirect('accounts:password_reset')

    user = otp_record.user

    if request.method == 'POST':
        form = ResetPasswordConfirmForm(request.POST, user=user)
        if form.is_valid():
            form.save()

            # Invalidate reset token and clear reset session
            otp_record.reset_token = None
            otp_record.save(update_fields=['reset_token'])
            request.session.pop('reset_token', None)
            request.session.pop('reset_email', None)

            messages.success(request, "Your password has been changed successfully! You can now sign in.")
            return redirect('accounts:password_reset_done')
    else:
        form = ResetPasswordConfirmForm(user=user)

    return render(request, 'accounts/password_reset_confirm.html', {'form': form, 'user': user})


def password_reset_done(request):
    """Step 4: Password reset completed confirmation."""
    return render(request, 'accounts/password_reset_done.html')


# Legacy class-based views kept for backwards compatibility
class CustomPasswordResetView(auth_views.PasswordResetView):
    def dispatch(self, request, *args, **kwargs):
        return redirect('accounts:password_reset')


class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    def dispatch(self, request, *args, **kwargs):
        return redirect('accounts:password_reset_done')
