from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, CaregiverProfile, CaregiverDocument


class SignupForm(UserCreationForm):
    ROLE_CHOICES = [
        ('employer', 'Employer / Family'),
        ('caregiver', 'Caregiver / PSW'),
    ]

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
        fields = ('first_name', 'last_name', 'email', 'phone', 'role', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise forms.ValidationError('An account with this email already exists.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = self.cleaned_data['email']
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone = self.cleaned_data.get('phone', '')
        user.role = self.cleaned_data['role']
        if commit:
            user.save()
        return user


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'placeholder': 'you@example.com'}),
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
        email = cleaned_data.get('email')
        password = cleaned_data.get('password')

        if email and password:
            self.user_cache = authenticate(
                self.request,
                username=email,
                password=password,
            )
            if self.user_cache is None:
                raise forms.ValidationError('Invalid email address or password.')

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
        fields = ('hourly_rate', 'city', 'skills')


class ProfileImageForm(forms.ModelForm):
    class Meta:
        model = CaregiverProfile
        fields = ('profile_image',)

    def clean_profile_image(self):
        img = self.cleaned_data.get('profile_image')
        if img:
            if img.size > 5 * 1024 * 1024:
                raise forms.ValidationError('Image must be under 5 MB.')
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
