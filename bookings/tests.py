import datetime
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from services.models import Service, ServiceCategory
from .models import ServiceRequest


class ServiceRequestWorkflowTests(TestCase):
    def setUp(self):
        self.customer = self._create_user('customer', Profile.ROLE_CUSTOMER)
        self.provider = self._create_user('provider', Profile.ROLE_PROVIDER)
        self.other_provider = self._create_user('otherprovider', Profile.ROLE_PROVIDER)
        self.category = ServiceCategory.objects.create(name='Plumbing', slug='plumbing')
        self.service = Service.objects.create(
            provider=self.provider,
            category=self.category,
            title='Pipe repair',
            description='Repair service',
            price=Decimal('500.00'),
            pricing_unit=Service.UNIT_VISIT,
            city='Testville',
            area='Central',
            is_active=True,
        )
        self.request_data = {
            'requested_date': (datetime.date.today() + datetime.timedelta(days=2)).isoformat(),
            'requested_time': '10:30',
            'service_location': '10 Main Street',
            'work_description': 'Repair the kitchen tap.',
            'notes': 'Please call before arriving.',
        }

    def _create_user(self, username, role):
        user = User.objects.create_user(username=username, password='TestPass123!')
        user.profile.role = role
        user.profile.save()
        return user

    def _create_request(self, status=ServiceRequest.STATUS_PENDING):
        return ServiceRequest.objects.create(
            customer=self.customer,
            service=self.service,
            requested_date=datetime.date.today() + datetime.timedelta(days=2),
            requested_time=datetime.time(10, 30),
            service_location='10 Main Street',
            work_description='Repair the kitchen tap.',
            status=status,
        )

    def test_customer_can_create_request_from_service(self):
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('bookings:request_service', args=[self.service.pk]),
            self.request_data,
        )

        request = ServiceRequest.objects.get()
        self.assertRedirects(response, reverse('bookings:request_detail', args=[request.pk]))
        self.assertEqual(request.customer, self.customer)
        self.assertEqual(request.service, self.service)
        self.assertEqual(request.status, ServiceRequest.STATUS_PENDING)

    def test_provider_cannot_request_own_service(self):
        self.client.force_login(self.provider)
        response = self.client.get(
            reverse('bookings:request_service', args=[self.service.pk])
        )

        self.assertRedirects(response, reverse('core:home'))
        self.assertFalse(ServiceRequest.objects.exists())

    def test_customer_cannot_create_request_with_past_date(self):
        self.client.force_login(self.customer)
        data = {**self.request_data, 'requested_date': '2000-01-01'}
        response = self.client.post(
            reverse('bookings:request_service', args=[self.service.pk]),
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'cannot be in the past')
        self.assertFalse(ServiceRequest.objects.exists())

    def test_provider_can_view_only_own_request_details(self):
        own_request = self._create_request()
        other_service = Service.objects.create(
            provider=self.other_provider,
            category=self.category,
            title='Other service',
            description='Other service',
            price=Decimal('700.00'),
            pricing_unit=Service.UNIT_VISIT,
            city='Testville',
            area='Central',
            is_active=True,
        )
        other_request = ServiceRequest.objects.create(
            customer=self.customer,
            service=other_service,
            requested_date=datetime.date.today() + datetime.timedelta(days=2),
            service_location='Other address',
            work_description='Other work',
        )
        self.client.force_login(self.provider)

        self.assertEqual(
            self.client.get(reverse('bookings:request_detail', args=[own_request.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('bookings:request_detail', args=[other_request.pk])).status_code,
            404,
        )

    def test_customer_can_view_only_own_request_details(self):
        own_request = self._create_request()
        other_customer = self._create_user('othercustomer', Profile.ROLE_CUSTOMER)
        other_request = ServiceRequest.objects.create(
            customer=other_customer,
            service=self.service,
            requested_date=datetime.date.today() + datetime.timedelta(days=2),
            service_location='Other address',
            work_description='Other work',
        )
        self.client.force_login(self.customer)

        self.assertEqual(
            self.client.get(reverse('bookings:request_detail', args=[own_request.pk])).status_code,
            200,
        )
        self.assertEqual(
            self.client.get(reverse('bookings:request_detail', args=[other_request.pk])).status_code,
            404,
        )

    def test_provider_can_accept_start_and_complete(self):
        service_request = self._create_request()
        self.client.force_login(self.provider)
        url = reverse('services:update_request_status', args=[service_request.pk])

        for status in (
            ServiceRequest.STATUS_ACCEPTED,
            ServiceRequest.STATUS_INPROGRESS,
            ServiceRequest.STATUS_COMPLETED,
        ):
            response = self.client.post(url, {'status': status})
            self.assertRedirects(response, reverse('services:provider_requests'))
            service_request.refresh_from_db()
            self.assertEqual(service_request.status, status)

    def test_provider_can_reject_pending_request(self):
        service_request = self._create_request()
        self.client.force_login(self.provider)
        self.client.post(
            reverse('services:update_request_status', args=[service_request.pk]),
            {'status': ServiceRequest.STATUS_REJECTED},
        )

        service_request.refresh_from_db()
        self.assertEqual(service_request.status, ServiceRequest.STATUS_REJECTED)

    def test_invalid_status_transition_is_rejected(self):
        service_request = self._create_request()
        self.client.force_login(self.provider)
        response = self.client.post(
            reverse('services:update_request_status', args=[service_request.pk]),
            {'status': ServiceRequest.STATUS_COMPLETED},
            follow=True,
        )

        service_request.refresh_from_db()
        self.assertEqual(service_request.status, ServiceRequest.STATUS_PENDING)
        self.assertContains(response, 'Invalid status transition.')

    def test_other_provider_cannot_change_request_status(self):
        service_request = self._create_request()
        self.client.force_login(self.other_provider)
        response = self.client.post(
            reverse('services:update_request_status', args=[service_request.pk]),
            {'status': ServiceRequest.STATUS_ACCEPTED},
        )

        self.assertEqual(response.status_code, 404)
        service_request.refresh_from_db()
        self.assertEqual(service_request.status, ServiceRequest.STATUS_PENDING)

    def test_customer_cannot_change_request_status(self):
        service_request = self._create_request()
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('services:update_request_status', args=[service_request.pk]),
            {'status': ServiceRequest.STATUS_ACCEPTED},
        )

        self.assertRedirects(response, reverse('core:home'))
        service_request.refresh_from_db()
        self.assertEqual(service_request.status, ServiceRequest.STATUS_PENDING)

    def test_customer_can_cancel_only_pending_or_accepted_request(self):
        service_request = self._create_request()
        self.client.force_login(self.customer)
        url = reverse('bookings:cancel_request', args=[service_request.pk])

        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        service_request.refresh_from_db()
        self.assertEqual(service_request.status, ServiceRequest.STATUS_CANCELLED)

        service_request.status = ServiceRequest.STATUS_INPROGRESS
        service_request.save()
        response = self.client.post(url)
        service_request.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(service_request.status, ServiceRequest.STATUS_INPROGRESS)

# Create your tests here.
