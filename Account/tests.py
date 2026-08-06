from django.test import TestCase
from django.urls import reverse

from .models import CustomUser


class LoginViewTests(TestCase):
    def test_valid_employer_login_redirects_to_employer_dashboard(self):
        CustomUser.objects.create_user(
            username='family@example.com',
            email='family@example.com',
            password='safe-password-123',
            role=CustomUser.EMPLOYER,
        )

        response = self.client.post(
            reverse('Account:login'),
            {'email': 'family@example.com', 'password': 'safe-password-123'},
        )

        self.assertRedirects(response, reverse('Account:employer_dashboard'))
