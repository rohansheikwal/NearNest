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
            available_days='0,1,2,3,4,5,6',
            start_time=datetime.time(9, 0),
            end_time=datetime.time(18, 0),
            duration_hours=1,
            availability='Everyday, 9 AM–6 PM',
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


class ProviderWiseAvailabilityValidationScenariosTests(TestCase):
    """
    Comprehensive tests covering all Scenarios A through N as specified in Section 12:
    - Test A: Provider A (Mon-Sat, 10 AM-10 PM), Wed 11 AM -> Valid
    - Test B: Provider A, Sunday 2 PM -> Rejected
    - Test C: Provider A, Monday 8 AM -> Rejected
    - Test D: Provider A, Monday 11 PM -> Rejected
    - Test E: Provider B (Mon-Fri, 8 AM-4 PM), Tue 9 AM -> Valid
    - Test F: Provider B, Saturday 11 AM -> Rejected
    - Test G: Provider C (Tue-Sun, 12 PM-8 PM), Sun 2 PM -> Valid
    - Test H: Independent Provider schedules (Provider A rules never apply to B or C)
    - Test I: Provider updates schedule -> future bookings immediately respect updated schedule
    - Test J: Past date -> Rejected
    - Test K: Service duration overflow (Closes 10 PM, duration 2 hrs, booking at 9 PM -> Rejected)
    - Test L: Confirmed/accepted overlapping booking -> Rejected
    - Test M: Backend direct POST bypass -> Rejected with validation errors
    - Test N: New future provider & service -> automatically validated
    """

    def setUp(self):
        self.category = ServiceCategory.objects.create(name='Home Services', slug='home-services')
        self.customer = self._create_user('cust_test', Profile.ROLE_CUSTOMER)

        # Provider A: Mon-Sat, 10:00 AM - 10:00 PM, duration 1 hr
        self.prov_a = self._create_user('provider_a', Profile.ROLE_PROVIDER)
        self.service_a = Service.objects.create(
            provider=self.prov_a,
            category=self.category,
            title='Electrician Service',
            description='Electrical repairs',
            price=Decimal('400.00'),
            available_days='0,1,2,3,4,5',
            start_time=datetime.time(10, 0),
            end_time=datetime.time(22, 0),
            duration_hours=1,
            availability='Monday to Saturday, 10:00 AM to 10:00 PM',
            city='Mumbai',
        )

        # Provider B: Mon-Fri, 08:00 AM - 04:00 PM, duration 1 hr
        self.prov_b = self._create_user('provider_b', Profile.ROLE_PROVIDER)
        self.service_b = Service.objects.create(
            provider=self.prov_b,
            category=self.category,
            title='Plumber Service',
            description='Plumbing repairs',
            price=Decimal('350.00'),
            available_days='0,1,2,3,4',
            start_time=datetime.time(8, 0),
            end_time=datetime.time(16, 0),
            duration_hours=1,
            availability='Monday to Friday, 8:00 AM to 4:00 PM',
            city='Mumbai',
        )

        # Provider C: Tue-Sun, 12:00 PM - 08:00 PM, duration 1 hr
        self.prov_c = self._create_user('provider_c', Profile.ROLE_PROVIDER)
        self.service_c = Service.objects.create(
            provider=self.prov_c,
            category=self.category,
            title='AC Repair Service',
            description='AC servicing',
            price=Decimal('600.00'),
            available_days='1,2,3,4,5,6',
            start_time=datetime.time(12, 0),
            end_time=datetime.time(20, 0),
            duration_hours=1,
            availability='Tuesday to Sunday, 12:00 PM to 8:00 PM',
            city='Mumbai',
        )

    def _create_user(self, username, role):
        user = User.objects.create_user(username=username, password='PassWord123!')
        user.profile.role = role
        user.profile.save()
        return user

    def _get_next_weekday(self, target_weekday):
        """Get date of the next occurrence of target_weekday (0=Mon...6=Sun) at least 1 day in future."""
        today = datetime.date.today()
        days_ahead = target_weekday - today.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        return today + datetime.timedelta(days=days_ahead)

    def test_scenario_a_provider_a_valid_booking(self):
        # Wed 11:00 AM is within Mon-Sat 10 AM - 10 PM
        wednesday = self._get_next_weekday(2)
        valid, msg = self.service_a.is_date_available(wednesday)
        self.assertTrue(valid, msg)
        valid_t, msg_t = self.service_a.is_time_available(wednesday, datetime.time(11, 0))
        self.assertTrue(valid_t, msg_t)

    def test_scenario_b_provider_a_unavailable_day_rejected(self):
        # Sunday is weekday 6, Provider A works 0-5
        sunday = self._get_next_weekday(6)
        valid, msg = self.service_a.is_date_available(sunday)
        self.assertFalse(valid)
        self.assertIn("Sunday", msg)

    def test_scenario_c_provider_a_before_working_hours_rejected(self):
        # Monday 08:00 AM is before 10:00 AM opening
        monday = self._get_next_weekday(0)
        valid_t, msg_t = self.service_a.is_time_available(monday, datetime.time(8, 0))
        self.assertFalse(valid_t)
        self.assertIn("before", msg_t.lower())

    def test_scenario_d_provider_a_after_working_hours_rejected(self):
        # Monday 11:00 PM (23:00) is after 10:00 PM (22:00) closing
        monday = self._get_next_weekday(0)
        valid_t, msg_t = self.service_a.is_time_available(monday, datetime.time(23, 0))
        self.assertFalse(valid_t)
        self.assertIn("after", msg_t.lower())

    def test_scenario_e_provider_b_valid_booking(self):
        # Tuesday 09:00 AM is within Mon-Fri 8 AM - 4 PM
        tuesday = self._get_next_weekday(1)
        valid, msg = self.service_b.is_date_available(tuesday)
        self.assertTrue(valid, msg)
        valid_t, msg_t = self.service_b.is_time_available(tuesday, datetime.time(9, 0))
        self.assertTrue(valid_t, msg_t)

    def test_scenario_f_provider_b_unavailable_day_rejected(self):
        # Saturday is weekday 5, Provider B works 0-4
        saturday = self._get_next_weekday(5)
        valid, msg = self.service_b.is_date_available(saturday)
        self.assertFalse(valid)
        self.assertIn("Saturday", msg)

    def test_scenario_g_provider_c_sunday_valid(self):
        # Sunday 2:00 PM is valid for Provider C (works Tue-Sun 12 PM - 8 PM)
        sunday = self._get_next_weekday(6)
        valid, msg = self.service_c.is_date_available(sunday)
        self.assertTrue(valid, msg)
        valid_t, msg_t = self.service_c.is_time_available(sunday, datetime.time(14, 0))
        self.assertTrue(valid_t, msg_t)

    def test_scenario_h_independent_schedules(self):
        # Sunday is valid for C, but rejected for A and B
        sunday = self._get_next_weekday(6)
        valid_a, _ = self.service_a.is_date_available(sunday)
        valid_b, _ = self.service_b.is_date_available(sunday)
        valid_c, _ = self.service_c.is_date_available(sunday)
        self.assertFalse(valid_a)
        self.assertFalse(valid_b)
        self.assertTrue(valid_c)

    def test_scenario_i_provider_updates_schedule(self):
        # Change Provider A to 12:00 PM - 08:00 PM
        self.service_a.start_time = datetime.time(12, 0)
        self.service_a.end_time = datetime.time(20, 0)
        self.service_a.save()

        monday = self._get_next_weekday(0)
        # 10:30 AM was valid before, now rejected
        valid_t, msg_t = self.service_a.is_time_available(monday, datetime.time(10, 30))
        self.assertFalse(valid_t)
        # 02:00 PM is valid
        valid_t2, _ = self.service_a.is_time_available(monday, datetime.time(14, 0))
        self.assertTrue(valid_t2)

    def test_scenario_j_past_date_rejected(self):
        past_date = datetime.date.today() - datetime.timedelta(days=1)
        valid, msg = self.service_a.is_date_available(past_date)
        self.assertFalse(valid)
        self.assertIn("past", msg.lower())

    def test_scenario_k_service_duration_overflow_rejected(self):
        # Provider A closes at 22:00 (10 PM). Service duration = 2 hours.
        self.service_a.duration_hours = 2
        self.service_a.save()

        monday = self._get_next_weekday(0)
        # 21:00 (9 PM) + 2 hrs = 23:00 (11 PM) -> exceeds closing time 22:00 -> rejected
        valid_t, msg_t = self.service_a.is_time_available(monday, datetime.time(21, 0))
        self.assertFalse(valid_t)
        self.assertIn("closing time", msg_t.lower())

        # 20:00 (8 PM) + 2 hrs = 22:00 -> exactly fits closing time -> allowed
        valid_t2, msg_t2 = self.service_a.is_time_available(monday, datetime.time(20, 0))
        self.assertTrue(valid_t2, msg_t2)

    def test_scenario_l_overlapping_booking_rejected(self):
        monday = self._get_next_weekday(0)
        # Existing accepted booking for Provider A from 14:00 to 16:00 (duration 2 hrs)
        self.service_a.duration_hours = 2
        self.service_a.save()
        ServiceRequest.objects.create(
            customer=self.customer,
            service=self.service_a,
            requested_date=monday,
            requested_time=datetime.time(14, 0),
            service_location='123 Test St',
            work_description='Fix wiring',
            status=ServiceRequest.STATUS_ACCEPTED,
        )

        # Another booking at 15:00 overlaps (14:00 - 16:00 is occupied)
        valid_t, msg_t = self.service_a.is_time_available(monday, datetime.time(15, 0))
        self.assertFalse(valid_t)
        self.assertIn("conflicts with an existing", msg_t.lower())

        # 16:00 onwards is free
        valid_t2, msg_t2 = self.service_a.is_time_available(monday, datetime.time(16, 0))
        self.assertTrue(valid_t2, msg_t2)

    def test_scenario_m_backend_post_bypass_rejected(self):
        # Direct POST bypassing frontend with Sunday date for Provider A
        sunday = self._get_next_weekday(6)
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('bookings:request_service', args=[self.service_a.pk]),
            {
                'requested_date': sunday.isoformat(),
                'requested_time': '14:00',
                'service_location': '123 Bypass St',
                'work_description': 'Test bypass',
            }
        )
        # Should stay on page and render error, NOT redirect to success
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sunday")

    def test_scenario_n_future_provider_and_service_auto_validated(self):
        # Brand new provider added dynamically
        new_prov = self._create_user('future_provider', Profile.ROLE_PROVIDER)
        new_svc = Service.objects.create(
            provider=new_prov,
            category=self.category,
            title='Gardening',
            description='Garden care',
            price=Decimal('250.00'),
            available_days='5,6',  # Saturday and Sunday only
            start_time=datetime.time(7, 0),
            end_time=datetime.time(12, 0),
            duration_hours=1,
            city='Delhi',
        )

        # Wednesday rejected automatically
        wednesday = self._get_next_weekday(2)
        valid_wed, _ = new_svc.is_date_available(wednesday)
        self.assertFalse(valid_wed)

        # Saturday 08:00 AM valid automatically
        saturday = self._get_next_weekday(5)
        valid_sat, _ = new_svc.is_date_available(saturday)
        self.assertTrue(valid_sat)
        valid_time, _ = new_svc.is_time_available(saturday, datetime.time(8, 0))
        self.assertTrue(valid_time)

# Create your tests here.
