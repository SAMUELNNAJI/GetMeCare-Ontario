from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
import datetime
from decimal import Decimal

from Account.models import Shift, ShiftLog, EmployerProfile, JobPosting, BookingProposal
from Account.forms import JobPostingForm


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


def _employer_ctx(user):
    """Shared context for base_employer.html sidebar."""
    profile, _ = EmployerProfile.objects.get_or_create(user=user)
    total_completed = Shift.objects.filter(
        employer=user, status=Shift.STATUS_COMPLETED
    ).count()
    open_jobs = JobPosting.objects.filter(
        employer=user, status=JobPosting.STATUS_OPEN
    ).count()
    return {
        'emp_profile':      profile,
        'is_activated':     profile.is_active,
        'total_completed':  total_completed,
        'open_jobs_count':  open_jobs,
    }


# ────────────────────────────────────────────────────────────
@employer_required
def dashboard(request):
    user = request.user
    ctx  = _employer_ctx(user)

    scheduled = Shift.objects.filter(
        employer=user, status=Shift.STATUS_SCHEDULED
    ).order_by('start_date', 'start_time').select_related('caregiver')

    active = Shift.objects.filter(
        employer=user, status=Shift.STATUS_IN_PROGRESS
    ).select_related('caregiver')

    recent = Shift.objects.filter(
        employer=user, status=Shift.STATUS_COMPLETED
    ).order_by('-start_date').select_related('caregiver')[:5]

    recent_jobs = JobPosting.objects.filter(
        employer=user, status=JobPosting.STATUS_OPEN
    ).order_by('-created_at')[:4]

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
        # Show activation modal only if account not active and user hasn't dismissed it
        'show_modal': not ctx['is_activated'] and not request.session.get('modal_dismissed'),
    })
    return render(request, 'EmployerApp/dashboard.html', ctx)


@employer_required
def my_shifts(request):
    shifts = Shift.objects.filter(
        employer=request.user
    ).select_related('caregiver').order_by('-start_date')
    ctx = _employer_ctx(request.user)
    ctx['shifts'] = shifts
    return render(request, 'EmployerApp/my-shifts.html', ctx)


@employer_required
def find_caregiver(request):
    return redirect('browse')


@employer_required
def payment_history(request):
    logs = ShiftLog.objects.filter(
        shift__employer=request.user,
        clock_out_time__isnull=False,
    ).select_related('shift', 'shift__caregiver').order_by('-clock_out_time')
    ctx = _employer_ctx(request.user)
    ctx['logs'] = logs
    return render(request, 'EmployerApp/payment-history.html', ctx)


@employer_required
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
            messages.success(request, f'Job "{job.title}" posted successfully.')
            return redirect('EmployerApp:my_jobs')
    else:
        form = JobPostingForm()

    ctx['form'] = form
    return render(request, 'EmployerApp/post-job.html', ctx)


@employer_required
def my_jobs(request):
    jobs = JobPosting.objects.filter(employer=request.user).order_by('-created_at')
    ctx  = _employer_ctx(request.user)
    ctx['jobs'] = jobs
    return render(request, 'EmployerApp/my-jobs.html', ctx)


@employer_required
def close_job(request, job_id):
    job = get_object_or_404(JobPosting, pk=job_id, employer=request.user)
    if request.method == 'POST':
        job.status = JobPosting.STATUS_CLOSED
        job.save()
        messages.success(request, f'Job "{job.title}" closed.')
    return redirect('EmployerApp:my_jobs')


@employer_required
def activate_account(request):
    """Simulate payment — in production wire this to Stripe."""
    ctx = _employer_ctx(request.user)

    if request.method == 'POST':
        # Simulated successful payment
        profile = ctx['emp_profile']
        profile.is_active          = True
        profile.activation_paid_at = timezone.now()
        profile.payment_reference  = f'SIM-{request.user.pk}-{int(timezone.now().timestamp())}'
        profile.save()
        # Clear the modal-dismissed flag so the dashboard knows account is now active
        request.session.pop('modal_dismissed', None)
        messages.success(
            request,
            'Account activated! You can now post job offers and connect with caregivers.'
        )
        return redirect('EmployerApp:dashboard')

    return render(request, 'EmployerApp/activate.html', ctx)


@employer_required
def pay_later(request):
    """Dismiss the activation modal and set a session flag."""
    request.session['modal_dismissed'] = True
    return redirect('EmployerApp:dashboard')


# ──────────────────────────────────────────────────────────────
# Caregiver Booking (from negotiation proposal)
# ──────────────────────────────────────────────────────────────

@employer_required
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
        start_date_str = request.POST.get('start_date', '').strip()
        start_time_str = request.POST.get('start_time', '').strip()
        end_time_str   = request.POST.get('end_time', '').strip()
        city           = request.POST.get('city', '').strip()

        errors = []
        if not start_date_str:
            errors.append('Shift date is required.')
        if not start_time_str:
            errors.append('Start time is required.')
        if not end_time_str:
            errors.append('End time is required.')
        if not city:
            errors.append('City / location is required.')

        if not errors:
            try:
                start_date = datetime.date.fromisoformat(start_date_str)
                start_time = datetime.time.fromisoformat(start_time_str)
                end_time   = datetime.time.fromisoformat(end_time_str)
            except ValueError:
                errors.append('Invalid date or time format.')

        if not errors:
            if start_date < today:
                errors.append('Shift date cannot be in the past.')
            if end_time <= start_time:
                errors.append('End time must be after start time.')

        if errors:
            for e in errors:
                messages.error(request, e)
            # Keep form values
            ctx['form'] = {
                'start_date': {'value': lambda: start_date_str},
                'start_time': {'value': lambda: start_time_str},
                'end_time':   {'value': lambda: end_time_str},
                'city':       {'value': lambda: city},
            }
            return render(request, 'EmployerApp/book-caregiver.html', ctx)

        # Mark proposal accepted and create the Shift
        proposal.status = BookingProposal.STATUS_ACCEPTED
        proposal.save(update_fields=['status', 'updated_at'])

        shift = Shift.objects.create(
            caregiver   = proposal.caregiver,
            employer    = request.user,
            city        = city,
            start_date  = start_date,
            start_time  = start_time,
            end_time    = end_time,
            hourly_rate = proposal.negotiated_rate,
            status      = Shift.STATUS_SCHEDULED,
        )
        # Link shift back to proposal
        proposal.shift = shift
        proposal.save(update_fields=['shift'])

        return redirect('EmployerApp:payment_checkout', shift_pk=shift.pk)

    # GET — render empty form
    ctx['form'] = {
        'start_date': {'value': lambda: ''},
        'start_time': {'value': lambda: ''},
        'end_time':   {'value': lambda: ''},
        'city':       {'value': lambda: ''},
    }
    return render(request, 'EmployerApp/book-caregiver.html', ctx)


@employer_required
def payment_checkout(request, shift_pk):
    """Show the Stripe payment placeholder for a newly created shift."""
    shift = get_object_or_404(
        Shift,
        pk=shift_pk,
        employer=request.user,
        status=Shift.STATUS_SCHEDULED,
    )
    # Calculate estimated total
    start_dt = datetime.datetime.combine(shift.start_date, shift.start_time)
    end_dt   = datetime.datetime.combine(shift.start_date, shift.end_time)
    duration_secs = (end_dt - start_dt).total_seconds()
    duration_hrs  = round(duration_secs / 3600, 2)
    total_charge  = round(Decimal(str(duration_hrs)) * shift.hourly_rate, 2)

    ctx = _employer_ctx(request.user)
    ctx.update({
        'shift':        shift,
        'duration_hrs': duration_hrs,
        'total_charge': total_charge,
    })
    return render(request, 'EmployerApp/payment-checkout.html', ctx)


@employer_required
def confirm_payment(request, shift_pk):
    """Simulate a successful Stripe payment.
       Marks the proposal as booked, records payment reference, and redirects to employer shifts.
    """
    if request.method != 'POST':
        return redirect('EmployerApp:my_shifts')

    shift = get_object_or_404(
        Shift,
        pk=shift_pk,
        employer=request.user,
        status=Shift.STATUS_SCHEDULED,
    )

    # Mark proposal as booked
    try:
        proposal = shift.booking_proposal
        proposal.status = BookingProposal.STATUS_BOOKED
        proposal.save(update_fields=['status', 'updated_at'])
    except Exception:
        pass  # proposal may not exist if shift was created manually by admin

    # Record simulated payment reference on EmployerProfile
    emp_profile, _ = EmployerProfile.objects.get_or_create(user=request.user)
    ref = f'SIM-BOOKING-{shift.pk}-{int(timezone.now().timestamp())}'
    emp_profile.payment_reference = ref
    emp_profile.save(update_fields=['payment_reference', 'updated_at'])

    messages.success(
        request,
        f'Payment confirmed! Shift #{shift.pk} with {shift.caregiver.get_full_name()} '
        f'on {shift.start_date.strftime("%b %d, %Y")} is booked. '
        f'The caregiver has been notified.'
    )
    return redirect('EmployerApp:my_shifts')
