from django.test import TestCase

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from accounts.models import Profile
from .admin import ServiceAdminForm
from .forms import ServiceForm
from .models import Service, ServiceCategory


class ServiceAdminValidationTests(TestCase):
    def setUp(self):
        self.customer = User.objects.create_user(
            username='customer',
            password='StrongPass123!',
        )
        self.provider = User.objects.create_user(
            username='provider',
            password='StrongPass123!',
        )
        self.provider.profile.role = Profile.ROLE_PROVIDER
        self.provider.profile.save()
        self.category = ServiceCategory.objects.create(name='Plumbing')

    def service_data(self, provider):
        return {
            'provider': provider.pk,
            'category': self.category.pk,
            'title': 'Sink repair',
            'description': 'Repair and maintenance.',
            'price': '500.00',
            'pricing_unit': Service.UNIT_VISIT,
            'city': 'Bengaluru',
            'area': 'Indiranagar',
            'availability': 'Weekdays',
            'is_active': True,
            'is_featured': False,
        }

    def test_admin_service_form_rejects_customer_provider(self):
        form = ServiceAdminForm(data=self.service_data(self.customer))

        self.assertFalse(form.is_valid())
        self.assertIn('provider', form.errors)

    def test_admin_service_form_accepts_provider(self):
        form = ServiceAdminForm(data=self.service_data(self.provider))

        self.assertTrue(form.is_valid(), form.errors)


class MarketplaceViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.provider = User.objects.create_user(
            username='provider',
            password='StrongPass123!',
        )
        self.provider.profile.role = Profile.ROLE_PROVIDER
        self.provider.profile.full_name = 'Provider One'
        self.provider.profile.save()
        self.other_provider = User.objects.create_user(
            username='other-provider',
            password='StrongPass123!',
        )
        self.other_provider.profile.role = Profile.ROLE_PROVIDER
        self.other_provider.profile.save()
        self.category = ServiceCategory.objects.create(name='Plumbing')
        self.other_category = ServiceCategory.objects.create(name='Electrical')

    def create_service(self, provider=None, **overrides):
        values = {
            'provider': provider or self.provider,
            'category': self.category,
            'title': 'Kitchen Plumbing Repair',
            'description': 'Leak repair and pipe replacement.',
            'price': 500,
            'pricing_unit': Service.UNIT_VISIT,
            'city': 'Bengaluru',
            'area': 'Koramangala',
            'availability': 'Weekdays',
            'is_active': True,
        }
        values.update(overrides)
        return Service.objects.create(**values)

    def test_explore_search_matches_title_and_description(self):
        matching = self.create_service(title='Emergency Pipe Repair')
        self.create_service(title='Garden Maintenance', description='Outdoor landscaping')

        response = self.client.get(reverse('services:service_list'), {'q': 'pipe'})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, matching.title)
        self.assertNotContains(response, 'Garden Maintenance')

    def test_service_card_uses_category_photo_when_upload_is_empty(self):
        self.create_service(title='Pipe Repair Without Upload')

        response = self.client.get(reverse('services:service_list'))

        self.assertContains(response, '/static/images/explore-plumber.jpg')
        self.assertNotContains(response, 'No image')

    def test_explore_shows_one_listing_per_provider_and_category(self):
        self.create_service(title='Second Plumbing Listing')
        self.create_service(
            title='Electrical Listing',
            category=self.other_category,
        )

        response = self.client.get(reverse('services:service_list'))
        services = response.context['page_obj'].object_list
        identities = [(service.provider_id, service.category_id) for service in services]

        self.assertEqual(len(identities), len(set(identities)))
        self.assertEqual(
            sum(category_id == self.category.id for _, category_id in identities),
            1,
        )

    def test_explore_filters_by_category_location_and_price(self):
        matching = self.create_service(price=750, city='Mumbai', area='Andheri')
        self.create_service(
            title='Cheap Electrical Work',
            category=self.other_category,
            price=200,
            city='Bengaluru',
        )

        response = self.client.get(reverse('services:service_list'), {
            'category': self.category.pk,
            'city': 'Mumbai',
            'area': 'Andheri',
            'min_price': '700',
            'max_price': '800',
        })

        self.assertContains(response, matching.title)
        self.assertNotContains(response, 'Cheap Electrical Work')

    def test_explore_paginates_and_preserves_filters(self):
        for index in range(13):
            provider = User.objects.create_user(
                username=f'pagination-provider-{index}',
                password='StrongPass123!',
            )
            provider.profile.role = Profile.ROLE_PROVIDER
            provider.profile.save()
            self.create_service(
                provider=provider,
                title=f'Plumbing Service {index}',
            )

        response = self.client.get(reverse('services:service_list'), {
            'q': 'Plumbing',
            'page': 2,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].number, 2)
        self.assertContains(response, 'q=Plumbing')
        self.assertContains(response, 'page=1')

    def test_unpublished_services_are_hidden_from_explore_and_detail(self):
        unpublished = self.create_service(title='Private Draft', is_active=False)

        response = self.client.get(reverse('services:service_list'))
        self.assertNotContains(response, unpublished.title)
        detail_response = self.client.get(
            reverse('services:service_detail', kwargs={'pk': unpublished.pk})
        )
        self.assertEqual(detail_response.status_code, 404)

    def test_provider_profile_shows_only_published_services(self):
        published = self.create_service(title='Published Plumbing')
        unpublished = self.create_service(title='Unpublished Plumbing', is_active=False)

        response = self.client.get(
            reverse('accounts:provider_profile', kwargs={'username': self.provider.username})
        )

        self.assertContains(response, published.title)
        self.assertNotContains(response, unpublished.title)

    def test_provider_cannot_edit_or_delete_another_providers_service(self):
        service = self.create_service(provider=self.other_provider)
        self.client.login(username='provider', password='StrongPass123!')

        edit_response = self.client.get(
            reverse('services:service_edit', kwargs={'pk': service.pk})
        )
        delete_response = self.client.get(
            reverse('services:service_delete', kwargs={'pk': service.pk})
        )

        self.assertEqual(edit_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)

    def test_service_form_rejects_non_image_upload(self):
        upload = SimpleUploadedFile(
            'not-an-image.txt',
            b'not an image',
            content_type='text/plain',
        )
        form = ServiceForm(data={
            'category': self.category.pk,
            'title': 'Image Test Service',
            'description': 'A sufficiently detailed description.',
            'price': '100',
            'pricing_unit': Service.UNIT_VISIT,
            'city': 'Bengaluru',
            'area': 'Koramangala',
            'availability': 'Weekdays',
            'is_active': True,
        }, files={'image': upload})

        self.assertFalse(form.is_valid())
        self.assertIn('image', form.errors)
