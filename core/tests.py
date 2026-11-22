from unittest.mock import patch
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core import mail
from core.models import ContactMessage


class ContactEmailFunctionalityTest(TestCase):
    @override_settings(ADMIN_EMAIL='admin@nearnest.local', DEFAULT_FROM_EMAIL='NearNest <noreply@nearnest.local>')
    def test_contact_email_sent_with_details_and_reply_to(self):
        """Verify email delivery to admin with user details and reply_to set to sender."""
        payload = {
            'name': 'Rahul Sharma',
            'email': 'rahul@example.com',
            'subject': 'Service Inquiry in Mumbai',
            'message': 'Hello, I would like to inquire about booking a carpenter in my area.',
        }
        response = self.client.post(reverse('core:contact'), payload, follow=True)
        self.assertEqual(response.status_code, 200)

        # 1 email sent to outbox
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]

        # Check recipient is admin
        self.assertIn('admin@nearnest.local', sent_email.to)

        # Check Reply-To is user's email
        self.assertEqual(sent_email.reply_to, ['rahul@example.com'])

        # Check subject
        self.assertIn('Service Inquiry in Mumbai', sent_email.subject)

        # Check email body contains all form fields
        self.assertIn('Rahul Sharma', sent_email.body)
        self.assertIn('rahul@example.com', sent_email.body)
        self.assertIn('Service Inquiry in Mumbai', sent_email.body)
        self.assertIn('Hello, I would like to inquire about booking a carpenter in my area.', sent_email.body)

        # Check message is stored in database
        self.assertTrue(ContactMessage.objects.filter(email='rahul@example.com').exists())

        # Check success message in response
        self.assertContains(response, 'Thank you! Your message has been sent successfully.')

    def test_contact_duplicate_prevention(self):
        """Submitting the exact same message within 2 minutes should be prevented."""
        payload = {
            'name': 'Pooja Verma',
            'email': 'pooja@example.com',
            'subject': 'Cleaning question',
            'message': 'Is deep cleaning service available on Sundays?',
        }

        # First submission succeeds
        res1 = self.client.post(reverse('core:contact'), payload, follow=True)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(ContactMessage.objects.filter(email='pooja@example.com').count(), 1)
        self.assertEqual(len(mail.outbox), 1)

        # Second submission immediately with same data should be blocked as duplicate
        res2 = self.client.post(reverse('core:contact'), payload, follow=True)
        self.assertEqual(res2.status_code, 200)
        self.assertContains(res2, 'You have already submitted this exact message recently.')
        # Database count remains 1
        self.assertEqual(ContactMessage.objects.filter(email='pooja@example.com').count(), 1)
        # No second email sent
        self.assertEqual(len(mail.outbox), 1)

    def test_contact_form_validation_rejects_whitespace(self):
        """Whitespace only inputs must fail validation."""
        payload = {
            'name': '   ',
            'email': 'test@example.com',
            'subject': '   ',
            'message': '          ',
        }
        response = self.client.post(reverse('core:contact'), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ContactMessage.objects.filter(email='test@example.com').exists())
        self.assertEqual(len(mail.outbox), 0)

    @patch('core.views.EmailMessage.send')
    def test_contact_email_failure_shows_error_message(self, mock_send):
        """If SMTP delivery raises an exception, an error message is shown to user."""
        mock_send.side_effect = Exception("SMTP Connection Failed")
        payload = {
            'name': 'Amit Kumar',
            'email': 'amit@example.com',
            'subject': 'Urgent Plumbing Issue',
            'message': 'Need someone today for a leaking pipe.',
        }
        response = self.client.post(reverse('core:contact'), payload, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sorry, an error occurred while delivering your message.')
