from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from .forms import ProfileImageForm
from .models import CustomUser, CaregiverProfile


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


class SignupMathChallengeTests(TestCase):
    def setUp(self):
        self.signup_url = reverse('Account:signup')

    def _math_payload(self, response):
        left, right = response.context['math_question'].split(' + ')
        return {
            'math_answer': str(int(left) + int(right)),
            'math_token': response.context['math_token'],
        }

    def test_employer_signup_requires_correct_math_answer(self):
        self.client.get(self.signup_url)
        data = {
            'role': CustomUser.EMPLOYER,
            'full_name': 'Test Family',
            'email': 'family@example.com',
            'password': 'Safe-password-123!',
            'phone': '+1 416 555 0100',
            'city': 'Toronto',
            'care_request': 'Looking for weekday companionship.',
        }

        rejected = self.client.post(self.signup_url, {**data, 'math_answer': 'wrong'})

        self.assertEqual(rejected.status_code, 200)
        self.assertTrue(rejected.context['math_error'])
        self.assertFalse(CustomUser.objects.filter(email=data['email']).exists())

        accepted = self.client.post(
            self.signup_url,
            {**data, **self._math_payload(rejected)},
        )

        self.assertRedirects(accepted, reverse('EmployerApp:dashboard'), fetch_redirect_response=False)
        self.assertTrue(CustomUser.objects.filter(email=data['email']).exists())

    @patch('Account.views.send_welcome_email')
    def test_caregiver_signup_requires_correct_math_answer(self, _send_welcome_email):
        response = self.client.get(f'{self.signup_url}?role=caregiver')
        data = {
            'role': CustomUser.CAREGIVER,
            'first_name': 'Care',
            'last_name': 'Giver',
            'username': 'caregiver_test',
            'email': 'caregiver@example.com',
            'phone': '+1 416 555 0101',
            'password1': 'Safe-password-123!',
            'password2': 'Safe-password-123!',
        }

        rejected = self.client.post(
            self.signup_url,
            {**data, 'math_answer': 'wrong'},
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertTrue(rejected.context['math_error'])
        self.assertFalse(CustomUser.objects.filter(email=data['email']).exists())

        accepted = self.client.post(
            self.signup_url,
            {**data, **self._math_payload(rejected)},
        )

        self.assertRedirects(accepted, reverse('CareGiverAcc:dashboard'), fetch_redirect_response=False)
        self.assertTrue(CustomUser.objects.filter(email=data['email']).exists())

    def test_math_answer_is_required_and_cannot_be_reused(self):
        response = self.client.get(self.signup_url)
        data = {
            'role': CustomUser.EMPLOYER,
            'full_name': 'Test Family',
            'email': 'family@example.com',
            'password': 'Safe-password-123!',
            'phone': '+1 416 555 0100',
            'city': 'Toronto',
            'care_request': 'Looking for weekday companionship.',
        }
        answer = self._math_payload(response)

        rejected = self.client.post(self.signup_url, data)
        self.assertTrue(rejected.context['math_error'])

        replayed = self.client.post(
            self.signup_url,
            {**data, **answer},
        )
        self.assertTrue(replayed.context['math_error'])
        self.assertFalse(CustomUser.objects.filter(email=data['email']).exists())


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
_JPEG_MAGIC = b'\xff\xd8\xff'
_PNG_MAGIC  = b'\x89PNG\r\n\x1a\n'
_WEBP_MAGIC = b'RIFF\x00\x00\x00\x00WEBP'  # 12 bytes; size field is don't-care


def _make_uploaded_file(content: bytes, name: str, content_type: str = 'image/jpeg'):
    """Return a SimpleUploadedFile with the given raw bytes."""
    return SimpleUploadedFile(name, content, content_type=content_type)


def _make_form_with_file(uploaded_file, profile):
    """Return an unbound ProfileImageForm with cleaned_data pre-populated.

    Django's ImageField runs Pillow validation during is_valid(), which rejects
    synthetic test bytes that are not actual valid images. We bypass that by
    injecting cleaned_data directly so that only our custom clean_profile_image
    logic is exercised, which is the unit under test.
    """
    form = ProfileImageForm(data={}, files={}, instance=profile)
    form.cleaned_data = {'profile_image': uploaded_file}
    return form


# ──────────────────────────────────────────────────────────────
# Test class
# ──────────────────────────────────────────────────────────────
class ProfileImageFormTests(TestCase):
    """Example-based unit tests for ProfileImageForm.clean_profile_image.

    Validates: Requirements 3.1, 3.2, 3.3, 3.4
    """

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            username='caregiver_test',
            email='caregiver@example.com',
            password='test-pass-123',
            role=CustomUser.CAREGIVER,
        )
        self.profile = CaregiverProfile.objects.create(user=self.user)

    # ── Tests 1–3: valid formats accepted ────────────────────

    def test_valid_jpeg_is_accepted(self):
        """Valid JPEG (correct magic bytes + .jpg extension, < 5 MB) must not raise."""
        content = _JPEG_MAGIC + b'\x00' * 1024  # small payload
        f = _make_uploaded_file(content, 'photo.jpg', 'image/jpeg')
        form = _make_form_with_file(f, self.profile)
        result = form.clean_profile_image()
        self.assertIsNotNone(result)

    def test_valid_png_is_accepted(self):
        """Valid PNG (magic bytes + .png extension) must not raise."""
        content = _PNG_MAGIC + b'\x00' * 1024
        f = _make_uploaded_file(content, 'photo.png', 'image/png')
        form = _make_form_with_file(f, self.profile)
        result = form.clean_profile_image()
        self.assertIsNotNone(result)

    def test_valid_webp_is_accepted(self):
        """Valid WebP (RIFF....WEBP magic bytes + .webp extension) must not raise."""
        content = _WEBP_MAGIC + b'\x00' * 1024
        f = _make_uploaded_file(content, 'photo.webp', 'image/webp')
        form = _make_form_with_file(f, self.profile)
        result = form.clean_profile_image()
        self.assertIsNotNone(result)

    # ── Tests 4–5: disallowed extensions rejected ─────────────

    def test_gif_extension_rejected(self):
        """.gif extension must be rejected even if magic bytes look like JPEG."""
        content = _JPEG_MAGIC + b'\x00' * 1024
        f = _make_uploaded_file(content, 'photo.gif', 'image/gif')
        form = _make_form_with_file(f, self.profile)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            form.clean_profile_image()

    def test_bmp_extension_rejected(self):
        """.bmp extension must be rejected."""
        content = _JPEG_MAGIC + b'\x00' * 1024
        f = _make_uploaded_file(content, 'photo.bmp', 'image/bmp')
        form = _make_form_with_file(f, self.profile)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            form.clean_profile_image()

    # ── Test 6: invalid magic bytes rejected ──────────────────

    def test_invalid_magic_bytes_rejected(self):
        """File whose magic bytes are all zeros (not JPEG/PNG/WebP) must be rejected."""
        content = b'\x00' * 1024
        f = _make_uploaded_file(content, 'photo.jpg', 'image/jpeg')
        form = _make_form_with_file(f, self.profile)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            form.clean_profile_image()

    # ── Tests 7–8: size boundary ──────────────────────────────

    def test_file_exactly_at_size_limit_is_accepted(self):
        """File of exactly 5,242,880 bytes with valid JPEG magic bytes must be accepted."""
        limit = 5 * 1024 * 1024  # 5,242,880 bytes
        content = _JPEG_MAGIC + b'\x00' * (limit - len(_JPEG_MAGIC))
        self.assertEqual(len(content), limit)
        f = _make_uploaded_file(content, 'photo.jpg', 'image/jpeg')
        form = _make_form_with_file(f, self.profile)
        result = form.clean_profile_image()
        self.assertIsNotNone(result)

    def test_file_one_byte_over_limit_is_rejected(self):
        """File of 5,242,881 bytes (one over the limit) with valid JPEG magic bytes must be rejected."""
        over_limit = 5 * 1024 * 1024 + 1  # 5,242,881 bytes
        content = _JPEG_MAGIC + b'\x00' * (over_limit - len(_JPEG_MAGIC))
        self.assertEqual(len(content), over_limit)
        f = _make_uploaded_file(content, 'photo.jpg', 'image/jpeg')
        form = _make_form_with_file(f, self.profile)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            form.clean_profile_image()

    # ── Test 9: AJAX POST with no file returns HTTP 400 ───────

    def test_ajax_post_with_no_file_returns_400(self):
        """AJAX POST to edit_profile with action=image and no file returns HTTP 400 with {ok: false}."""
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('Account:edit_profile'),
            {'action': 'image'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['ok'])
