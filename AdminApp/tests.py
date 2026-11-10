from django.test import TestCase

from django.urls import reverse

from Account.models import CustomUser, JobPosting


class DeleteJobRequestTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user(
            username='admin',
            password='test-password-123',
            is_staff=True,
        )
        self.employer = CustomUser.objects.create_user(
            username='employer',
            password='test-password-123',
            role=CustomUser.EMPLOYER,
        )
        self.job = JobPosting.objects.create(
            employer=self.employer,
            title='In-home care',
            care_type='senior_elder',
            city='Ottawa',
        )
        self.url = reverse('AdminApp:delete_job_request', args=[self.job.pk])

    def test_staff_can_delete_care_request_with_post(self):
        self.client.force_login(self.admin)

        response = self.client.post(self.url)

        self.assertRedirects(response, reverse('AdminApp:job_requests'))
        self.assertFalse(JobPosting.objects.filter(pk=self.job.pk).exists())
        self.assertTrue(CustomUser.objects.filter(pk=self.employer.pk).exists())

    def test_get_does_not_delete_care_request(self):
        self.client.force_login(self.admin)

        response = self.client.get(self.url)

        self.assertRedirects(response, reverse('AdminApp:job_requests'))
        self.assertTrue(JobPosting.objects.filter(pk=self.job.pk).exists())

    def test_non_staff_cannot_delete_care_request(self):
        self.client.force_login(self.employer)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('Account:login'))
        self.assertTrue(JobPosting.objects.filter(pk=self.job.pk).exists())
