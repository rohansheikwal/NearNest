"""
Neighborly Test Suite
=====================
Covers models, views, and workflows across all apps.
Run with: py manage.py test
"""
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from decimal import Decimal
import datetime

from accounts.models import Profile
from services.models import Service, ServiceCategory
from bookings.models import ServiceRequest, SavedService
from reviews.models import Review


# ============================================================
# HELPERS
# ============================================================

def make_customer(username='customer1', password='TestPass123!'):
    user = User.objects.create_user(username=username, password=password, email=f'{username}@test.com')
    user.profile.role = Profile.ROLE_CUSTOMER
    user.profile.city = 'Testville'
    user.profile.full_name = 'Test Customer'
    user.profile.save()
    return user


def make_provider(username='provider1', password='TestPass123!'):
    user = User.objects.create_user(username=username, password=password, email=f'{username}@test.com')
    user.profile.role = Profile.ROLE_PROVIDER
    user.profile.city = 'Testville'
    user.profile.full_name = 'Test Provider'
    user.profile.skills = 'Plumbing, Repairs'
    user.profile.save()
    return user


def make_category(name='Plumbing'):
    return ServiceCategory.objects.create(name=name, slug=name.lower().replace(' ', '-'))


def make_service(provider, category, title='Test Service', price=500):
    return Service.objects.create(
        provider=provider,
        category=category,
        title=title,
        description='A detailed service description for testing purposes.',
        price=Decimal(price),
        pricing_unit=Service.UNIT_VISIT,
        city='Testville',
        area='Test Area',
        is_active=True,
    )


def make_request(customer, service, status=ServiceRequest.STATUS_PENDING):
    return ServiceRequest.objects.create(
        customer=customer,
        service=service,
        requested_date=datetime.date.today() + datetime.timedelta(days=3),
        service_location='123 Test Street, Testville',
        work_description='Please fix the leaking pipe under the kitchen sink.',
        status=status,
    )


# ============================================================
# ACCOUNTS APP TESTS
# ============================================================

class ProfileModelTest(TestCase):

    def test_profile_auto_created_on_user_creation(self):
        user = User.objects.create_user(username='signaltest', password='pass')
        self.assertTrue(hasattr(user, 'profile'))
        self.assertIsInstance(user.profile, Profile)

    def test_default_role_is_customer(self):
        user = User.objects.create_user(username='defaultrole', password='pass')
        self.assertTrue(user.profile.is_customer)
        self.assertFalse(user.profile.is_provider)

    def test_provider_role(self):
        provider = make_provider()
        self.assertTrue(provider.profile.is_provider)
        self.assertFalse(provider.profile.is_customer)

    def test_get_display_name_uses_full_name(self):
        user = User.objects.create_user(username='disptest', password='pass')
        user.profile.full_name = 'Ravi Kumar'
        user.profile.save()
        self.assertEqual(user.profile.get_display_name(), 'Ravi Kumar')

    def test_get_display_name_falls_back_to_username(self):
        user = User.objects.create_user(username='fallback', password='pass')
        self.assertEqual(user.profile.get_display_name(), 'fallback')

    def test_get_location_display_with_city_and_area(self):
        user = User.objects.create_user(username='loctest', password='pass')
        user.profile.city = 'Bangalore'
        user.profile.area = 'Koramangala'
        user.profile.save()
        loc = user.profile.get_location_display()
        self.assertIn('Bangalore', loc)
        self.assertIn('Koramangala', loc)

    def test_get_location_display_without_location(self):
        user = User.objects.create_user(username='noloc', password='pass')
        loc = user.profile.get_location_display()
        self.assertEqual(loc, 'Location not specified')


class AuthViewTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_login_page_loads(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'accounts/login.html')

    def test_register_customer_page_loads(self):
        response = self.client.get(reverse('accounts:register_customer'))
        self.assertEqual(response.status_code, 200)

    def test_register_provider_page_loads(self):
        response = self.client.get(reverse('accounts:register_provider'))
        self.assertEqual(response.status_code, 200)

    def test_customer_registration(self):
        response = self.client.post(reverse('accounts:register_customer'), {
            'username': 'newcustomer',
            'email': 'newcustomer@test.com',
            'full_name': 'New Customer',
            'city': 'Mumbai',
            'password1': 'Str0ng!Pass#99',
            'password2': 'Str0ng!Pass#99',
        })
        # Should redirect after success
        self.assertIn(response.status_code, [200, 302])
        # User created
        self.assertTrue(User.objects.filter(username='newcustomer').exists())
        # Role assigned correctly
        user = User.objects.get(username='newcustomer')
        self.assertTrue(user.profile.is_customer)

    def test_provider_registration(self):
        response = self.client.post(reverse('accounts:register_provider'), {
            'username': 'newprovider',
            'email': 'newprovider@test.com',
            'full_name': 'New Provider',
            'city': 'Delhi',
            'skills': 'Electrical, Wiring',
            'password1': 'Str0ng!Pass#99',
            'password2': 'Str0ng!Pass#99',
        })
        self.assertIn(response.status_code, [200, 302])
        if User.objects.filter(username='newprovider').exists():
            user = User.objects.get(username='newprovider')
            self.assertTrue(user.profile.is_provider)

    def test_login_and_logout(self):
        user = make_customer('logintest')
        response = self.client.post(reverse('accounts:login'), {
            'username': 'logintest',
            'password': 'TestPass123!',
        })
        self.assertEqual(response.status_code, 302)
        # Logout
        self.client.login(username='logintest', password='TestPass123!')
        response = self.client.get(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)

    def test_login_rejects_external_next_redirect(self):
        make_customer('redirecttest')
        response = self.client.post(
            reverse('accounts:login') + '?next=//evil.example/login',
            {'username': 'redirecttest', 'password': 'TestPass123!'},
        )
        self.assertEqual(response.status_code, 302)
        self.assertNotIn('evil.example', response.url)

    def test_dashboard_redirects_unauthenticated(self):
        response = self.client.get(reverse('accounts:customer_dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_customer_dashboard_accessible_when_logged_in(self):
        user = make_customer('dashtest')
        self.client.login(username='dashtest', password='TestPass123!')
        response = self.client.get(reverse('accounts:customer_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_profile_view_requires_login(self):
        response = self.client.get(reverse('accounts:profile'))
        self.assertEqual(response.status_code, 302)


# ============================================================
# SERVICES APP TESTS
# ============================================================

class ServiceCategoryModelTest(TestCase):

    def test_category_slug_auto_generated(self):
        cat = ServiceCategory.objects.create(name='Home Cleaning')
        self.assertEqual(cat.slug, 'home-cleaning')

    def test_category_get_absolute_url(self):
        cat = make_category('Electrical')
        url = cat.get_absolute_url()
        self.assertIn('electrical', url)


class ServiceModelTest(TestCase):

    def setUp(self):
        self.provider = make_provider()
        self.category = make_category()

    def test_service_creation(self):
        service = make_service(self.provider, self.category)
        self.assertEqual(service.title, 'Test Service')
        self.assertEqual(service.price, Decimal('500'))
        self.assertTrue(service.is_active)

    def test_get_price_display(self):
        service = make_service(self.provider, self.category, price=750)
        display = service.get_price_display()
        self.assertIn('750', display)

    def test_get_location_display(self):
        service = make_service(self.provider, self.category)
        loc = service.get_location_display()
        self.assertIn('Testville', loc)

    def test_get_absolute_url(self):
        service = make_service(self.provider, self.category)
        url = service.get_absolute_url()
        self.assertIn(str(service.pk), url)

    def test_get_average_rating_no_reviews(self):
        service = make_service(self.provider, self.category)
        self.assertIsNone(service.get_average_rating())

    def test_get_review_count_no_reviews(self):
        service = make_service(self.provider, self.category)
        self.assertEqual(service.get_review_count(), 0)


class ServiceViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.provider = make_provider()
        self.category = make_category()
        self.service = make_service(self.provider, self.category)

    def test_service_list_page_loads(self):
        response = self.client.get(reverse('services:service_list'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'services/service_list.html')

    def test_service_list_shows_active_services(self):
        response = self.client.get(reverse('services:service_list'))
        self.assertContains(response, self.service.title)

    def test_service_list_hides_inactive_services(self):
        inactive = make_service(self.provider, self.category, title='Inactive Service')
        inactive.is_active = False
        inactive.save()
        response = self.client.get(reverse('services:service_list'))
        self.assertNotContains(response, 'Inactive Service')

    def test_service_detail_page_loads(self):
        detail_url = reverse('services:service_detail', kwargs={'pk': self.service.pk})
        response = self.client.get(detail_url)
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={detail_url}",
        )
        make_customer()
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.get(reverse('services:service_detail', kwargs={'pk': self.service.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'services/service_detail.html')

    def test_service_detail_requires_login(self):
        response = self.client.get(reverse('services:service_detail', kwargs={'pk': self.service.pk}))
        self.assertEqual(response.status_code, 302)

    def test_service_detail_shows_service_info(self):
        make_customer()
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.get(reverse('services:service_detail', kwargs={'pk': self.service.pk}))
        self.assertContains(response, self.service.title)

    def test_service_detail_uses_category_fallback_image(self):
        make_customer()
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.get(
            reverse('services:service_detail', kwargs={'pk': self.service.pk})
        )
        self.assertContains(response, '/static/images/explore-plumber.jpg')
        self.assertNotContains(response, 'No image provided')

    def test_service_list_search_filter(self):
        response = self.client.get(reverse('services:service_list') + '?q=Test')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.service.title)

    def test_service_list_city_filter(self):
        response = self.client.get(reverse('services:service_list') + '?city=Testville')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.service.title)

    def test_provider_dashboard_requires_login(self):
        response = self.client.get(reverse('services:provider_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_provider_dashboard_requires_provider_role(self):
        customer = make_customer('notprovider')
        self.client.login(username='notprovider', password='TestPass123!')
        response = self.client.get(reverse('services:provider_dashboard'))
        # Should redirect to home, not show 200
        self.assertEqual(response.status_code, 302)

    def test_provider_dashboard_accessible_for_provider(self):
        self.client.login(username='provider1', password='TestPass123!')
        response = self.client.get(reverse('services:provider_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_service_create_page_loads_for_provider(self):
        self.client.login(username='provider1', password='TestPass123!')
        response = self.client.get(reverse('services:service_create'))
        self.assertEqual(response.status_code, 200)

    def test_category_page_loads(self):
        response = self.client.get(reverse('services:category', kwargs={'slug': self.category.slug}))
        self.assertEqual(response.status_code, 200)


# ============================================================
# BOOKINGS APP TESTS
# ============================================================

class ServiceRequestModelTest(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.provider = make_provider()
        self.category = make_category()
        self.service = make_service(self.provider, self.category)

    def test_request_creation(self):
        req = make_request(self.customer, self.service)
        self.assertEqual(req.status, ServiceRequest.STATUS_PENDING)
        self.assertEqual(req.customer, self.customer)
        self.assertEqual(req.service, self.service)

    def test_can_be_cancelled_when_pending(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_PENDING)
        self.assertTrue(req.can_be_cancelled)

    def test_can_be_cancelled_when_accepted(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_ACCEPTED)
        self.assertTrue(req.can_be_cancelled)

    def test_cannot_be_cancelled_when_completed(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_COMPLETED)
        self.assertFalse(req.can_be_cancelled)

    def test_cannot_be_cancelled_when_inprogress(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_INPROGRESS)
        self.assertFalse(req.can_be_cancelled)

    def test_has_review_false_by_default(self):
        req = make_request(self.customer, self.service)
        self.assertFalse(req.has_review)

    def test_get_status_badge_class(self):
        req = make_request(self.customer, self.service)
        badge = req.get_status_badge_class
        self.assertEqual(badge, 'badge-warning')


class BookingViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.customer = make_customer()
        self.provider = make_provider()
        self.category = make_category()
        self.service = make_service(self.provider, self.category)

    def test_request_form_requires_login(self):
        response = self.client.get(reverse('bookings:request_service', kwargs={'service_pk': self.service.pk}))
        self.assertEqual(response.status_code, 302)

    def test_request_form_loads_for_customer(self):
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.get(reverse('bookings:request_service', kwargs={'service_pk': self.service.pk}))
        self.assertEqual(response.status_code, 200)

    def test_submit_service_request(self):
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.post(
            reverse('bookings:request_service', kwargs={'service_pk': self.service.pk}),
            {
                'requested_date': (datetime.date.today() + datetime.timedelta(days=2)).isoformat(),
                'service_location': '45 Test Road, Testville',
                'work_description': 'Please fix the kitchen tap that is dripping badly.',
            }
        )
        # Should redirect to request detail
        self.assertEqual(response.status_code, 302)
        self.assertTrue(ServiceRequest.objects.filter(customer=self.customer, service=self.service).exists())

    def test_my_requests_page_loads(self):
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.get(reverse('bookings:my_requests'))
        self.assertEqual(response.status_code, 200)

    def test_saved_services_page_loads(self):
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.get(reverse('bookings:saved_services'))
        self.assertEqual(response.status_code, 200)

    def test_toggle_save_service(self):
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.post(
            reverse('bookings:toggle_save', kwargs={'service_pk': self.service.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['saved'])
        self.assertTrue(SavedService.objects.filter(customer=self.customer, service=self.service).exists())

    def test_toggle_save_service_unsave(self):
        """Toggling a saved service removes it."""
        SavedService.objects.create(customer=self.customer, service=self.service)
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.post(
            reverse('bookings:toggle_save', kwargs={'service_pk': self.service.pk})
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data['saved'])

    def test_cancel_pending_request(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_PENDING)
        self.client.login(username='customer1', password='TestPass123!')
        self.client.post(reverse('bookings:cancel_request', kwargs={'pk': req.pk}))
        req.refresh_from_db()
        self.assertEqual(req.status, ServiceRequest.STATUS_CANCELLED)

    def test_cannot_cancel_completed_request(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_COMPLETED)
        self.client.login(username='customer1', password='TestPass123!')
        self.client.post(reverse('bookings:cancel_request', kwargs={'pk': req.pk}))
        req.refresh_from_db()
        # Status should remain completed
        self.assertEqual(req.status, ServiceRequest.STATUS_COMPLETED)


# ============================================================
# REVIEWS APP TESTS
# ============================================================

class ReviewModelTest(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.provider = make_provider()
        self.category = make_category()
        self.service = make_service(self.provider, self.category)
        self.req = make_request(self.customer, self.service, ServiceRequest.STATUS_COMPLETED)

    def test_review_creation(self):
        review = Review.objects.create(
            service_request=self.req,
            rating=4,
            comment='Great service, very professional!'
        )
        self.assertEqual(review.rating, 4)
        self.assertEqual(review.customer, self.customer)
        self.assertEqual(review.service, self.service)

    def test_has_review_true_after_review(self):
        Review.objects.create(service_request=self.req, rating=5, comment='Excellent!')
        self.req.refresh_from_db()
        self.assertTrue(self.req.has_review)

    def test_service_average_rating_after_review(self):
        Review.objects.create(service_request=self.req, rating=4, comment='Good work')
        avg = self.service.get_average_rating()
        self.assertEqual(avg, 4.0)

    def test_service_review_count(self):
        Review.objects.create(service_request=self.req, rating=3, comment='Decent')
        self.assertEqual(self.service.get_review_count(), 1)


class ReviewViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.customer = make_customer()
        self.provider = make_provider()
        self.category = make_category()
        self.service = make_service(self.provider, self.category)

    def test_review_form_requires_completed_request(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_PENDING)
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.get(reverse('reviews:submit_review', kwargs={'request_pk': req.pk}))
        # Should 404 because status isn't completed
        self.assertEqual(response.status_code, 404)

    def test_review_form_loads_for_completed_request(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_COMPLETED)
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.get(reverse('reviews:submit_review', kwargs={'request_pk': req.pk}))
        self.assertEqual(response.status_code, 200)

    def test_submit_review(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_COMPLETED)
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.post(
            reverse('reviews:submit_review', kwargs={'request_pk': req.pk}),
            {'rating': 5, 'comment': 'Absolutely fantastic service!'}
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Review.objects.filter(service_request=req).exists())

    def test_review_requires_nonempty_comment(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_COMPLETED)
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.post(
            reverse('reviews:submit_review', kwargs={'request_pk': req.pk}),
            {'rating': 5, 'comment': '   '}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Review.objects.filter(service_request=req).exists())
        self.assertContains(response, 'This field is required.')

    def test_other_customer_cannot_review_request(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_COMPLETED)
        other_customer = make_customer('othercustomer')
        self.client.login(username='othercustomer', password='TestPass123!')
        response = self.client.get(
            reverse('reviews:submit_review', kwargs={'request_pk': req.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_provider_cannot_review_request(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_COMPLETED)
        self.client.login(username='provider1', password='TestPass123!')
        response = self.client.get(
            reverse('reviews:submit_review', kwargs={'request_pk': req.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_double_review(self):
        req = make_request(self.customer, self.service, ServiceRequest.STATUS_COMPLETED)
        Review.objects.create(service_request=req, rating=4, comment='Already reviewed.')
        self.client.login(username='customer1', password='TestPass123!')
        response = self.client.get(reverse('reviews:submit_review', kwargs={'request_pk': req.pk}))
        # Should redirect away
        self.assertEqual(response.status_code, 302)


# ============================================================
# CORE APP TESTS
# ============================================================

class CoreViewTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_homepage_loads(self):
        response = self.client.get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'core/home.html')

    def test_about_page_loads(self):
        response = self.client.get(reverse('core:about'))
        self.assertEqual(response.status_code, 200)

    def test_how_it_works_page_loads(self):
        response = self.client.get(reverse('core:how_it_works'))
        self.assertEqual(response.status_code, 200)

    def test_contact_page_loads(self):
        response = self.client.get(reverse('core:contact'))
        self.assertEqual(response.status_code, 200)

    def test_faq_page_loads(self):
        response = self.client.get(reverse('core:faq'))
        self.assertEqual(response.status_code, 200)

    def test_privacy_page_loads(self):
        response = self.client.get(reverse('core:privacy'))
        self.assertEqual(response.status_code, 200)

    def test_terms_page_loads(self):
        response = self.client.get(reverse('core:terms'))
        self.assertEqual(response.status_code, 200)

    def test_become_provider_page_loads(self):
        response = self.client.get(reverse('core:become_provider'))
        self.assertEqual(response.status_code, 200)

    def test_contact_form_submission(self):
        response = self.client.post(reverse('core:contact'), {
            'name': 'Test User',
            'email': 'test@test.com',
            'subject': 'Test Subject',
            'message': 'This is a test message for the contact form.',
        })
        self.assertEqual(response.status_code, 302)
        from core.models import ContactMessage
        self.assertTrue(ContactMessage.objects.filter(email='test@test.com').exists())

    def test_contact_form_rejects_invalid_email(self):
        response = self.client.post(reverse('core:contact'), {
            'name': 'Test User',
            'email': 'not-an-email',
            'subject': 'Test Subject',
            'message': 'This is a test message for the contact form.',
        })
        self.assertEqual(response.status_code, 200)
        from core.models import ContactMessage
        self.assertFalse(ContactMessage.objects.exists())

    def test_homepage_search_redirects(self):
        response = self.client.get(reverse('core:home') + '?q=plumber')
        self.assertEqual(response.status_code, 302)
        self.assertIn('plumber', response.url)


# ============================================================
# PROVIDER WORKFLOW INTEGRATION TEST
# ============================================================

class ProviderWorkflowTest(TestCase):
    """End-to-end test of the provider request management workflow."""

    def setUp(self):
        self.client = Client()
        self.customer = make_customer()
        self.provider = make_provider()
        self.category = make_category()
        self.service = make_service(self.provider, self.category)
        self.req = make_request(self.customer, self.service, ServiceRequest.STATUS_PENDING)

    def test_provider_can_accept_request(self):
        self.client.login(username='provider1', password='TestPass123!')
        self.client.post(
            reverse('services:update_request_status', kwargs={'request_id': self.req.pk}),
            {'status': 'accepted', 'next': reverse('services:provider_requests')}
        )
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, ServiceRequest.STATUS_ACCEPTED)

    def test_provider_can_reject_request(self):
        self.client.login(username='provider1', password='TestPass123!')
        self.client.post(
            reverse('services:update_request_status', kwargs={'request_id': self.req.pk}),
            {'status': 'rejected', 'next': reverse('services:provider_requests')}
        )
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, ServiceRequest.STATUS_REJECTED)

    def test_provider_can_progress_to_inprogress(self):
        self.req.status = ServiceRequest.STATUS_ACCEPTED
        self.req.save()
        self.client.login(username='provider1', password='TestPass123!')
        self.client.post(
            reverse('services:update_request_status', kwargs={'request_id': self.req.pk}),
            {'status': 'inprogress', 'next': reverse('services:provider_requests')}
        )
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, ServiceRequest.STATUS_INPROGRESS)

    def test_provider_can_mark_completed(self):
        self.req.status = ServiceRequest.STATUS_INPROGRESS
        self.req.save()
        self.client.login(username='provider1', password='TestPass123!')
        self.client.post(
            reverse('services:update_request_status', kwargs={'request_id': self.req.pk}),
            {'status': 'completed', 'next': reverse('services:provider_requests')}
        )
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, ServiceRequest.STATUS_COMPLETED)

    def test_invalid_status_transition_blocked(self):
        """Cannot jump from pending to completed directly."""
        self.client.login(username='provider1', password='TestPass123!')
        self.client.post(
            reverse('services:update_request_status', kwargs={'request_id': self.req.pk}),
            {'status': 'completed', 'next': reverse('services:provider_requests')}
        )
        self.req.refresh_from_db()
        self.assertEqual(self.req.status, ServiceRequest.STATUS_PENDING)

    def test_customer_cannot_update_provider_requests(self):
        """A customer logged in should not be able to update request status."""
        self.client.login(username='customer1', password='TestPass123!')
        self.client.post(
            reverse('services:update_request_status', kwargs={'request_id': self.req.pk}),
            {'status': 'accepted'}
        )
        self.req.refresh_from_db()
        # Status should remain pending — provider-only action
        self.assertEqual(self.req.status, ServiceRequest.STATUS_PENDING)


# ============================================================
# CUSTOMER PORTAL & BOOKING ISOLATION TESTS
# ============================================================

class CustomerPortalBookingTests(TestCase):

    def setUp(self):
        self.customer = make_customer('customer_test', 'SecretPass123!')
        self.provider = make_provider('provider_test', 'SecretPass123!')
        self.category = make_category('Home Repair')
        self.service = make_service(self.provider, self.category, 'Tap Fixing', price=400)

    def test_customer_login_authenticates_and_shows_customer_navbar(self):
        response = self.client.post(reverse('accounts:login'), {
            'username': 'customer_test',
            'password': 'SecretPass123!',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['user'].is_authenticated)
        self.assertTrue(response.context['user'].profile.is_customer)
        self.assertContains(response, 'Test Customer')
        self.assertContains(response, 'My Requests')
        self.assertNotContains(response, 'href="/accounts/login/"')

    def test_customer_can_access_booking_even_with_provider_query_param(self):
        self.client.login(username='customer_test', password='SecretPass123!')
        url = reverse('bookings:request_service', kwargs={'service_pk': self.service.pk}) + '?portal=provider'
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tap Fixing')

        post_data = {
            'requested_date': (datetime.date.today() + datetime.timedelta(days=2)).isoformat(),
            'requested_time': '11:00',
            'service_location': '77 Park Avenue',
            'work_description': 'Fix the leaking tap please',
        }
        post_response = self.client.post(url, post_data)
        self.assertEqual(post_response.status_code, 302)
        self.assertTrue(ServiceRequest.objects.filter(customer=self.customer, service=self.service).exists())

    def test_customer_login_sanitizes_provider_next_url(self):
        next_target = f"/bookings/request/{self.service.pk}/?portal=provider"
        response = self.client.post(f"{reverse('accounts:login')}?next={next_target}", {
            'username': 'customer_test',
            'password': 'SecretPass123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, f"/bookings/request/{self.service.pk}/")

