import time
from urllib.parse import parse_qs, urlsplit

from django.conf import settings
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.exceptions import SessionInterrupted
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date


class PortalSessionMiddleware(SessionMiddleware):
    """Keep customer and provider/admin authentication in separate sessions."""

    def _portal_for_request(self, request):
        path = request.path

        # 1. Path prefixes for strictly role-specific routes (Absolute priority)
        # Dedicated provider paths can NEVER be customer portal
        if path.startswith(('/services/provider/', '/admin/', '/accounts/register/provider/')):
            return 'provider'

        # Dedicated customer paths can NEVER be provider portal
        if path.startswith(('/accounts/register/customer/', '/accounts/dashboard/')):
            return 'customer'

        if path.startswith('/bookings/'):
            # /bookings/request/<pk>/detail/ is shared between customer and provider
            if '/detail/' in path:
                if request.GET.get('portal') == 'provider':
                    return 'provider'
                if 'nearnest_provider_sessionid' in request.COOKIES and 'nearnest_customer_sessionid' not in request.COOKIES:
                    return 'provider'
                return 'customer'
            # All other /bookings/ routes (including requesting a service, my requests, saved) are customer-only
            return 'customer'

        # 2. Social / OAuth routes: Guarantee session consistency between login initiation & callback
        if path.startswith(('/accounts/google/', '/accounts/social/')):
            state_id = request.GET.get('state')
            if state_id:
                for p_name, cookie_name in settings.PORTAL_SESSION_COOKIE_NAMES.items():
                    s_key = request.COOKIES.get(cookie_name)
                    if s_key:
                        s = self.SessionStore(s_key)
                        states = s.get('socialaccount_states', {})
                        if isinstance(states, dict) and state_id in states:
                            return p_name
            if request.GET.get('portal') == 'provider':
                return 'provider'
            return 'customer'

        # 3. Host / Subdomain check (e.g. provider.localhost, customer.localhost)
        host = request.get_host().split(':')[0].lower()
        if host.startswith('provider.'):
            return 'provider'
        if host.startswith('customer.'):
            return 'customer'

        # 3. Custom header from frontend (per-tab sessionStorage or AJAX)
        header_portal = request.headers.get('X-NearNest-Portal') or request.META.get('HTTP_X_NEARNST_PORTAL')
        if header_portal in settings.PORTAL_SESSION_COOKIE_NAMES:
            return header_portal

        # 4. Explicit query parameter or POST parameter
        portal = request.GET.get('portal') or request.POST.get('portal')
        if portal in settings.PORTAL_SESSION_COOKIE_NAMES:
            return portal

        # 5. Check 'next' parameter if present
        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url:
            next_path = urlsplit(next_url).path
            if next_path.startswith(('/services/provider/', '/admin/', '/accounts/register/provider/')):
                return 'provider'
            if next_path.startswith(('/accounts/register/customer/', '/accounts/dashboard/', '/bookings/')):
                return 'customer'
            next_portal = parse_qs(urlsplit(next_url).query).get('portal', [None])[0]
            if next_portal in settings.PORTAL_SESSION_COOKIE_NAMES:
                return next_portal

        # 6. Password reset routes
        if path.startswith('/accounts/password-reset/'):
            if 'nearnest_provider_sessionid' in request.COOKIES and 'nearnest_customer_sessionid' not in request.COOKIES:
                return 'provider'
            return 'customer'

        # 7. Referer check (for internal link clicks from within a portal)
        # NOTE: Ignore referers from /accounts/ (e.g. login/logout redirects) to avoid leaking stale portal state!
        referer = request.META.get('HTTP_REFERER')
        if referer:
            ref_parsed = urlsplit(referer)
            if not ref_parsed.path.startswith('/accounts/'):
                ref_host = ref_parsed.netloc.split(':')[0].lower()
                if ref_host.startswith('provider.'):
                    return 'provider'
                if ref_host.startswith('customer.'):
                    return 'customer'
                if ref_parsed.path.startswith(('/services/provider/', '/admin/')):
                    return 'provider'
                if ref_parsed.path.startswith(('/bookings/',)):
                    return 'customer'
                ref_portal = parse_qs(ref_parsed.query).get('portal', [None])[0]
                if ref_portal in settings.PORTAL_SESSION_COOKIE_NAMES:
                    return ref_portal

        # 8. Smart cookie fallback for public/shared routes
        if 'nearnest_provider_sessionid' in request.COOKIES and 'nearnest_customer_sessionid' not in request.COOKIES:
            return 'provider'

        return 'customer'

    def switch_portal(self, request, target_portal):
        """Allow views (e.g. login) to switch the active portal session dynamically."""
        if target_portal in settings.PORTAL_SESSION_COOKIE_NAMES:
            request.portal = target_portal
            request.portal_cookie_name = settings.PORTAL_SESSION_COOKIE_NAMES[target_portal]
            cookie_name = request.portal_cookie_name
            session_key = request.COOKIES.get(cookie_name)
            request.session = self.SessionStore(session_key)

    def process_request(self, request):
        request.portal = self._portal_for_request(request)
        request.portal_cookie_name = settings.PORTAL_SESSION_COOKIE_NAMES[request.portal]
        request.switch_portal = lambda target: self.switch_portal(request, target)
        cookie_name = request.portal_cookie_name
        session_key = request.COOKIES.get(cookie_name)

        # Allow existing users to transition from the old shared session cookie.
        if not session_key and not any(
            name in request.COOKIES
            for name in settings.PORTAL_SESSION_COOKIE_NAMES.values()
        ):
            session_key = request.COOKIES.get(settings.SESSION_COOKIE_NAME)
            request.using_legacy_session_cookie = bool(session_key)
        else:
            request.using_legacy_session_cookie = False

        session = self.SessionStore(session_key)

        # Smart preservation: If the chosen portal session cookie is empty or has no logged-in user,
        # but the alternate portal cookie has an authenticated user session, load that session!
        # Do not override on auth pages (login/register) or when portal was explicitly requested in URL/POST.
        is_auth_page = request.path.startswith(('/accounts/login/', '/accounts/register/'))
        has_explicit_portal = bool(request.GET.get('portal') or request.POST.get('portal'))

        if not is_auth_page and not has_explicit_portal and not session.get('_auth_user_id'):
            alt_portal = 'provider' if request.portal == 'customer' else 'customer'
            alt_cookie = settings.PORTAL_SESSION_COOKIE_NAMES[alt_portal]
            alt_key = request.COOKIES.get(alt_cookie)
            if alt_key:
                alt_session = self.SessionStore(alt_key)
                if alt_session.get('_auth_user_id'):
                    request.portal = alt_portal
                    request.portal_cookie_name = alt_cookie
                    session = alt_session

        request.session = session

    def process_response(self, request, response):
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response

        cookie_name = getattr(
            request,
            'portal_cookie_name',
            settings.PORTAL_SESSION_COOKIE_NAMES['customer'],
        )
        if cookie_name in request.COOKIES and empty:
            response.delete_cookie(
                cookie_name,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            need_vary_cookie = True
        else:
            need_vary_cookie = accessed
            if (modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty:
                if request.session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = request.session.get_expiry_age()
                    expires = http_date(time.time() + max_age)
                if response.status_code < 500:
                    try:
                        request.session.save()
                    except UpdateError:
                        raise SessionInterrupted(
                            'The request session was deleted before it completed.'
                        )
                    response.set_cookie(
                        cookie_name,
                        request.session.session_key,
                        max_age=max_age,
                        expires=expires,
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path=settings.SESSION_COOKIE_PATH,
                        secure=settings.SESSION_COOKIE_SECURE or None,
                        httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                    )
                    # Keep Django's conventional cookie synchronized for
                    # clients/tests that inspect it directly. It is ignored
                    # once either portal cookie exists.
                    response.set_cookie(
                        settings.SESSION_COOKIE_NAME,
                        request.session.session_key,
                        max_age=max_age,
                        expires=expires,
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path=settings.SESSION_COOKIE_PATH,
                        secure=settings.SESSION_COOKIE_SECURE or None,
                        httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                    )
                    need_vary_cookie = True
        if need_vary_cookie:
            patch_vary_headers(response, ('Cookie',))
        response['X-NearNest-Portal'] = getattr(request, 'portal', 'customer')
        return response
