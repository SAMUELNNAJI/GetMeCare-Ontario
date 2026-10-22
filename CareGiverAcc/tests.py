from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from Account.models import CaregiverProfile
from GETMECARE.whatsapp import whatsapp_digits, whatsapp_link

User = get_user_model()


class WhatsappHelperTests(TestCase):
    """The shared validation rule must be identical everywhere."""

    def test_valid_numbers(self):
        self.assertEqual(whatsapp_digits('4165550123'), '4165550123')
        self.assertEqual(whatsapp_digits('(416) 555-0123'), '4165550123')
        self.assertEqual(whatsapp_digits('+1 416 555 0123'), '14165550123')

    def test_invalid_numbers(self):
        self.assertEqual(whatsapp_digits(''), '')
        self.assertEqual(whatsapp_digits(None), '')
        self.assertEqual(whatsapp_digits('12345'), '')   # < 7 digits
        self.assertEqual(whatsapp_digits('abc'), '')

    def test_link_built_from_same_rule(self):
        self.assertEqual(whatsapp_link('4165550123'), 'https://wa.me/4165550123')
        self.assertEqual(whatsapp_link('12345'), '')



class UpdateWhatsappEndpointTests(TestCase):
    """Caregiver-only endpoint that persists the WhatsApp number."""

    def setUp(self):
        self.caregiver = User.objects.create_user(
            username='cg', password='pw12345!', role=User.CAREGIVER,
            first_name='Ada', phone='',
        )
        CaregiverProfile.objects.create(user=self.caregiver, status=CaregiverProfile.STATUS_ACTIVE)
        self.employer = User.objects.create_user(
            username='emp', password='pw12345!', role=User.EMPLOYER, phone='',
        )
        self.url = reverse('CareGiverAcc:update_whatsapp')

    def test_anonymous_is_redirected_to_login(self):
        res = self.client.post(self.url, {'phone': '4165550123'})
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res['Location'])
        self.caregiver.refresh_from_db()
        self.assertEqual(self.caregiver.phone, '')

    def test_employer_is_denied(self):
        self.client.force_login(self.employer)
        res = self.client.post(self.url, {'phone': '4165550123'})
        self.assertEqual(res.status_code, 302)
        self.employer.refresh_from_db()
        self.assertEqual(self.employer.phone, '')

    def test_ajax_valid_number_saves_normalised_digits(self):
        self.client.force_login(self.caregiver)
        res = self.client.post(
            self.url, {'phone': '(416) 555-0123'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['phone'], '4165550123')
        self.assertEqual(data['wa_link'], 'https://wa.me/4165550123')
        self.caregiver.refresh_from_db()
        self.assertEqual(self.caregiver.phone, '4165550123')

    def test_ajax_invalid_number_is_rejected(self):
        self.client.force_login(self.caregiver)
        res = self.client.post(
            self.url, {'phone': '123'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json()['ok'])
        self.assertIn('error', res.json())
        self.caregiver.refresh_from_db()
        self.assertEqual(self.caregiver.phone, '')

    def test_non_ajax_valid_number_redirects(self):
        self.client.force_login(self.caregiver)
        res = self.client.post(self.url, {'phone': '4165550123'})
        self.assertEqual(res.status_code, 302)
        self.caregiver.refresh_from_db()
        self.assertEqual(self.caregiver.phone, '4165550123')

    def test_get_is_redirected(self):
        self.client.force_login(self.caregiver)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 302)

class CaregiverPublicPageWhatsappTests(TestCase):
    """The public caregiver page and browse page must not display a WhatsApp button."""

    def setUp(self):
        self.caregiver = User.objects.create_user(
            username='cg2', password='pw12345!', role=User.CAREGIVER,
            first_name='Ada', phone='4165550123',
        )
        self.profile = CaregiverProfile.objects.create(
            user=self.caregiver, status=CaregiverProfile.STATUS_ACTIVE,
            city='Toronto', hourly_rate=30,
        )
        self.employer = User.objects.create_user(
            username='emp2', password='pw12345!', role=User.EMPLOYER, phone='',
        )

    def test_no_whatsapp_button_on_browse_anonymous(self):
        res = self.client.get(reverse('browse'))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'https://wa.me/')
        self.assertNotContains(res, 'fa-whatsapp')

    def test_no_whatsapp_button_on_browse_employer(self):
        self.client.force_login(self.employer)
        res = self.client.get(reverse('browse'))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'https://wa.me/')
        self.assertNotContains(res, 'fa-whatsapp')

    def test_no_whatsapp_button_on_caregiver_profile_anonymous(self):
        res = self.client.get(reverse('caregiver_profile', args=[self.profile.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'https://wa.me/')
        self.assertNotContains(res, 'fa-whatsapp')

    def test_no_whatsapp_button_on_caregiver_profile_employer(self):
        self.client.force_login(self.employer)
        res = self.client.get(reverse('caregiver_profile', args=[self.profile.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertNotContains(res, 'https://wa.me/')
        self.assertNotContains(res, 'fa-whatsapp')





