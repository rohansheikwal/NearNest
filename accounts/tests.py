from datetime import timedelta
import re
from django.test import TestCase
from django.utils import timezone
from django.contrib.auth.models import User
from django.core import mail
from django.urls import reverse

from .models import Profile, PasswordResetOTP


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

    def test_otp_password_reset_full_flow(self):
        """Test complete 4-step OTP password reset flow."""
        user = User.objects.create_user(
            username='resetuser',
            email='reset@example.com',
            password='OldStrongPass123!',
        )

        # 1. Page loads
        resp = self.client.get(reverse('accounts:password_reset'))
        self.assertEqual(resp.status_code, 200)

        # 2. Submit registered email -> OTP generated & emailed
        resp = self.client.post(reverse('accounts:password_reset'), {
            'email': user.email,
        })
        self.assertRedirects(resp, reverse('accounts:password_reset_verify_otp'))
        self.assertEqual(len(mail.outbox), 1)
        email_body = mail.outbox[0].body
        self.assertIn('NearNest', email_body)
        self.assertIn('5 minutes', email_body)

        # Extract 6-digit OTP from email
        otp_match = re.search(r'\b\d{6}\b', email_body)
        self.assertIsNotNone(otp_match)
        otp_code = otp_match.group(0)

        # Verify OTP is hashed in DB, never plain text
        otp_record = PasswordResetOTP.objects.get(email=user.email)
        self.assertNotEqual(otp_record.otp_hash, otp_code)
        self.assertEqual(otp_record.otp_hash, PasswordResetOTP.hash_otp(otp_code))

        # 3. Verify correct OTP -> Redirects to set password
        verify_resp = self.client.post(reverse('accounts:password_reset_verify_otp'), {
            'otp': otp_code,
        })
        self.assertRedirects(verify_resp, reverse('accounts:password_reset_set_password'))
        otp_record.refresh_from_db()
        self.assertTrue(otp_record.is_used)
        self.assertTrue(otp_record.reset_token)

        # 4. Attempt mismatched password on set-password page -> Rejected
        mismatch_resp = self.client.post(reverse('accounts:password_reset_set_password'), {
            'new_password1': 'BrandNewPass123!',
            'new_password2': 'DoesNotMatch123!',
        })
        self.assertEqual(mismatch_resp.status_code, 200)
        self.assertIn('new_password2', mismatch_resp.context['form'].errors)

        # 5. Submit valid matching new password -> Succeeds
        set_resp = self.client.post(reverse('accounts:password_reset_set_password'), {
            'new_password1': 'BrandNewPass123!',
            'new_password2': 'BrandNewPass123!',
        })
        self.assertRedirects(set_resp, reverse('accounts:password_reset_done'))

        # 6. Verify old password no longer works
        user.refresh_from_db()
        self.assertFalse(self.client.login(username='resetuser', password='OldStrongPass123!'))

        # 7. Verify new password works immediately
        self.assertTrue(self.client.login(username='resetuser', password='BrandNewPass123!'))

    def test_otp_password_reset_rejects_unregistered_email(self):
        """Reject password reset request if email is not registered."""
        response = self.client.post(reverse('accounts:password_reset'), {
            'email': 'unknown@example.com',
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['form'].errors)
        self.assertEqual(len(mail.outbox), 0)

    def test_otp_verification_rejects_invalid_otp_and_tracks_attempts(self):
        """Reject invalid OTP and enforce 5-attempt limit."""
        user = User.objects.create_user(
            username='attemptuser',
            email='attempt@example.com',
            password='OldPass123!',
        )
        self.client.post(reverse('accounts:password_reset'), {'email': user.email})
        self.assertEqual(len(mail.outbox), 1)

        otp_record = PasswordResetOTP.objects.get(email=user.email)

        # Submit wrong OTP 4 times
        for attempt in range(1, 5):
            resp = self.client.post(reverse('accounts:password_reset_verify_otp'), {'otp': '000000'})
            self.assertEqual(resp.status_code, 200)
            otp_record.refresh_from_db()
            self.assertEqual(otp_record.attempts, attempt)

        # 5th attempt -> max attempts reached
        resp5 = self.client.post(reverse('accounts:password_reset_verify_otp'), {'otp': '000000'})
        self.assertEqual(resp5.status_code, 200)
        otp_record.refresh_from_db()
        self.assertEqual(otp_record.attempts, 5)

        # Now even submitting the correct OTP is rejected because attempts exceeded
        correct_otp = re.search(r'\b\d{6}\b', mail.outbox[0].body).group(0)
        resp_after_lock = self.client.post(reverse('accounts:password_reset_verify_otp'), {'otp': correct_otp})
        self.assertEqual(resp_after_lock.status_code, 200)
        self.assertContains(resp_after_lock, 'Maximum verification attempts exceeded')

    def test_otp_verification_rejects_expired_otp(self):
        """Reject OTP that has expired (>5 minutes)."""
        user = User.objects.create_user(
            username='expireduser',
            email='expired@example.com',
            password='OldPass123!',
        )
        self.client.post(reverse('accounts:password_reset'), {'email': user.email})
        correct_otp = re.search(r'\b\d{6}\b', mail.outbox[0].body).group(0)

        # Manually expire the OTP
        otp_record = PasswordResetOTP.objects.get(email=user.email)
        otp_record.expires_at = timezone.now() - timedelta(minutes=1)
        otp_record.save()

        resp = self.client.post(reverse('accounts:password_reset_verify_otp'), {'otp': correct_otp})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'expired')

    def test_otp_resend_and_cooldown(self):
        """Verify 60-second cooldown on OTP resend."""
        user = User.objects.create_user(
            username='cooldownuser',
            email='cooldown@example.com',
            password='OldPass123!',
        )
        self.client.post(reverse('accounts:password_reset'), {'email': user.email})
        self.assertEqual(len(mail.outbox), 1)

        # Immediate resend should be blocked by 60s cooldown
        resend_blocked = self.client.post(reverse('accounts:password_reset_resend_otp'))
        self.assertRedirects(resend_blocked, reverse('accounts:password_reset_verify_otp'))
        self.assertEqual(len(mail.outbox), 1)  # No new email sent

        # Simulate cooldown elapsed (>60s)
        otp_record = PasswordResetOTP.objects.get(email=user.email)
        otp_record.created_at = timezone.now() - timedelta(seconds=65)
        otp_record.save()

        # Resend should now succeed and send a new OTP
        resend_ok = self.client.post(reverse('accounts:password_reset_resend_otp'))
        self.assertRedirects(resend_ok, reverse('accounts:password_reset_verify_otp'))
        self.assertEqual(len(mail.outbox), 2)  # New email sent
        self.assertEqual(PasswordResetOTP.objects.filter(email=user.email).count(), 2)

    def test_cannot_access_set_password_without_otp_verification(self):
        """Ensure reset password page is protected and cannot be bypassed."""
        resp = self.client.get(reverse('accounts:password_reset_set_password'))
        self.assertRedirects(resp, reverse('accounts:password_reset'))

    def test_password_reset_works_for_oauth_user_with_unusable_password(self):
        """OAuth users with unusable passwords can set a password via OTP."""
        user = User.objects.create_user(
            username='oauthuser',
            email='oauthuser@example.com',
        )
        user.set_unusable_password()
        user.save()
        self.assertFalse(user.has_usable_password())

        self.client.post(reverse('accounts:password_reset'), {'email': user.email})
        otp_code = re.search(r'\b\d{6}\b', mail.outbox[0].body).group(0)

        self.client.post(reverse('accounts:password_reset_verify_otp'), {'otp': otp_code})
        self.client.post(reverse('accounts:password_reset_set_password'), {
            'new_password1': 'NewOAuthPass123!',
            'new_password2': 'NewOAuthPass123!',
        })

        user.refresh_from_db()
        self.assertTrue(user.has_usable_password())
        self.assertTrue(self.client.login(username='oauthuser', password='NewOAuthPass123!'))

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
