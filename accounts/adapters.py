from django.contrib.auth import get_user_model

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.http import HttpResponseBadRequest


class SecureSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Link a Google identity to one existing, verified email account only."""

    def get_app(self, request, provider, client_id=None):
        apps = self.list_apps(request, provider=provider, client_id=client_id)
        if not apps:
            from allauth.socialaccount.models import SocialApp
            import os
            cid = os.environ.get('GOOGLE_CLIENT_ID', '').strip() or 'google-client-id'
            sec = os.environ.get('GOOGLE_CLIENT_SECRET', '').strip() or 'google-client-secret'
            return SocialApp(provider=provider, name='Google', client_id=cid, secret=sec)

        # If both database and settings apps exist (or duplicate), avoid MultipleObjectsReturned crash.
        # Prefer the app with a real configured client_id.
        valid_apps = [
            a for a in apps
            if getattr(a, 'client_id', '') and a.client_id not in {
                'your-google-client-id-here', 'placeholder', 'google-client-id'
            }
        ]
        if valid_apps:
            return valid_apps[0]
        return apps[0]

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return

        email = sociallogin.user.email
        email_verified = sociallogin.account.extra_data.get('email_verified', False)
        if not email or not email_verified:
            return

        users = get_user_model().objects.filter(email__iexact=email)
        if users.count() > 1:
            raise ImmediateHttpResponse(
                HttpResponseBadRequest(
                    'This email is associated with multiple accounts. '
                    'Sign in with your existing account instead.'
                )
            )

        user = users.first()
        if user:
            sociallogin.connect(request, user)

    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        extra_data = getattr(sociallogin.account, 'extra_data', {}) or {}
        full_name = extra_data.get('name') or f"{extra_data.get('given_name', '')} {extra_data.get('family_name', '')}".strip()
        if hasattr(user, 'profile'):
            if full_name and not user.profile.full_name:
                user.profile.full_name = full_name
            # If signing up from provider registration route
            if request and ('/register/provider/' in getattr(request, 'path', '') or getattr(request, 'GET', {}).get('portal') == 'provider'):
                user.profile.role = 'provider'
            user.profile.save()
        return user
