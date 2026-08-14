from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm, PasswordChangeForm as DjangoPasswordChangeForm
from .models import CustomUser, CaregiverProfile, CaregiverDocument


class SignupForm(UserCreationForm):
    ROLE_CHOICES = [
        ('employer', 'Employer / Family'),
        ('caregiver', 'Caregiver / PSW'),
    ]

    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Choose a username'}),
    )
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'First name'}),
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'Last name'}),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '+1 (416) 000-0000'}),
    )
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.HiddenInput(),
        initial='employer',
    )
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={'placeholder': 'At least 8 characters'}),
    )
    password2 = forms.CharField(
        label='Confirm password',
        widget=forms.PasswordInput(attrs={'placeholder': 'Repeat your password'}),
    )

    class Meta:
        model = CustomUser
        fields = ('username', 'first_name', 'last_name', 'email', 'phone', 'role', 'password1', 'password2')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def clean_role(self):
        """Ensure only the two public roles can be chosen via the signup form.
        Admin accounts must be created through the Django admin or createsuperuser.
        """
        role = self.cleaned_data.get('role')
        allowed = {choice[0] for choice in self.ROLE_CHOICES}
        if role not in allowed:
            raise forms.ValidationError('Invalid role selected.')
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['username']
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data.get('phone', '')
        user.role = self.cleaned_data['role']
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    username_or_email = forms.CharField(
        label='Username or Email',
        widget=forms.TextInput(attrs={'placeholder': 'Username or email address'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter your password'}),
    )

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        self.user_cache = None

    def clean(self):
        cleaned_data = super().clean()
        username_or_email = cleaned_data.get('username_or_email')
        password = cleaned_data.get('password')

        if username_or_email and password:
            self.user_cache = authenticate(
                self.request,
                username=username_or_email,
                password=password,
            )
            if self.user_cache is None:
                raise forms.ValidationError('Invalid username/email or password.')

        return cleaned_data

    def get_user(self):
        return self.user_cache


# ──────────────────────────────────────────────────────────────
# Edit Profile forms
# ──────────────────────────────────────────────────────────────
class EditUserForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'First name'}),
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': 'Last name'}),
    )
    phone = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '+1 (416) 000-0000'}),
    )

    class Meta:
        model = CustomUser
        fields = ('first_name', 'last_name', 'phone')


class EditCaregiverProfileForm(forms.ModelForm):
    care_type = forms.MultipleChoiceField(
        choices=CaregiverProfile.CARE_TYPE_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple(),
        label='Care Types',
    )
    hourly_rate = forms.DecimalField(
        max_digits=6, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'e.g. 28.00', 'step': '0.50', 'min': '15'}),
    )
    city = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Ottawa'}),
    )
    skills = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Dementia Care, Palliative, Mobility Assist'}),
        help_text='Comma-separated list of skills',
    )

    class Meta:
        model = CaregiverProfile
        fields = ('care_type', 'hourly_rate', 'city', 'skills')

    def __init__(self, *args, **kwargs):
        instance = kwargs.get('instance')
        if instance and instance.care_type:
            # Pre-select the checkboxes from the comma-separated string
            initial = kwargs.get('initial', {})
            initial['care_type'] = instance.care_types_list
            kwargs['initial'] = initial
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Join the list back to comma-separated string
        selected = self.cleaned_data.get('care_type') or []
        instance.care_type = ','.join(selected)
        if commit:
            instance.save()
        return instance


class ProfileImageForm(forms.ModelForm):
    class Meta:
        model = CaregiverProfile
        fields = ('profile_image',)

    # Allowed MIME types and their corresponding magic-byte signatures
    _ALLOWED_MIME = {'image/jpeg', 'image/png', 'image/webp'}
    _MAGIC = {
        b'\xff\xd8\xff': 'image/jpeg',
        b'\x89PNG':      'image/png',
        b'RIFF':         'image/webp',   # RIFF????WEBP — checked below
    }

    def clean_profile_image(self):
        img = self.cleaned_data.get('profile_image')
        if not img:
            return img

        # 1. Size check
        if img.size > 5 * 1024 * 1024:
            raise forms.ValidationError('Image must be under 5 MB.')

        # 2. Extension check
        ext = img.name.rsplit('.', 1)[-1].lower() if '.' in img.name else ''
        if ext not in ('jpg', 'jpeg', 'png', 'webp'):
            raise forms.ValidationError(
                'Only JPG, PNG, or WebP images are allowed.'
            )

        # 3. Magic-byte check — peek at the first 12 bytes without
        #    consuming the stream (seek back afterwards)
        img.seek(0)
        header = img.read(12)
        img.seek(0)

        detected = None
        for magic, mime in self._MAGIC.items():
            if header[:len(magic)] == magic:
                detected = mime
                break

        # WebP needs the extra "WEBP" marker at bytes 8-12
        if detected == 'image/webp' and header[8:12] != b'WEBP':
            detected = None

        if detected not in self._ALLOWED_MIME:
            raise forms.ValidationError(
                'File does not appear to be a valid image. '
                'Please upload a JPG, PNG, or WebP file.'
            )

        return img


class BankDetailsForm(forms.ModelForm):
    bank_name = forms.CharField(
        max_length=100, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. TD Bank, RBC, Scotiabank'}),
    )
    bank_account_name = forms.CharField(
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Full name as on your account'}),
    )
    bank_account_number = forms.CharField(
        max_length=30, required=False,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. 1234567'}),
    )
    bank_transit_number = forms.CharField(
        max_length=10, required=False,
        widget=forms.TextInput(attrs={'placeholder': '5 digits, e.g. 00123'}),
    )
    bank_institution_number = forms.CharField(
        max_length=5, required=False,
        widget=forms.TextInput(attrs={'placeholder': '3 digits, e.g. 004'}),
    )

    class Meta:
        model = CaregiverProfile
        fields = ('bank_name', 'bank_account_name', 'bank_account_number',
                  'bank_transit_number', 'bank_institution_number')


# ──────────────────────────────────────────────────────────────
# Document upload form
# ──────────────────────────────────────────────────────────────

# The 5 doc types that are compulsory for verification
REQUIRED_DOC_TYPES = [
    CaregiverDocument.DOC_PSW_CERT,
    CaregiverDocument.DOC_VSC,
    CaregiverDocument.DOC_GOVERNMENT_ID,
    CaregiverDocument.DOC_FIRST_AID,
    CaregiverDocument.DOC_RESUME,
]


class DocumentUploadForm(forms.ModelForm):
    class Meta:
        model = CaregiverDocument
        fields = ('doc_type', 'file')
        widgets = {
            'doc_type': forms.Select(attrs={'class': 'doc-type-select'}),
        }

    def __init__(self, *args, uploaded_types=None, **kwargs):
        super().__init__(*args, **kwargs)
        # Remove already-uploaded required types from the dropdown.
        # Run this even when uploaded_types is empty so the empty-set
        # case is handled correctly and choices are always a plain list.
        if uploaded_types is None:
            uploaded_types = set()
        available = [
            (value, label)
            for value, label in self.fields['doc_type'].choices
            if value not in uploaded_types or value == CaregiverDocument.DOC_OTHER
        ]
        self.fields['doc_type'].choices = available


# ──────────────────────────────────────────────────────────────
# Job Posting form
# ──────────────────────────────────────────────────────────────
from .models import JobPosting

class JobPostingForm(forms.ModelForm):
    title = forms.CharField(
        max_length=120,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Weekend Respite Care'}),
    )
    city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'placeholder': 'e.g. Nepean, Ottawa'}),
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'placeholder': 'Describe the care needed, patient details, home environment, special requirements…',
            'rows': 4,
        }),
    )
    hourly_rate = forms.DecimalField(
        max_digits=6, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={'placeholder': 'e.g. 34.00', 'step': '0.50', 'min': '15'}),
    )
    hours_per_week = forms.IntegerField(
        required=False, min_value=1, max_value=168,
        widget=forms.NumberInput(attrs={'placeholder': 'e.g. 12'}),
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
    )

    class Meta:
        model = JobPosting
        fields = ('title', 'care_type', 'city', 'description',
                  'hourly_rate', 'hours_per_week', 'schedule', 'start_date')
        widgets = {
            'care_type': forms.Select(),
            'schedule':  forms.Select(),
        }


class PasswordChangeForm(DjangoPasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].widget.attrs.update({
            'placeholder': 'Enter your current password',
        })
        self.fields['new_password1'].widget.attrs.update({
            'placeholder': 'At least 8 characters',
        })
        self.fields['new_password2'].widget.attrs.update({
            'placeholder': 'Repeat your new password',
        })
