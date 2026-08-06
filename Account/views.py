from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal

from .forms import LoginForm, SignupForm, EditUserForm, EditCaregiverProfileForm, DocumentUploadForm, ProfileImageForm, BankDetailsForm
from .models import CustomUser, CaregiverProfile, CaregiverDocument, Shift, ShiftLog


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def redirect_for_user(user):
    if user.is_superuser or user.is_staff:
        return redirect('AdminApp:dashboard')
    if user.is_caregiver:
        return redirect('CareGiverAcc:dashboard')
    if user.is_employer:
        return redirect('EmployerApp:dashboard')
    return redirect('home')


def caregiver_required(view_func):
    """Decorator: must be logged in AND have caregiver role."""
    @login_required(login_url='Account:login')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_caregiver:
            messages.error(request, 'Access denied. Caregiver account required.')
            return redirect('Account:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


# ──────────────────────────────────────────────────────────────
# Auth views
# ──────────────────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect_for_user(request.user)

    if request.method == 'POST':
        form = LoginForm(request, request.POST)
        if form.is_valid():
            login(request, form.get_user())
            return redirect_for_user(form.get_user())
    else:
        form = LoginForm()

    return render(request, 'Account/login.html', {'form': form})


def signup(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Auto-create CaregiverProfile when role is caregiver
            if user.is_caregiver:
                CaregiverProfile.objects.get_or_create(user=user)
            login(request, user)
            return redirect_for_user(user)
    else:
        form = SignupForm()

    return render(request, 'Account/signup.html', {'form': form})


# ──────────────────────────────────────────────────────────────
# Dashboard: Admin  (legacy URL — forwards to AdminApp)
# ──────────────────────────────────────────────────────────────
@login_required(login_url='Account:login')
def admin_dashboard(request):
    if not (request.user.is_staff or request.user.is_superuser):
        messages.error(request, 'Access denied.')
        return redirect('Account:login')
    return redirect('AdminApp:dashboard')


# ──────────────────────────────────────────────────────────────
# Dashboard: Employer  (legacy URL — forwards to EmployerApp)
# ──────────────────────────────────────────────────────────────
@login_required(login_url='Account:login')
def employer_dashboard(request):
    if not request.user.is_employer:
        messages.error(request, 'Access denied. Employer account required.')
        return redirect('Account:login')
    return redirect('EmployerApp:dashboard')


# ──────────────────────────────────────────────────────────────
# Dashboard: Caregiver  (legacy URL — forwards to CareGiverAcc)
# ──────────────────────────────────────────────────────────────
@caregiver_required
def caregiver_dashboard(request):
    """Legacy URL — forwards to CareGiverAcc app dashboard."""
    return redirect('CareGiverAcc:dashboard')


# ──────────────────────────────────────────────────────────────
# Clock-in / Clock-out actions
# ──────────────────────────────────────────────────────────────
@caregiver_required
def clock_in(request):
    if request.method != 'POST':
        return redirect('CareGiverAcc:dashboard')

    shift_id = request.POST.get('shift_id')
    shift = get_object_or_404(
        Shift,
        pk=shift_id,
        caregiver=request.user,
        status=Shift.STATUS_SCHEDULED,
    )

    # Prevent double clock-in
    if ShiftLog.objects.filter(shift=shift, clock_in_time__isnull=False).exists():
        messages.warning(request, 'You have already clocked in for this shift.')
        return redirect('CareGiverAcc:dashboard')

    ShiftLog.objects.create(shift=shift, clock_in_time=timezone.now())
    shift.status = Shift.STATUS_IN_PROGRESS
    shift.save(update_fields=['status'])

    messages.success(request, f'Clocked in for Shift #{shift.pk}. Have a great shift!')
    return redirect('CareGiverAcc:dashboard')


@caregiver_required
def clock_out(request):
    if request.method != 'POST':
        return redirect('CareGiverAcc:dashboard')

    try:
        log = (
            ShiftLog.objects
            .select_related('shift')
            .get(
                shift__caregiver=request.user,
                shift__status=Shift.STATUS_IN_PROGRESS,
                clock_in_time__isnull=False,
                clock_out_time__isnull=True,
            )
        )
    except ShiftLog.DoesNotExist:
        messages.error(request, 'No active shift found to clock out of.')
        return redirect('CareGiverAcc:dashboard')

    log.clock_out_time = timezone.now()
    log.calculate_earnings()
    log.save()

    log.shift.status = Shift.STATUS_COMPLETED
    log.shift.save(update_fields=['status'])

    messages.success(
        request,
        f'Clocked out. You worked {log.hours_worked} hrs — '
        f'${log.amount_earned} CAD will be credited after admin settlement.'
    )
    return redirect('CareGiverAcc:dashboard')


# ──────────────────────────────────────────────────────────────
# Edit Profile
# ──────────────────────────────────────────────────────────────
@login_required(login_url='Account:login')
def edit_profile(request):
    from Account.forms import ProfileImageForm, BankDetailsForm
    user = request.user
    profile = None
    profile_form = None
    image_form = None
    bank_form = None

    if user.is_caregiver:
        profile, _ = CaregiverProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        action = request.POST.get('action', 'profile')

        if action == 'image' and user.is_caregiver:
            image_form = ProfileImageForm(request.POST, request.FILES, instance=profile)
            if image_form.is_valid():
                image_form.save()
                messages.success(request, 'Profile photo updated.')
            else:
                messages.error(request, 'Photo upload failed. Use JPG or PNG under 5 MB.')
            return redirect('Account:edit_profile')

        elif action == 'bank' and user.is_caregiver:
            bank_form = BankDetailsForm(request.POST, instance=profile)
            if bank_form.is_valid():
                bank_form.save()
                messages.success(request, 'Bank details saved.')
            else:
                messages.error(request, 'Please fix the errors below.')
            return redirect('Account:edit_profile')

        else:  # default: main profile form
            user_form = EditUserForm(request.POST, instance=user)
            if user.is_caregiver:
                profile_form = EditCaregiverProfileForm(request.POST, instance=profile)
                if user_form.is_valid() and profile_form.is_valid():
                    user_form.save()
                    profile_form.save()
                    messages.success(request, 'Profile updated successfully.')
                    return redirect('Account:edit_profile')
            else:
                if user_form.is_valid():
                    user_form.save()
                    messages.success(request, 'Profile updated successfully.')
                    return redirect('Account:edit_profile')
    else:
        user_form = EditUserForm(instance=user)
        if user.is_caregiver:
            profile_form = EditCaregiverProfileForm(instance=profile)
            image_form   = ProfileImageForm(instance=profile)
            bank_form    = BankDetailsForm(instance=profile)

    # Build sidebar context for caregiver base template
    ctx = {}
    if user.is_caregiver:
        from CareGiverAcc.views import _sidebar_context
        ctx = _sidebar_context(user)

    ctx.update({
        'user_form':    user_form,
        'profile_form': profile_form,
        'image_form':   image_form,
        'bank_form':    bank_form,
        'profile':      profile,
    })
    return render(request, 'Account/edit-profile.html', ctx)


# ──────────────────────────────────────────────────────────────
# Documents / Verification
# ──────────────────────────────────────────────────────────────
@caregiver_required
def documents(request):
    user = request.user
    profile, _ = CaregiverProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.user = user
            doc.save()
            messages.success(request, f'{doc.get_doc_type_display()} uploaded successfully. It will be reviewed shortly.')
            return redirect('Account:documents')
        else:
            messages.error(request, 'Upload failed. Please check the file and try again.')
    else:
        form = DocumentUploadForm()

    user_docs = CaregiverDocument.objects.filter(user=user)

    # Build checklist status
    uploaded_types = set(user_docs.values_list('doc_type', flat=True))
    required_docs = [
        CaregiverDocument.DOC_GOVERNMENT_ID,
        CaregiverDocument.DOC_PSW_CERT,
        CaregiverDocument.DOC_VSC,
    ]
    optional_docs = [
        CaregiverDocument.DOC_FIRST_AID,
        CaregiverDocument.DOC_RESUME,
    ]

    return render(request, 'Account/documents.html', {
        'form': form,
        'user_docs': user_docs,
        'profile': profile,
        'uploaded_types': uploaded_types,
        'required_docs': required_docs,
        'optional_docs': optional_docs,
    })


# ──────────────────────────────────────────────────────────────
# Logout
# ──────────────────────────────────────────────────────────────
@login_required(login_url='Account:login')
def logout_view(request):
    logout(request)
    return redirect('Account:login')
