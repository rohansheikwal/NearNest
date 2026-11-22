from django.contrib.auth import get_user_model

from allauth.core.exceptions import ImmediateHttpResponse
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.http import HttpResponseBadRequest


class SecureSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Link a Google identity to one existing, verified email account only."""

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
