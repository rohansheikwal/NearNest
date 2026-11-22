from django.test import TestCase

from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse

from .models import Profile


class AuthenticationAndProfileTests(TestCase):
    def test_customer_and_provider_sessions_are_independent(self):
        customer = User.objects.create_user(
            username='sessioncustomer',
            password='StrongPass123!',
        )
        provider = User.objects.create_user(
            username='sessionprovider',
            password='StrongPass123!',
        )
        provider.profile.role = Profile.ROLE_PROVIDER
        provider.profile.save()

        customer_client = self.client
        provider_client = self.client.__class__()

        customer_client.post(
            reverse('accounts:login') + '?portal=customer',
            {'username': customer.username, 'password': 'StrongPass123!'},
        )
        provider_client.post(
            reverse('accounts:login') + '?portal=provider',
            {'username': provider.username, 'password': 'StrongPass123!'},
        )

        self.assertEqual(
            customer_client.get(reverse('accounts:customer_dashboard')).status_code,
            200,
        )
        self.assertEqual(
            provider_client.get(reverse('services:provider_dashboard')).status_code,
            200,
        )

        provider_client.get(reverse('accounts:logout') + '?portal=provider')
        self.assertEqual(
            customer_client.get(reverse('accounts:customer_dashboard')).status_code,
            200,
        )
        self.assertNotEqual(
            provider_client.get(reverse('services:provider_dashboard')).status_code,
            200,
        )

    def test_single_browser_simultaneous_portal_sessions_and_tab_isolation(self):
        """Simulate two Chrome tabs in the same browser sharing cookie jar."""
        provider = User.objects.create_user(
            username='mohit_provider',
            password='StrongPass123!',
        )
        provider.profile.role = Profile.ROLE_PROVIDER
        provider.profile.save()

        customer = User.objects.create_user(
            username='rohit_customer',
            password='StrongPass123!',
        )
        customer.profile.role = Profile.ROLE_CUSTOMER
        customer.profile.save()

        browser = self.client

        # 1. Login as Service Provider in Tab 1
        resp_prov = browser.post(
            reverse('accounts:login'),
            {'username': 'mohit_provider', 'password': 'StrongPass123!'},
        )
        self.assertRedirects(resp_prov, reverse('services:provider_dashboard'))
        self.assertIn('nearnest_provider_sessionid', browser.cookies)

        # 2. Login as Customer in Tab 2 (same browser / cookie jar)
        resp_cust = browser.post(
            reverse('accounts:login') + '?portal=customer',
            {'username': 'rohit_customer', 'password': 'StrongPass123!'},
        )
        self.assertRedirects(resp_cust, reverse('core:home'))
        self.assertIn('nearnest_customer_sessionid', browser.cookies)

        # Both portal cookies exist simultaneously in the browser!
        self.assertTrue(browser.cookies['nearnest_provider_sessionid'].value)
        self.assertTrue(browser.cookies['nearnest_customer_sessionid'].value)

        # 3. Refresh both tabs
        resp_refresh_prov = browser.get(reverse('services:provider_dashboard'))
        self.assertEqual(resp_refresh_prov.status_code, 200)
        self.assertEqual(resp_refresh_prov.context['user'].username, 'mohit_provider')

        resp_refresh_cust = browser.get(reverse('accounts:customer_dashboard'))
        self.assertEqual(resp_refresh_cust.status_code, 200)
        self.assertEqual(resp_refresh_cust.context['user'].username, 'rohit_customer')

        # 4. Navigate through both dashboards
        resp_prov_reqs = browser.get(reverse('services:provider_requests'))
        self.assertEqual(resp_prov_reqs.status_code, 200)

        resp_cust_reqs = browser.get(reverse('bookings:my_requests'))
        self.assertEqual(resp_cust_reqs.status_code, 200)

        # 5. Logout from Tab 2 (Customer) and verify Tab 1 (Provider) remains logged in
        browser.get(reverse('accounts:logout') + '?portal=customer')
        self.assertNotEqual(browser.get(reverse('accounts:customer_dashboard')).status_code, 200)

        resp_prov_after_logout = browser.get(reverse('services:provider_dashboard'))
        self.assertEqual(resp_prov_after_logout.status_code, 200)
        self.assertEqual(resp_prov_after_logout.context['user'].username, 'mohit_provider')

        # 6. Verify customers cannot access Service Provider-only pages
        cust_browser = self.client.__class__()
        cust_browser.post(
            reverse('accounts:login'),
            {'username': 'rohit_customer', 'password': 'StrongPass123!'},
        )
        # Attempting to access provider dashboard as customer must be denied/redirected
        denied_resp = cust_browser.get(reverse('services:provider_dashboard'), follow=True)
        self.assertNotEqual(denied_resp.resolver_match.url_name, 'provider_dashboard')

        # 7. Verify Subdomain Host-based portal routing works
        sub_prov = browser.get(reverse('services:provider_dashboard'), HTTP_HOST='provider.localhost:8000')
        self.assertEqual(sub_prov.status_code, 200)

    def test_user_creation_creates_customer_profile_without_admin_flags(self):
        user = User.objects.create_user(
            username='customer',
            email='customer@example.com',
            password='StrongPass123!',
        )

        self.assertTrue(user.profile.is_customer)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.check_password('StrongPass123!'))
        self.assertNotEqual(user.password, 'StrongPass123!')

    def test_customer_registration_assigns_customer_role_and_logs_in(self):
        response = self.client.post(reverse('accounts:register_customer'), {
            'username': 'newcustomer',
            'email': 'customer@example.com',
            'full_name': 'New Customer',
            'city': 'Bengaluru',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })

        self.assertRedirects(response, reverse('core:home'))
        user = User.objects.get(username='newcustomer')
        self.assertEqual(user.profile.role, Profile.ROLE_CUSTOMER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(self.client.session.get('_auth_user_id'))

    def test_provider_registration_assigns_provider_role_without_admin_flags(self):
        response = self.client.post(reverse('accounts:register_provider'), {
            'username': 'newprovider',
            'email': 'provider@example.com',
            'full_name': 'New Provider',
            'city': 'Bengaluru',
            'skills': 'Plumbing',
            'password1': 'StrongPass123!',
            'password2': 'StrongPass123!',
        })

        self.assertRedirects(response, reverse('services:provider_dashboard'))
        user = User.objects.get(username='newprovider')
        self.assertEqual(user.profile.role, Profile.ROLE_PROVIDER)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_login_accepts_registered_email_address(self):
        User.objects.create_user(
            username='emailuser',
            email='EmailUser@example.com',
            password='StrongPass123!',
        )

        response = self.client.post(reverse('accounts:login'), {
            'username': 'emailuser@example.com',
            'password': 'StrongPass123!',
        })

        self.assertRedirects(response, reverse('core:home'))

    def test_password_reset_flow_is_available(self):
        user = User.objects.create_user(
            username='resetuser',
            email='reset@example.com',
            password='OldStrongPass123!',
        )

        response = self.client.get(reverse('accounts:password_reset'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reset your password')

        response = self.client.post(reverse('accounts:password_reset'), {
            'email': user.email,
        })
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

        reset_url = next(
            line for line in mail.outbox[0].body.splitlines()
            if '/accounts/reset/' in line
        )
        response = self.client.get(reset_url.replace('http://testserver', ''))
        self.assertEqual(response.status_code, 302)

        response = self.client.post(response.url, {
            'new_password1': 'NewStrongPass123!',
            'new_password2': 'NewStrongPass123!',
        })
        self.assertRedirects(response, reverse('accounts:password_reset_complete'))
        self.assertTrue(self.client.login(
            username='resetuser',
            password='NewStrongPass123!',
        ))

    def test_password_reset_works_for_oauth_user_with_unusable_password(self):
        user = User.objects.create_user(
            username='oauthuser',
            email='oauthuser@example.com',
        )
        user.set_unusable_password()
        user.save()
        self.assertFalse(user.has_usable_password())

        response = self.client.post(reverse('accounts:password_reset'), {
            'email': user.email,
        })
        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)

        reset_url = next(
            line for line in mail.outbox[0].body.splitlines()
            if '/accounts/reset/' in line
        )
        confirm_resp = self.client.get(reset_url.replace('http://testserver', ''))
        self.assertEqual(confirm_resp.status_code, 302)

        set_resp = self.client.post(confirm_resp.url, {
            'new_password1': 'NewOAuthPass123!',
            'new_password2': 'NewOAuthPass123!',
        })
        self.assertRedirects(set_resp, reverse('accounts:password_reset_complete'))
        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertTrue(self.client.login(
            username='oauthuser',
            password='NewOAuthPass123!',
        ))

    def test_password_reset_does_not_reveal_unknown_email(self):
        response = self.client.post(reverse('accounts:password_reset'), {
            'email': 'unknown@example.com',
        })

        self.assertRedirects(response, reverse('accounts:password_reset_done'))
        self.assertEqual(len(mail.outbox), 0)
        self.assertContains(
            self.client.get(reverse('accounts:password_reset_done')),
            'If an account exists for that email address',
        )

    def test_password_reset_rejects_mismatched_new_passwords(self):
        user = User.objects.create_user(
            username='mismatchuser',
            email='mismatch@example.com',
            password='OldStrongPass123!',
        )
        self.client.post(reverse('accounts:password_reset'), {'email': user.email})
        reset_url = next(
            line for line in mail.outbox[0].body.splitlines()
            if '/accounts/reset/' in line
        ).replace('http://testserver', '')
        response = self.client.get(reset_url)

        response = self.client.post(response.url, {
            'new_password1': 'NewStrongPass123!',
            'new_password2': 'DifferentStrongPass123!',
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn('new_password2', response.context['form'].errors)
        self.assertTrue(self.client.login(
            username='mismatchuser',
            password='OldStrongPass123!',
        ))

    def test_profile_edit_does_not_allow_customer_to_set_provider_fields(self):
        user = User.objects.create_user(
            username='customer',
            email='customer@example.com',
            password='StrongPass123!',
        )
        self.client.login(username='customer', password='StrongPass123!')

        response = self.client.post(reverse('accounts:profile_edit'), {
            'full_name': 'Updated Customer',
            'email': 'customer@example.com',
            'skills': 'Attempted provider access',
        })

        self.assertRedirects(response, reverse('accounts:profile'))
        user.profile.refresh_from_db()
        self.assertEqual(user.profile.full_name, 'Updated Customer')
        self.assertEqual(user.profile.skills, '')
