from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum
from django.db import transaction
from django.http import JsonResponse
from decimal import Decimal
import logging

from .forms import LoginForm, SignupForm, UnifiedEmployerSignupForm, EditUserForm, EditCaregiverProfileForm, DocumentUploadForm, ProfileImageForm, BankDetailsForm, PasswordChangeForm
from .models import CustomUser, CaregiverProfile, CaregiverDocument, Shift, ShiftLog, EmployerProfile, JobPosting, Notification
from GETMECARE.email_utils import (
    send_welcome_email,
    send_clock_in_email,
    send_clock_out_email,
    send_password_changed_email,
)

_profile_logger = logging.getLogger(__name__)
logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────
def redirect_for_user(user):
    if user.is_superuser or user.is_staff:
        return redirect('AdminApp:dashboard')
    if user.is_caregiver:
        return redirect('CareGiverAcc:dashboard')
    if user.is_employer:
        # Route through the dashboard so the first-job-post popup greets
        # brand-new employers on signup (dashboard decides the modal).
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
    # Families complete registration and publish their care request in one
    # atomic submit.  A failed job creation therefore never leaves an empty
    # employer account behind.
    if request.method == 'POST' and request.POST.get('role') == CustomUser.EMPLOYER:
        employer_form = UnifiedEmployerSignupForm(request.POST)
        caregiver_form = SignupForm()
        if employer_form.is_valid():
            data = employer_form.cleaned_data
            names = data['full_name'].strip().split(None, 1)
            first_name = names[0]
            last_name = names[1] if len(names) > 1 else ''
            base_username = data['email'].split('@', 1)[0][:140] or 'family'
            username = base_username
            suffix = 2
            while CustomUser.objects.filter(username=username).exists():
                username = f'{base_username[:145]}-{suffix}'
                suffix += 1
            with transaction.atomic():
                user = CustomUser.objects.create_user(
                    username=username, email=data['email'], password=data['password'],
                    first_name=first_name, last_name=last_name, phone=data['phone'],
                    role=CustomUser.EMPLOYER,
                )
                profile = EmployerProfile.objects.create(user=user)
                # A request is publicly visible immediately; activation/payment
                # happens later when a caregiver is selected over WhatsApp.
                job = JobPosting.objects.create(
                    employer=user, title='New care request', city=data['city'],
                    description=data['care_request'], care_type='other', schedule='flexible',
                    status=JobPosting.STATUS_OPEN,
                )
                payload = {
                    'user_id': user.pk, 'job_posting_id': job.pk,
                    'name': user.get_full_name(), 'email': user.email,
                    'phone': user.phone, 'city': job.city,
                    'care_request': job.description,
                }
                transaction.on_commit(lambda: _notify_new_care_request(payload))
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            try:
                send_welcome_email(user)
            except Exception:
                logger.exception('Welcome email failed for user %s', user.pk)
            messages.success(request, 'Your care request is live! Our matching coordination team has been alerted and will review candidates shortly.')
            return redirect('EmployerApp:dashboard')
        return render(request, 'Account/signup.html', {
            'form': caregiver_form, 'employer_form': employer_form, 'selected_role': 'employer',
        })

    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Auto-create CaregiverProfile when role is caregiver
            if user.is_caregiver:
                CaregiverProfile.objects.get_or_create(user=user)
            # Auto-activate employer and mark fee-exempt if fee is currently OFF
            if user.is_employer:
                from AdminApp.models import SiteSettings
                fee_on = SiteSettings.get().activation_fee_enabled
                ep, _ = EmployerProfile.objects.get_or_create(user=user)
                if not fee_on:
                    ep.is_active          = True
                    ep.fee_exempt         = True
                    ep.activation_paid_at = timezone.now()
                    ep.payment_reference  = 'free-access'
                    ep.save(update_fields=['is_active', 'fee_exempt', 'activation_paid_at', 'payment_reference'])
            login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            # Send welcome email (non-blocking — failure won't break signup)
            try:
                send_welcome_email(user)
            except Exception:
                logger.exception('Welcome email failed for user %s', user.pk)
            return redirect_for_user(user)
    else:
        form = SignupForm()

    return render(request, 'Account/signup.html', {
        'form': form, 'employer_form': UnifiedEmployerSignupForm(), 'selected_role': 'caregiver' if request.method == 'POST' else 'employer',
    })


def _notify_new_care_request(payload):
    from GETMECARE.whatsapp import notify_admin
    title = payload.get('title') or 'New care request'
    care_type = payload.get('care_type') or 'General Care'
    rate = f"${payload['hourly_rate']}/hr" if payload.get('hourly_rate') else "Flexible"
    message = (
        '🆕 NEW CARE REQUEST — LIVE ON JOB BOARD\n'
        '━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        f"Title: {title}\n"
        f"Family: {payload['name']}\n"
        f"Phone: {payload['phone']}\n"
        f"City: {payload['city']}\n"
        f"Care Type: {care_type}\n"
        f"Target Rate: {rate}\n"
        f"Details: {payload['care_request'][:400]}\n"
        f"Job ID: #{payload['job_posting_id']}\n"
        '━━━━━━━━━━━━━━━━━━━━━━━━━\n'
        'Action: Review & match caregivers in the Admin Panel.'
    )
    try:
        notify_admin(message, event='care_request_created', payload=payload)
    except Exception:
        logger.exception('New care request WhatsApp alert failed for job %s', payload['job_posting_id'])


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

    # Email notification
    try:
        send_clock_in_email(request.user, shift)
    except Exception:
        logger.exception('Clock-in email failed for shift %s', shift.pk)

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

    # Email notification
    try:
        send_clock_out_email(request.user, log.shift, log)
    except Exception:
        logger.exception('Clock-out email failed for shift %s', log.shift.pk)

    messages.success(
        request,
        f'Clocked out. You worked {log.hours_worked} hrs — '
        f'${log.amount_earned} CAD will be settled by the admin shortly.'
    )
    return redirect('CareGiverAcc:dashboard')


# ──────────────────────────────────────────────────────────────
# Edit Profile
# ──────────────────────────────────────────────────────────────

@login_required(login_url='Account:login')
def edit_profile(request):
    user = request.user
    profile = None

    # Block suspended/deactivated caregivers from editing their profile
    if user.is_caregiver:
        try:
            _prof = user.caregiver_profile
            if _prof.is_moderation_restricted:
                messages.warning(request, 'Your account is currently restricted. Please contact support.')
                return redirect('CareGiverAcc:dashboard')
        except Exception:
            pass
    profile_form = None
    image_form = None
    bank_form = None

    if user.is_caregiver:
        profile, _ = CaregiverProfile.objects.get_or_create(user=user)

    if request.method == 'POST':
        action = request.POST.get('action', 'profile')

        if action == 'image' and user.is_caregiver:
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

            # Guard: file must actually be present in the request
            if 'profile_image' not in request.FILES:
                msg = 'No file received. Please select an image and try again.'
                if is_ajax:
                    return JsonResponse({'ok': False, 'error': msg}, status=400)
                messages.error(request, msg)
                return redirect('Account:edit_profile')

            image_form = ProfileImageForm(request.POST, request.FILES, instance=profile)
            if image_form.is_valid():
                try:
                    saved_profile = image_form.save()
                    img_url = ''
                    if saved_profile.profile_image:
                        img_url = saved_profile.profile_image.url
                    if is_ajax:
                        return JsonResponse({'ok': True, 'url': img_url})
                    messages.success(request, 'Profile photo updated.')
                except Exception as exc:
                    import traceback
                    _profile_logger.error(
                        'Profile image save failed for user %s:\n%s',
                        user.pk, traceback.format_exc(),
                    )
                    user_msg = str(exc) or 'Upload failed — please try again.'
                    if is_ajax:
                        return JsonResponse({'ok': False, 'error': user_msg}, status=500)
                    messages.error(request, f'Photo upload failed: {user_msg}')
            else:
                error_msg = '; '.join(
                    str(e) for errors in image_form.errors.values() for e in errors
                )
                _profile_logger.warning(
                    'ProfileImageForm invalid for user %s: %s', user.pk, image_form.errors
                )
                if is_ajax:
                    return JsonResponse({'ok': False, 'error': error_msg or 'Invalid image.'}, status=400)
                messages.error(request, error_msg or 'Photo upload failed. Use JPG or PNG under 5 MB.')
            if not is_ajax:
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


# ──────────────────────────────────────────────────────────────
# Password Change
# ──────────────────────────────────────────────────────────────
@login_required(login_url='Account:login')
def password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Your password has been changed successfully.')
            try:
                send_password_changed_email(request.user)
            except Exception:
                logger.exception('Password changed email failed for user %s', request.user.pk)
            return redirect('Account:password_change')
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'Account/password_change_form.html', {
        'form': form,
    })


# ──────────────────────────────────────────────────────────────
# In-app notification center (bell dropdown & clear notification)
# ──────────────────────────────────────────────────────────────
def ensure_user_notifications(user):
    """
    Ensure user has realistic, helpful notifications seeded if they have none,
    reflecting their account role and current platform status.
    """
    if not user or not user.is_authenticated:
        return
    if user.notifications.exists():
        return

    if user.is_caregiver:
        profile = getattr(user, 'caregiver_profile', None)
        if profile and profile.status == CaregiverProfile.STATUS_ACTIVE:
            Notification.send(
                user=user,
                title='Account Verified & Active',
                message='Your caregiver profile is verified and active. Families and employers across Ontario can view your profile and book shifts.',
                notification_type=Notification.TYPE_ACCOUNT,
                link='/caregiver-acc/',
            )
        else:
            Notification.send(
                user=user,
                title='Complete Your Documents',
                message='Welcome to GetMeCare! Upload your police check (VSC) and certifications to complete your activation and begin accepting shifts.',
                notification_type=Notification.TYPE_DOC,
                link='/caregiver-acc/documents/',
            )

        upcoming_shifts = getattr(user, 'shifts_as_caregiver', None)
        shift_count = upcoming_shifts.count() if upcoming_shifts else 0
        if shift_count > 0:
            Notification.send(
                user=user,
                title='Upcoming Schedule',
                message=f'You have {shift_count} shift(s) scheduled on your calendar.',
                notification_type=Notification.TYPE_SHIFT,
                link='/caregiver-acc/my-schedule/',
            )

        Notification.send(
            user=user,
            title='GetMeCare Live Support',
            message='Need assistance or have questions about a shift? Live administrative support is available 24/7 directly from your dashboard.',
            notification_type=Notification.TYPE_MESSAGE,
            link='/chatbot/support/',
        )
    elif user.is_employer:
        Notification.send(
            user=user,
            title='Welcome to GetMeCare Ontario',
            message='Browse pre-vetted Personal Support Workers (PSWs) in your local area with verified credentials.',
            notification_type=Notification.TYPE_INFO,
            link='/employer/dashboard/',
        )


@login_required(login_url='Account:login')
def get_notifications(request):
    """Return JSON serialized notifications for the current logged-in user."""
    ensure_user_notifications(request.user)
    notifs = request.user.notifications.all()[:20]
    unread_count = request.user.notifications.filter(is_read=False).count()
    data = [
        {
            'id': n.id,
            'title': n.title,
            'message': n.message,
            'type': n.notification_type,
            'link': n.link,
            'is_read': n.is_read,
            'created_at': n.created_at.strftime('%b %d, %H:%M'),
        }
        for n in notifs
    ]
    return JsonResponse({'ok': True, 'unread_count': unread_count, 'notifications': data})


@login_required(login_url='Account:login')
def clear_notifications(request):
    """
    Clear notifications for the user:
    Marks all notifications as read, and optionally removes them if requested.
    """
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    delete_all = request.POST.get('delete_all') == '1' or request.headers.get('X-Action') == 'delete'
    if delete_all:
        cleared_count = request.user.notifications.all().delete()[0]
    else:
        cleared_count = request.user.notifications.filter(is_read=False).update(is_read=True)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
        return JsonResponse({'ok': True, 'unread_count': 0, 'cleared_count': cleared_count})

    messages.success(request, 'Notifications cleared.')
    return redirect(request.META.get('HTTP_REFERER') or 'home')


@login_required(login_url='Account:login')
def dismiss_notification(request, notif_id):
    """Dismiss/remove a single notification."""
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required'}, status=405)

    n = get_object_or_404(Notification, id=notif_id, user=request.user)
    n.delete()
    unread_count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'ok': True, 'unread_count': unread_count})


@login_required(login_url='Account:login')
def update_user_whatsapp(request):
    """
    Save WhatsApp number to request.user.phone for any authenticated user
    (both Caregivers and Employers).
    """
    if request.method != 'POST':
        return redirect('home')

    raw = (request.POST.get('phone') or request.POST.get('whatsapp') or '').strip()
    from GETMECARE.whatsapp import whatsapp_digits, whatsapp_link
    digits = whatsapp_digits(raw)

    if not digits:
        error = 'Please enter a valid phone number (at least 7 digits).'
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'ok': False, 'error': error}, status=400)
        messages.error(request, error)
        return redirect(request.META.get('HTTP_REFERER') or 'home')

    request.user.phone = digits
    request.user.save(update_fields=['phone'])
    request.session['dismissed_whatsapp_modal'] = True

    wa_link = whatsapp_link(digits)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': True, 'wa_link': wa_link, 'phone': digits})

    messages.success(request, 'Your WhatsApp number has been updated successfully.')
    return redirect(request.META.get('HTTP_REFERER') or 'home')


@login_required(login_url='Account:login')
def dismiss_whatsapp_modal(request):
    """Allow user to dismiss the WhatsApp modal for the current session."""
    if request.method == 'POST':
        request.session['dismissed_whatsapp_modal'] = True
        return JsonResponse({'ok': True})
    return JsonResponse({'ok': False, 'error': 'POST required'}, status=400)

