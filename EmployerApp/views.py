from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
import datetime
import json
import logging
from decimal import Decimal

from Account.models import Shift, ShiftLog, EmployerProfile, JobPosting, BookingProposal, EmployerPayment, Dispute
from Account.forms import JobPostingForm
from EmployerApp import stripe_payments
from GETMECARE.email_utils import (
    send_shift_payment_employer_email,
    send_shift_payment_caregiver_email,
    send_activation_confirmation_email,
    send_dispute_submitted_admin_email,
    send_dispute_resolved_employer_email,
    send_job_posted_caregivers_email,
)

logger = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _employer_needs_activation(profile) -> bool:
    """
    True when this employer still needs to pay/be activated.
    Returns False (i.e. skip the gate) when:
      - the fee is currently OFF (SiteSettings), OR
      - the employer is fee-exempt (registered when fee was off), OR
      - the employer has already paid / been manually activated
    """
    if profile.is_active or profile.fee_exempt:
        return False
    from AdminApp.models import SiteSettings
    return SiteSettings.get().activation_fee_enabled


def employer_required(view_func):
    """Decorator: must be logged in AND have employer role."""
    @login_required(login_url='Account:login')
    def wrapper(request, *args, **kwargs):
        if not request.user.is_employer:
            messages.error(request, 'Access denied. Employer account required.')
            return redirect('Account:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def employer_moderation_check(view_func):
    """
    Decorator: redirect suspended/deactivated employers to dashboard,
    where the lockout banner is shown. Only the dashboard itself and
    the support chat are allowed through.
    """
    @login_required(login_url='Account:login')
    def wrapper(request, *args, **kwargs):
        if request.user.is_employer:
            profile = EmployerProfile.objects.filter(user=request.user).first()
            if profile and profile.is_moderation_restricted:
                messages.warning(
                    request,
                    'Your account is currently restricted. '
                    'Please use the support chat to contact us.'
                )
                return redirect('EmployerApp:dashboard')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def _employer_ctx(user):
    """Shared context for base_employer.html sidebar."""
    profile, _ = EmployerProfile.objects.get_or_create(user=user)
    total_completed = Shift.objects.filter(
        employer=user, status=Shift.STATUS_COMPLETED
    ).count()
    open_jobs = JobPosting.objects.filter(
        employer=user, status=JobPosting.STATUS_OPEN
    ).count()
    unseen_payments = EmployerPayment.objects.filter(
        employer=user, is_seen=False
    ).count()
    return {
        'emp_profile':            profile,
        'is_activated':           profile.is_active or profile.fee_exempt or not __import__('AdminApp.models', fromlist=['SiteSettings']).SiteSettings.get().activation_fee_enabled,
        'total_completed':        total_completed,
        'open_jobs_count':        open_jobs,
        'unseen_payments':        unseen_payments,
        'account_status':         profile.account_status,
        'account_status_reason':  profile.status_reason,
        'is_moderation_restricted': profile.is_moderation_restricted,
    }


# ────────────────────────────────────────────────────────────
@employer_required
def dashboard(request):
    user = request.user
    ctx  = _employer_ctx(user)

    q = request.GET.get('q', '').strip()

    scheduled_qs = Shift.objects.filter(
        employer=user, status=Shift.STATUS_SCHEDULED
    ).select_related('caregiver')

    active_qs = Shift.objects.filter(
        employer=user, status=Shift.STATUS_IN_PROGRESS
    ).select_related('caregiver')

    recent_qs = Shift.objects.filter(
        employer=user, status=Shift.STATUS_COMPLETED
    ).select_related('caregiver')

    recent_jobs_qs = JobPosting.objects.filter(
        employer=user, status=JobPosting.STATUS_OPEN
    )

    if q:
        scheduled_qs = scheduled_qs.filter(
            Q(caregiver__first_name__icontains=q) |
            Q(caregiver__last_name__icontains=q) |
            Q(city__icontains=q)
        )
        active_qs = active_qs.filter(
            Q(caregiver__first_name__icontains=q) |
            Q(caregiver__last_name__icontains=q) |
            Q(city__icontains=q)
        )
        recent_qs = recent_qs.filter(
            Q(caregiver__first_name__icontains=q) |
            Q(caregiver__last_name__icontains=q) |
            Q(city__icontains=q)
        )
        recent_jobs_qs = recent_jobs_qs.filter(
            Q(title__icontains=q) |
            Q(city__icontains=q)
        )

    search_shifts_count = scheduled_qs.count() + active_qs.count() + recent_qs.count()
    search_jobs_count = recent_jobs_qs.count()

    scheduled = scheduled_qs.order_by('start_date', 'start_time')
    active = active_qs
    recent = recent_qs.order_by('-start_date')[:5]
    recent_jobs = recent_jobs_qs.order_by('-created_at')[:4]

    now   = timezone.localtime()
    hour  = now.hour
    if hour < 12:
        greeting = 'Good morning'
    elif hour < 17:
        greeting = 'Good afternoon'
    else:
        greeting = 'Good evening'

    ctx.update({
        'scheduled_shifts':  scheduled,
        'active_shifts':     active,
        'recent_shifts':     recent,
        'total_scheduled':   scheduled.count(),
        'total_active':      active.count(),
        'recent_jobs':       recent_jobs,
        'greeting':          greeting,
        'today':             now.date(),
        'employer_profile':  ctx['emp_profile'],
        'show_modal': not ctx['is_activated'] and not request.session.get('modal_dismissed'),
        'search_q':          q,
        'search_shifts_count': search_shifts_count,
        'search_jobs_count': search_jobs_count,
    })
    return render(request, 'EmployerApp/dashboard.html', ctx)


@employer_required
@employer_moderation_check
def my_shifts(request):
    shifts = Shift.objects.filter(
        employer=request.user
    ).select_related('caregiver').order_by('-start_date', '-created_at')
    ctx = _employer_ctx(request.user)
    ctx['shifts'] = shifts
    return render(request, 'EmployerApp/my-shifts.html', ctx)


@employer_required
@employer_moderation_check
def find_caregiver(request):
    return redirect('browse')


@employer_required
@employer_moderation_check
def payment_history(request):
    emp_payments = EmployerPayment.objects.filter(
        employer=request.user
    ).select_related('shift', 'shift__caregiver').order_by('-paid_at')

    # Mark all unseen payments as seen now that the employer is viewing this page
    EmployerPayment.objects.filter(
        employer=request.user, is_seen=False
    ).update(is_seen=True)

    # Keep the old shift-log data for the caregiver payout sub-table
    logs = ShiftLog.objects.filter(
        shift__employer=request.user,
        clock_out_time__isnull=False,
    ).select_related('shift', 'shift__caregiver').order_by('-clock_out_time')

    # Pre-compute summary totals
    total_paid       = sum(p.amount for p in emp_payments if p.status == EmployerPayment.STATUS_COMPLETED)
    activation_fee   = next(
        (p.amount for p in emp_payments if p.payment_type == EmployerPayment.TYPE_ACTIVATION),
        None,
    )
    booking_count    = sum(1 for p in emp_payments if p.payment_type == EmployerPayment.TYPE_BOOKING)
    booking_total    = sum(
        p.amount for p in emp_payments
        if p.payment_type == EmployerPayment.TYPE_BOOKING and p.status == EmployerPayment.STATUS_COMPLETED
    )

    ctx = _employer_ctx(request.user)
    ctx.update({
        'emp_payments':   emp_payments,
        'logs':           logs,
        'total_paid':     total_paid,
        'activation_fee': activation_fee,
        'booking_count':  booking_count,
        'booking_total':  booking_total,
    })
    return render(request, 'EmployerApp/payment-history.html', ctx)


@employer_required
@employer_moderation_check
def post_job(request):
    """Only activated (paid) employers can post jobs."""
    ctx = _employer_ctx(request.user)

    if not ctx['is_activated']:
        messages.warning(request, 'Activate your account to post job offers.')
        return redirect('EmployerApp:activate_account')

    if request.method == 'POST':
        form = JobPostingForm(request.POST)
        if form.is_valid():
            job = form.save(commit=False)
            job.employer = request.user
            job.save()
            # Broadcast job alert to all active caregivers
            try:
                send_job_posted_caregivers_email(job)
            except Exception:
                logger.exception('Job-post broadcast email failed for job %s', job.pk)
            messages.success(request, f'Job "{job.title}" posted successfully.')
            return redirect('EmployerApp:my_jobs')
    else:
        form = JobPostingForm()

    ctx['form'] = form
    return render(request, 'EmployerApp/post-job.html', ctx)


@employer_required
@employer_moderation_check
def my_jobs(request):
    jobs = JobPosting.objects.filter(employer=request.user).order_by('-created_at')
    ctx  = _employer_ctx(request.user)
    ctx['jobs'] = jobs
    return render(request, 'EmployerApp/my-jobs.html', ctx)


@employer_required
@employer_moderation_check
def close_job(request, job_id):
    job = get_object_or_404(JobPosting, pk=job_id, employer=request.user)
    if request.method == 'POST':
        job.status = JobPosting.STATUS_CLOSED
        job.save()
        messages.success(request, f'Job "{job.title}" closed.')
    return redirect('EmployerApp:my_jobs')


@employer_required
@employer_moderation_check
def activate_account(request):
    """Show the Stripe checkout option for the one-time activation fee.
    If the fee is disabled or employer is fee-exempt, auto-activate and redirect.
    """
    profile, _ = EmployerProfile.objects.get_or_create(user=request.user)

    # If fee is off or they are exempt — auto-activate and send to dashboard
    if not _employer_needs_activation(profile):
        if not profile.is_active:
            profile.is_active          = True
            profile.activation_paid_at = timezone.now()
            profile.payment_reference  = 'free-access'
            profile.save(update_fields=['is_active', 'activation_paid_at', 'payment_reference'])
        return redirect('EmployerApp:dashboard')

    ctx = _employer_ctx(request.user)
    ctx['activation_fee'] = EmployerProfile.ACTIVATION_FEE
    return render(request, 'EmployerApp/activate.html', ctx)


def _complete_activation(employer, reference: str) -> None:
    """Activate an employer account and record the payment (idempotent)."""
    profile, _ = EmployerProfile.objects.get_or_create(user=employer)
    if profile.is_active:
        return

    profile.is_active          = True
    profile.activation_paid_at = timezone.now()
    profile.payment_reference  = reference
    profile.save()

    payment, _ = EmployerPayment.objects.get_or_create(
        employer          = employer,
        payment_reference = reference,
        defaults={
            'payment_type': EmployerPayment.TYPE_ACTIVATION,
            'amount':       EmployerProfile.ACTIVATION_FEE,
            'status':       EmployerPayment.STATUS_COMPLETED,
            'description':  'One-time account activation fee (Stripe)',
        },
    )

    # Send activation confirmation email
    try:
        send_activation_confirmation_email(employer, payment)
    except Exception:
        logger.exception('Activation email failed for user %s', employer.pk)


@employer_required
@employer_moderation_check
def stripe_activation_checkout(request):
    """POST — create a Stripe Checkout session for the activation fee."""
    if request.method != 'POST':
        return redirect('EmployerApp:activate_account')

    profile, _ = EmployerProfile.objects.get_or_create(user=request.user)

    # Guard: fee is off or employer is exempt — just activate for free
    if not _employer_needs_activation(profile):
        if not profile.is_active:
            profile.is_active          = True
            profile.activation_paid_at = timezone.now()
            profile.payment_reference  = 'free-access'
            profile.save(update_fields=['is_active', 'activation_paid_at', 'payment_reference'])
        messages.info(request, 'Your account is already active.')
        return redirect('EmployerApp:dashboard')

    if profile.is_active:
        messages.info(request, 'Your account is already active.')
        return redirect('EmployerApp:dashboard')

    reference = stripe_payments.generate_reference('ACT')
    try:
        session = stripe_payments.create_checkout_session(
            amount=EmployerProfile.ACTIVATION_FEE,
            customer_name=request.user.get_full_name() or request.user.get_username(),
            customer_email=request.user.email,
            reference=reference,
            success_url=(
                request.build_absolute_uri(
                    reverse('EmployerApp:stripe_activation_callback')
                )
                + '?session_id={CHECKOUT_SESSION_ID}'
            ),
            cancel_url=request.build_absolute_uri(
                reverse('EmployerApp:activate_account')
            ),
            metadata={
                'payment_type': EmployerPayment.TYPE_ACTIVATION,
                'user_id':      str(request.user.pk),
            },
            description='GetMeCare — one-time account activation fee',
        )
    except Exception:
        logger.exception(
            'Stripe activation checkout failed for user %s', request.user.pk
        )
        messages.error(
            request, 'Could not start the secure payment page. Please try again.'
        )
        return redirect('EmployerApp:activate_account')

    request.session['stripe_activation_ref'] = reference
    return redirect(session.url, status=303)


@employer_required
@employer_moderation_check
def stripe_activation_callback(request):
    """Handle the redirect back from Stripe after activation fee payment.

    Stripe appends ?session_id=<cs_...> to the success_url.  We retrieve the
    session server-side and only activate the account when Stripe reports the
    payment as captured.
    """
    session_id = request.GET.get('session_id', '')

    if not session_id:
        messages.error(request, 'Payment reference not found. Please try again.')
        return redirect('EmployerApp:activate_account')

    try:
        result = stripe_payments.verify_payment(session_id)
    except Exception:
        logger.exception('Stripe activation verify failed: session=%s', session_id)
        messages.error(request, 'Could not verify payment. Please contact support.')
        return redirect('EmployerApp:activate_account')

    if result['status'] != 'success':
        messages.error(
            request,
            f'Payment was not successful (status: {result["status"]}). '
            'Please try again or contact support.',
        )
        return redirect('EmployerApp:activate_account')

    # ── Payment confirmed — activate the account ──────────────────────────────
    reference = (
        result['reference']
        or request.session.get('stripe_activation_ref', '')
        or session_id
    )

    _complete_activation(request.user, reference)

    # Clean up session flag
    request.session.pop('stripe_activation_ref', None)
    request.session.pop('modal_dismissed', None)

    messages.success(
        request,
        'Payment confirmed! Your account is now active. '
        'You can post job offers and connect with caregivers.',
    )
    return redirect('EmployerApp:dashboard')


@employer_required
@employer_moderation_check
def pay_later(request):
    """Dismiss the activation modal and set a session flag."""
    request.session['modal_dismissed'] = True
    return redirect('EmployerApp:dashboard')


# ──────────────────────────────────────────────────────────────
# Caregiver Booking (from negotiation proposal)
# ──────────────────────────────────────────────────────────────

@employer_required
@employer_moderation_check
def book_caregiver(request, proposal_pk):
    """Employer fills in date/time and confirms the booking from a price proposal."""
    from Account.models import BookingProposal
    proposal = get_object_or_404(
        BookingProposal,
        pk=proposal_pk,
        employer=request.user,
        status__in=[BookingProposal.STATUS_PENDING, BookingProposal.STATUS_ACCEPTED],
    )
    today = timezone.now().date()
    ctx = _employer_ctx(request.user)
    ctx['proposal'] = proposal
    ctx['today'] = today

    if request.method == 'POST':
        start_date_str   = request.POST.get('start_date', '').strip()
        start_time_str   = request.POST.get('start_time', '').strip()
        duration_hrs_str = request.POST.get('duration_hours', '').strip()
        city             = request.POST.get('city', '').strip()

        errors = []
        if not start_date_str:
            errors.append('Shift date is required.')
        if not start_time_str:
            errors.append('Start time is required.')
        if not duration_hrs_str:
            errors.append('Duration (hours) is required.')
        if not city:
            errors.append('City / location is required.')

        duration_hours = None
        if not errors:
            try:
                start_date     = datetime.date.fromisoformat(start_date_str)
                start_time     = datetime.time.fromisoformat(start_time_str)
                duration_hours = Decimal(duration_hrs_str)
            except (ValueError, Exception):
                errors.append('Invalid date, time, or duration.')

        if not errors:
            if start_date < today:
                errors.append('Shift date cannot be in the past.')
            if duration_hours <= 0 or duration_hours > 24:
                errors.append('Duration must be between 0.5 and 24 hours.')

        if errors:
            for e in errors:
                messages.error(request, e)
            ctx.update({
                'form_start_date':    start_date_str,
                'form_start_time':    start_time_str,
                'form_duration_hours': duration_hrs_str,
                'form_city':          city,
            })
            return render(request, 'EmployerApp/book-caregiver.html', ctx)

        # Derive end_time from start_time + duration for display purposes
        import datetime as _dt
        start_dt = _dt.datetime.combine(_dt.date.today(), start_time)
        end_dt   = start_dt + _dt.timedelta(hours=float(duration_hours))
        end_time = end_dt.time()

        # Mark proposal accepted and create the Shift
        proposal.status = BookingProposal.STATUS_ACCEPTED
        proposal.save(update_fields=['status', 'updated_at'])

        shift = Shift.objects.create(
            caregiver      = proposal.caregiver,
            employer       = request.user,
            city           = city,
            start_date     = start_date,
            start_time     = start_time,
            end_time       = end_time,
            duration_hours = duration_hours,
            hourly_rate    = proposal.negotiated_rate,
            status         = Shift.STATUS_SCHEDULED,
        )
        # Link shift back to proposal
        proposal.shift = shift
        proposal.save(update_fields=['shift'])

        return redirect('EmployerApp:payment_checkout', shift_pk=shift.pk)

    # GET — render empty form
    ctx.update({
        'form_start_date':     '',
        'form_start_time':     '',
        'form_duration_hours': '',
        'form_city':           '',
    })
    return render(request, 'EmployerApp/book-caregiver.html', ctx)


@employer_required
@employer_moderation_check
def payment_checkout(request, shift_pk):
    """Show the payment summary and the Stripe card-payment button."""
    shift = get_object_or_404(
        Shift,
        pk=shift_pk,
        employer=request.user,
        status=Shift.STATUS_SCHEDULED,
    )
    # Calculate total from duration_hours (set at booking time)
    duration_hrs = shift.duration_hours or Decimal('0')
    total_charge = round(duration_hrs * shift.hourly_rate, 2)

    # GetMeCare collects booking payments via Stripe Checkout
    # (credit / debit cards, charged in CAD).
    ctx = _employer_ctx(request.user)
    ctx.update({
        'shift':        shift,
        'duration_hrs': duration_hrs,
        'total_charge': total_charge,
    })
    return render(request, 'EmployerApp/payment-checkout.html', ctx)


def _complete_booking(employer, shift, reference: str, send_emails: bool = True) -> None:
    """Mark a shift as booked and record its payment (idempotent)."""
    # Guard against double-processing (webhook may have already done this)
    already_recorded = EmployerPayment.objects.filter(
        payment_reference=reference
    ).exists()

    if not already_recorded:
        # Mark proposal as booked
        try:
            proposal = shift.booking_proposal
            proposal.status = BookingProposal.STATUS_BOOKED
            proposal.save(update_fields=['status', 'updated_at'])
        except Exception:
            pass

        duration_hrs = shift.duration_hours or Decimal('0')
        total_charge = round(duration_hrs * shift.hourly_rate, 2)

        EmployerPayment.objects.create(
            employer          = employer,
            payment_type      = EmployerPayment.TYPE_BOOKING,
            amount            = total_charge,
            status            = EmployerPayment.STATUS_COMPLETED,
            payment_reference = reference,
            shift             = shift,
            description       = (
                f'Shift #{shift.pk} — {shift.caregiver.get_full_name()}, '
                f'{duration_hrs} hrs @ ${shift.hourly_rate}/hr (Stripe)'
            ),
        )

    if send_emails:
        # ── Send payment confirmation emails ──────────────────────────────────
        try:
            payment_record = EmployerPayment.objects.filter(
                payment_reference=reference
            ).first()
            if payment_record:
                send_shift_payment_employer_email(employer, shift, payment_record)
                send_shift_payment_caregiver_email(shift.caregiver, shift)
        except Exception:
            logger.exception('Shift payment emails failed for shift %s', shift.pk)


@employer_required
@employer_moderation_check
def stripe_booking_checkout(request, shift_pk):
    """POST — create a Stripe Checkout session for a shift booking."""
    if request.method != 'POST':
        return redirect('EmployerApp:payment_checkout', shift_pk=shift_pk)

    shift = get_object_or_404(
        Shift,
        pk=shift_pk,
        employer=request.user,
        status=Shift.STATUS_SCHEDULED,
    )

    duration_hrs = shift.duration_hours or Decimal('0')
    total_charge = round(duration_hrs * shift.hourly_rate, 2)

    if total_charge <= 0:
        messages.error(request, 'This booking has no amount due.')
        return redirect('EmployerApp:my_shifts')

    reference = stripe_payments.generate_reference('BOOK')
    try:
        session = stripe_payments.create_checkout_session(
            amount=total_charge,
            customer_name=request.user.get_full_name() or request.user.get_username(),
            customer_email=request.user.email,
            reference=reference,
            success_url=(
                request.build_absolute_uri(
                    reverse('EmployerApp:stripe_booking_callback', args=[shift.pk])
                )
                + '?session_id={CHECKOUT_SESSION_ID}'
            ),
            cancel_url=request.build_absolute_uri(
                reverse('EmployerApp:payment_checkout', args=[shift.pk])
            ),
            metadata={
                'payment_type': EmployerPayment.TYPE_BOOKING,
                'user_id':      str(request.user.pk),
                'shift_id':     str(shift.pk),
            },
            description=(
                f'GetMeCare — Shift #{shift.pk} with '
                f'{shift.caregiver.get_full_name()}'
            ),
        )
    except Exception:
        logger.exception('Stripe booking checkout failed for shift %s', shift.pk)
        messages.error(
            request, 'Could not start the secure payment page. Please try again.'
        )
        return redirect('EmployerApp:payment_checkout', shift_pk=shift.pk)

    request.session['stripe_booking_ref'] = reference
    return redirect(session.url, status=303)


@employer_required
@employer_moderation_check
def stripe_booking_callback(request, shift_pk):
    """Handle the redirect back from Stripe after a shift-booking payment.

    Stripe appends ?session_id=<cs_...> to the success_url.  We retrieve the
    session server-side and only confirm the booking when Stripe reports the
    payment as captured.
    """
    shift = get_object_or_404(Shift, pk=shift_pk, employer=request.user)

    session_id = request.GET.get('session_id', '')

    if not session_id:
        messages.error(request, 'Payment reference not found. Please contact support.')
        return redirect('EmployerApp:my_shifts')

    try:
        result = stripe_payments.verify_payment(session_id)
    except Exception:
        logger.exception('Stripe booking verify failed: session=%s', session_id)
        messages.error(request, 'Could not verify payment. Please contact support.')
        return redirect('EmployerApp:my_shifts')

    if result['status'] != 'success':
        messages.error(
            request,
            f'Payment was not successful (status: {result["status"]}). '
            'Please try again or contact support.',
        )
        return redirect('EmployerApp:payment_checkout', shift_pk=shift.pk)

    # ── Payment confirmed ──────────────────────────────────────────────────────
    meta = result.get('metadata') or {}
    if meta.get('shift_id') and meta['shift_id'] != str(shift.pk):
        messages.error(request, 'Payment does not match this booking.')
        return redirect('EmployerApp:payment_checkout', shift_pk=shift.pk)

    reference = (
        result['reference']
        or request.session.get('stripe_booking_ref', '')
        or session_id
    )

    _complete_booking(request.user, shift, reference)

    # Clean up session
    request.session.pop('stripe_booking_ref', None)

    messages.success(
        request,
        f'Payment confirmed! Shift #{shift.pk} with {shift.caregiver.get_full_name()} '
        f'on {shift.start_date.strftime("%b %d, %Y")} is booked. '
        f'The caregiver has been notified.',
    )
    return redirect('EmployerApp:my_shifts')


# Keep the old confirm_payment view as a graceful fallback for any stale links.
# In the new flow the employer is redirected to Stripe's hosted page instead.
@employer_required
@employer_moderation_check
def confirm_payment(request, shift_pk):
    """Legacy endpoint — redirects to checkout if accessed directly."""
    return redirect('EmployerApp:payment_checkout', shift_pk=shift_pk)


# ──────────────────────────────────────────────────────────────
# Dispute views
# ──────────────────────────────────────────────────────────────

@employer_required
@employer_moderation_check
def submit_dispute(request):
    """POST — employer raises a dispute from the modal form."""
    if request.method != 'POST':
        return redirect('EmployerApp:my_disputes')

    shift_pk   = request.POST.get('shift_pk', '').strip()
    payment_pk = request.POST.get('payment_pk', '').strip()
    category   = request.POST.get('category', '').strip()
    description = request.POST.get('description', '').strip()

    # Validate category
    valid_cats = [c[0] for c in Dispute.CATEGORY_CHOICES]
    if category not in valid_cats:
        messages.error(request, 'Please select a valid dispute category.')
        return redirect(request.META.get('HTTP_REFERER', 'EmployerApp:payment_history'))

    if not description:
        messages.error(request, 'Please describe the issue before submitting.')
        return redirect(request.META.get('HTTP_REFERER', 'EmployerApp:payment_history'))

    # Resolve shift (required — dispute must be tied to a shift or payment)
    shift = None
    caregiver = None
    if shift_pk:
        shift = get_object_or_404(Shift, pk=shift_pk, employer=request.user)
        caregiver = shift.caregiver
    elif payment_pk:
        payment_obj = get_object_or_404(
            EmployerPayment,
            pk=payment_pk,
            employer=request.user,
            payment_type=EmployerPayment.TYPE_BOOKING,
        )
        shift = payment_obj.shift
        if shift:
            caregiver = shift.caregiver

    if not caregiver:
        messages.error(request, 'Could not identify the caregiver for this dispute.')
        return redirect(request.META.get('HTTP_REFERER', 'EmployerApp:payment_history'))

    # Prevent duplicate open disputes for the same shift
    existing = Dispute.objects.filter(
        employer=request.user,
        shift=shift,
        status__in=[Dispute.STATUS_OPEN, Dispute.STATUS_UNDER_REVIEW],
    ).first()
    if existing:
        messages.warning(
            request,
            f'You already have an open dispute (#{existing.pk}) for this shift. '
            'Please wait for it to be resolved before raising another.'
        )
        return redirect(request.META.get('HTTP_REFERER', 'EmployerApp:payment_history'))

    payment_obj = None
    if payment_pk:
        try:
            payment_obj = EmployerPayment.objects.get(
                pk=payment_pk, employer=request.user
            )
        except EmployerPayment.DoesNotExist:
            pass

    Dispute.objects.create(
        employer    = request.user,
        caregiver   = caregiver,
        shift       = shift,
        payment     = payment_obj,
        category    = category,
        description = description,
        status      = Dispute.STATUS_OPEN,
    )

    # Notify admin of the new complaint
    try:
        _new_dispute = Dispute.objects.filter(
            employer=request.user,
            description=description,
        ).order_by('-pk').first()
        if _new_dispute:
            send_dispute_submitted_admin_email(_new_dispute)
    except Exception:
        logger.exception('Dispute submitted email failed for employer %s', request.user.pk)

    messages.success(
        request,
        'Your dispute has been submitted. Our team will review it and respond within 2 business days.'
    )
    return redirect(request.META.get('HTTP_REFERER', 'EmployerApp:my_disputes'))


@employer_required
@employer_moderation_check
def my_disputes(request):
    """Employer views all their own disputes."""
    disputes = Dispute.objects.filter(
        employer=request.user
    ).select_related('caregiver', 'shift', 'payment').order_by('-created_at')

    open_count     = disputes.filter(status=Dispute.STATUS_OPEN).count()
    review_count   = disputes.filter(status=Dispute.STATUS_UNDER_REVIEW).count()
    resolved_count = disputes.filter(
        status__in=[Dispute.STATUS_RESOLVED, Dispute.STATUS_DISMISSED]
    ).count()

    ctx = _employer_ctx(request.user)
    ctx.update({
        'disputes':       disputes,
        'open_count':     open_count,
        'review_count':   review_count,
        'resolved_count': resolved_count,
        'categories':     Dispute.CATEGORY_CHOICES,
    })
    return render(request, 'EmployerApp/my-disputes.html', ctx)


# ──────────────────────────────────────────────────────────────
# Stripe Webhook Endpoint
# Receives checkout.session.completed events from Stripe and records
# payments that may not have been captured by the redirect flow.
# ──────────────────────────────────────────────────────────────
@csrf_exempt
def stripe_webhook(request):
    """Process Stripe webhook notifications (checkout.session.completed).

    This endpoint is called by Stripe's servers whenever a checkout
    session completes.  It runs independently of the redirect callback
    so payments are recorded even if the customer closes the browser.

    Signature is validated against the Stripe-Signature header using
    STRIPE_WEBHOOK_SECRET.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)

    # ── Validate signature ────────────────────────────────────────────────────
    try:
        event = stripe_payments.construct_webhook_event(
            request.body, request.headers.get('Stripe-Signature', ''),
        )
    except Exception as exc:
        logger.warning('Stripe webhook rejected: %s', exc)
        return HttpResponse('Invalid signature', status=400)

    # ── Only checkout completions are handled ─────────────────────────────────
    if event['type'] != 'checkout.session.completed':
        logger.info('Stripe webhook ignored event: %s', event['type'])
        return HttpResponse(status=200)

    session   = event['data']['object']
    meta      = session.get('metadata') or {}
    reference = session.get('client_reference_id') or meta.get('reference', '')

    if session.get('payment_status') != 'paid':
        logger.info(
            'Stripe webhook: session=%s not paid — skipped', session.get('id'),
        )
        return HttpResponse(status=200)

    if not reference:
        reference = session.get('id', '')

    payment_type = meta.get('payment_type', '')
    user_id      = meta.get('user_id')
    shift_id     = meta.get('shift_id')

    # ── Activation fee ────────────────────────────────────────────────────────
    if payment_type == EmployerPayment.TYPE_ACTIVATION and user_id:
        from Account.models import CustomUser
        try:
            employer = CustomUser.objects.get(pk=user_id, is_employer=True)
        except CustomUser.DoesNotExist:
            logger.error('Stripe webhook: employer user_id=%s not found', user_id)
            return HttpResponse(status=200)

        _complete_activation(employer, reference)
        logger.info('Stripe webhook: activation recorded for user %s', user_id)

    # ── Shift booking ─────────────────────────────────────────────────────────
    elif payment_type == EmployerPayment.TYPE_BOOKING and user_id and shift_id:
        from Account.models import CustomUser
        try:
            employer = CustomUser.objects.get(pk=user_id, is_employer=True)
            shift    = Shift.objects.get(pk=shift_id)
        except (CustomUser.DoesNotExist, Shift.DoesNotExist) as exc:
            logger.error('Stripe webhook: entity not found — %s', exc)
            return HttpResponse(status=200)

        if shift.employer_id != employer.pk:
            logger.warning(
                'Stripe webhook: shift %s belongs to another employer', shift.pk,
            )
            return HttpResponse(status=200)

        _complete_booking(employer, shift, reference)
        logger.info('Stripe webhook: booking payment recorded for shift %s', shift_id)

    else:
        logger.warning(
            'Stripe webhook: unrecognised payment_type=%s user_id=%s shift_id=%s',
            payment_type, user_id, shift_id,
        )

    return HttpResponse(status=200)
