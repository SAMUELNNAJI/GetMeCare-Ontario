from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Q
from decimal import Decimal
from django.utils import timezone

from Account.models import CaregiverProfile, CaregiverDocument, Shift, ShiftLog, JobPosting


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


def _sidebar_context(user):
    """Return the context variables required by base_caregiver.html sidebar."""
    profile, _ = CaregiverProfile.objects.get_or_create(user=user)
    total_earned = (
        ShiftLog.objects.filter(shift__caregiver=user, payment_status=ShiftLog.PAY_PAID)
        .aggregate(t=Sum('amount_earned'))['t'] or Decimal('0.00')
    )
    completed_count = Shift.objects.filter(
        caregiver=user, status=Shift.STATUS_COMPLETED,
    ).count()
    doc_types = set(CaregiverDocument.objects.filter(user=user).values_list('doc_type', flat=True))

    is_verified = profile.status == CaregiverProfile.STATUS_ACTIVE
    has_bank    = bool(profile.bank_account_number and profile.bank_transit_number)

    checklist = [
        {'label': 'Identity verified',        'done': 'government_id'           in doc_types},
        {'label': 'PSW certificate uploaded', 'done': 'psw_certificate'         in doc_types},
        {'label': 'Vulnerable sector check',  'done': 'vulnerable_sector_check' in doc_types},
        {'label': 'Compliance interview',     'done': is_verified},
        {'label': 'Direct deposit details',   'done': has_bank},
    ]

    # Once admin has verified the caregiver, onboarding is complete regardless
    if is_verified:
        onboarding_pct = 100
    else:
        onboarding_pct = int(sum(1 for c in checklist if c['done']) / len(checklist) * 100)
    
    # Count upcoming shifts for badge
    today = timezone.now().date()
    upcoming_shifts_count = Shift.objects.filter(
        caregiver=user,
        status=Shift.STATUS_SCHEDULED,
        start_date__gte=today,
    ).count()
    
    return {
        'profile':         profile,
        'total_earned':    f"{total_earned:.2f}",
        'completed_count': completed_count,
        'onboarding_pct':  onboarding_pct,
        'checklist':       checklist,
        'upcoming_shifts_count': upcoming_shifts_count,
    }


@caregiver_required
def dashboard(request):
    import json
    from datetime import timedelta, datetime as dt

    user  = request.user
    today = timezone.now().date()
    now   = timezone.now()

    ctx = _sidebar_context(user)
    profile = ctx['profile']

    q = request.GET.get('q', '').strip()

    upcoming_qs = Shift.objects.filter(
        caregiver=user,
        status=Shift.STATUS_SCHEDULED,
        start_date__gte=today,
    ).select_related('employer')

    latest_jobs_qs = JobPosting.objects.filter(status=JobPosting.STATUS_OPEN)

    if q:
        upcoming_qs = upcoming_qs.filter(
            Q(employer__first_name__icontains=q) |
            Q(employer__last_name__icontains=q) |
            Q(city__icontains=q)
        )
        latest_jobs_qs = latest_jobs_qs.filter(
            Q(title__icontains=q) |
            Q(city__icontains=q)
        )

    search_upcoming_count = upcoming_qs.count()
    search_jobs_count = latest_jobs_qs.count()

    upcoming = upcoming_qs.order_by('start_date', 'start_time')[:5]

    # All schedulable shifts for the clock-in picker (no cap)
    clockable_shifts = Shift.objects.filter(
        caregiver=user,
        status=Shift.STATUS_SCHEDULED,
    ).order_by('start_date', 'start_time')

    history = ShiftLog.objects.filter(
        shift__caregiver=user,
        shift__status=Shift.STATUS_COMPLETED,
    ).select_related('shift', 'shift__employer').order_by('-shift__start_date')[:10]

    earned_this_month = (
        ShiftLog.objects.filter(
            shift__caregiver=user,
            payment_status=ShiftLog.PAY_PAID,
            clock_out_time__year=now.year,
            clock_out_time__month=now.month,
        ).aggregate(t=Sum('amount_earned'))['t'] or Decimal('0.00')
    )

    # ── Weekly earnings chart data ──────────────────────────────
    monday = today - timedelta(days=today.weekday())
    week_days = [monday + timedelta(days=i) for i in range(7)]
    day_labels = [d.strftime('%a').upper() for d in week_days]

    week_logs = ShiftLog.objects.filter(
        shift__caregiver=user,
        clock_out_time__date__gte=monday,
        clock_out_time__date__lte=monday + timedelta(days=6),
    ).select_related('shift')

    day_totals = {d: Decimal('0.00') for d in week_days}
    for log in week_logs:
        if log.clock_out_time and log.amount_earned:
            d = log.clock_out_time.date()
            if d in day_totals:
                day_totals[d] += log.amount_earned

    weekly_data   = [float(day_totals[d]) for d in week_days]
    weekly_total  = sum(weekly_data)
    weekly_labels = day_labels

    prev_monday = monday - timedelta(days=7)
    prev_logs = ShiftLog.objects.filter(
        shift__caregiver=user,
        clock_out_time__date__gte=prev_monday,
        clock_out_time__date__lte=prev_monday + timedelta(days=6),
    ).select_related('shift')
    prev_total = float(
        prev_logs.aggregate(t=Sum('amount_earned'))['t'] or Decimal('0.00')
    )
    if prev_total > 0:
        week_change_pct = round((weekly_total - prev_total) / prev_total * 100, 1)
    else:
        week_change_pct = None

    hour = now.hour
    greeting = 'Good morning' if hour < 12 else ('Good afternoon' if hour < 17 else 'Good evening')

    # ── Shift tracker state ──────────────────────────────────────
    # Priority 1: active (clocked in)
    active_log = ShiftLog.objects.filter(
        shift__caregiver=user,
        shift__status=Shift.STATUS_IN_PROGRESS,
        clock_in_time__isnull=False,
        clock_out_time__isnull=True,
    ).select_related('shift').first()

    # Priority 2: just completed (most recent completed today)
    recently_completed = ShiftLog.objects.filter(
        shift__caregiver=user,
        shift__status=Shift.STATUS_COMPLETED,
        clock_out_time__date=today,
    ).order_by('-clock_out_time').first()

    # Priority 3: next scheduled shift
    next_shift = Shift.objects.filter(
        caregiver=user,
        status=Shift.STATUS_SCHEDULED,
        start_date__gte=today,
    ).order_by('start_date', 'start_time').first()

    tracker_state        = 'none'
    tracker_shift_pk     = 0
    tracker_start_iso    = ''
    tracker_clock_in_iso = ''
    tracker_duration_secs = 0

    if active_log:
        tracker_state        = 'active'
        tracker_shift_pk     = active_log.shift.pk
        tracker_clock_in_iso = active_log.clock_in_time.isoformat()
        # Duration in seconds so the JS countdown knows when to auto-clock-out
        dur = active_log.shift.duration_hours
        tracker_duration_secs = int(float(dur) * 3600) if dur else 0
    elif recently_completed and not active_log and not next_shift:
        tracker_state      = 'completed'
        tracker_shift_pk   = recently_completed.shift.pk
    elif next_shift:
        # Combine shift date + start_time to get naive datetime, then make aware
        naive_start = dt.combine(next_shift.start_date, next_shift.start_time)
        aware_start = timezone.make_aware(naive_start) if timezone.is_naive(naive_start) else naive_start
        tracker_shift_pk  = next_shift.pk
        tracker_start_iso = aware_start.isoformat()
        if now >= aware_start:
            tracker_state = 'ready'       # start time passed, not clocked in yet
        else:
            tracker_state = 'countdown'   # counting down to start

    ctx.update({
        'upcoming':          upcoming,
        'history':           history,
        'earned_this_month': f"{earned_this_month:,.2f}",
        'greeting':          greeting,
        'today':             today,
        'weekly_labels':     json.dumps(weekly_labels),
        'weekly_data':       json.dumps(weekly_data),
        'weekly_total':      f"{weekly_total:,.2f}",
        'week_change_pct':   week_change_pct,
        'latest_jobs':       latest_jobs_qs.order_by('-created_at')[:3],
        'search_q':          q,
        'search_upcoming_count': search_upcoming_count,
        'search_jobs_count': search_jobs_count,
        # Tracker
        'tracker_state':          tracker_state,
        'tracker_shift_pk':       tracker_shift_pk,
        'tracker_start_iso':      tracker_start_iso,
        'tracker_clock_in_iso':   tracker_clock_in_iso,
        'tracker_duration_secs':  tracker_duration_secs if tracker_state == 'active' else 0,
        # Clock-in picker
        'clockable_shifts':       clockable_shifts,
        'clockable_count':        clockable_shifts.count(),
    })
    return render(request, 'CareGiverAcc/dashboard.html', ctx)


@caregiver_required
def my_schedule(request):
    from django.core.paginator import Paginator
    from datetime import datetime as dt

    user  = request.user
    today = timezone.now().date()
    now   = timezone.now()

    upcoming = Shift.objects.filter(
        caregiver=user,
        status__in=[Shift.STATUS_SCHEDULED, Shift.STATUS_IN_PROGRESS],
        start_date__gte=today,
    ).order_by('start_date', 'start_time')

    # Shift history — paginated at 10
    history_qs = ShiftLog.objects.filter(
        shift__caregiver=user,
        shift__status=Shift.STATUS_COMPLETED,
    ).select_related('shift', 'shift__employer').order_by('-shift__start_date')

    paginator    = Paginator(history_qs, 10)
    page_number  = request.GET.get('page', 1)
    history_page = paginator.get_page(page_number)

    # ── Same tracker state logic as dashboard ────────────────────
    active_log = ShiftLog.objects.filter(
        shift__caregiver=user,
        shift__status=Shift.STATUS_IN_PROGRESS,
        clock_in_time__isnull=False,
        clock_out_time__isnull=True,
    ).select_related('shift').first()

    recently_completed = ShiftLog.objects.filter(
        shift__caregiver=user,
        shift__status=Shift.STATUS_COMPLETED,
        clock_out_time__date=today,
    ).order_by('-clock_out_time').first()

    next_shift = Shift.objects.filter(
        caregiver=user,
        status=Shift.STATUS_SCHEDULED,
        start_date__gte=today,
    ).order_by('start_date', 'start_time').first()

    # All schedulable shifts for the clock-in picker
    clockable_shifts = Shift.objects.filter(
        caregiver=user,
        status=Shift.STATUS_SCHEDULED,
    ).order_by('start_date', 'start_time')

    tracker_state         = 'none'
    tracker_shift_pk      = 0
    tracker_start_iso     = ''
    tracker_clock_in_iso  = ''
    tracker_duration_secs = 0

    if active_log:
        tracker_state        = 'active'
        tracker_shift_pk     = active_log.shift.pk
        tracker_clock_in_iso = active_log.clock_in_time.isoformat()
        dur = active_log.shift.duration_hours
        tracker_duration_secs = int(float(dur) * 3600) if dur else 0
    elif recently_completed and not active_log and not next_shift:
        tracker_state    = 'completed'
        tracker_shift_pk = recently_completed.shift.pk
    elif next_shift:
        naive_start = dt.combine(next_shift.start_date, next_shift.start_time)
        aware_start = timezone.make_aware(naive_start) if timezone.is_naive(naive_start) else naive_start
        tracker_shift_pk  = next_shift.pk
        tracker_start_iso = aware_start.isoformat()
        tracker_state     = 'ready' if now >= aware_start else 'countdown'

    ctx = _sidebar_context(user)
    ctx.update({
        'shifts':               upcoming,
        'shift_history':        history_page,        # Page object
        'today':                today,
        # Tracker
        'tracker_state':          tracker_state,
        'tracker_shift_pk':       tracker_shift_pk,
        'tracker_start_iso':      tracker_start_iso,
        'tracker_clock_in_iso':   tracker_clock_in_iso,
        'tracker_duration_secs':  tracker_duration_secs,
        # Clock-in picker
        'clockable_shifts':       clockable_shifts,
        'clockable_count':        clockable_shifts.count(),
    })
    return render(request, 'CareGiverAcc/my-schedule.html', ctx)


@caregiver_required
def earnings(request):
    logs = ShiftLog.objects.filter(
        shift__caregiver=request.user,
        clock_out_time__isnull=False,
    ).select_related('shift').order_by('-clock_out_time')

    total = logs.aggregate(t=Sum('amount_earned'))['t'] or Decimal('0.00')
    paid  = logs.filter(payment_status=ShiftLog.PAY_PAID).aggregate(t=Sum('amount_earned'))['t'] or Decimal('0.00')

    ctx = _sidebar_context(request.user)
    ctx.update({
        'logs':    logs,
        'total':   f"{total:.2f}",
        'paid':    f"{paid:.2f}",
        'pending': f"{(total - paid):.2f}",
    })
    return render(request, 'CareGiverAcc/earnings.html', ctx)


@caregiver_required
def documents(request):
    from Account.forms import DocumentUploadForm, REQUIRED_DOC_TYPES

    # Get all user documents in a single query, ordered by upload date
    user_docs = CaregiverDocument.objects.filter(
        user=request.user
    ).select_related('user').order_by('-uploaded_at')

    # Build per-type status map for the required checklist
    latest_by_type = {}
    uploaded_types = set()
    for doc in user_docs:
        uploaded_types.add(doc.doc_type)
        if doc.doc_type not in latest_by_type:
            latest_by_type[doc.doc_type] = doc

    required_checklist = []
    for dt in REQUIRED_DOC_TYPES:
        doc = latest_by_type.get(dt)
        required_checklist.append({
            'key':     dt,
            'label':   dict(CaregiverDocument.DOC_TYPE_CHOICES).get(dt, dt),
            'uploaded': doc is not None,
            'status':   doc.status if doc else None,
            'doc':      doc,
        })

    all_uploaded   = all(item['uploaded'] for item in required_checklist)
    all_approved   = all(
        item['doc'] and item['doc'].status == CaregiverDocument.STATUS_APPROVED
        for item in required_checklist
    )

    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES, uploaded_types=uploaded_types)
        if form.is_valid():
            dt = form.cleaned_data['doc_type']
            if dt in uploaded_types and dt != CaregiverDocument.DOC_OTHER:
                messages.error(
                    request,
                    f'You have already uploaded a {dict(CaregiverDocument.DOC_TYPE_CHOICES)[dt]}. '
                    'Wait for admin review before re-uploading.'
                )
            else:
                doc = form.save(commit=False)
                doc.user = request.user
                doc.save()
                messages.success(request, f'{doc.get_doc_type_display()} uploaded successfully.')
            return redirect('CareGiverAcc:documents')
    else:
        form = DocumentUploadForm(uploaded_types=uploaded_types)

    # Count remaining required types still to be uploaded (excluding blank choice)
    remaining_required = [
        dt for dt in REQUIRED_DOC_TYPES if dt not in uploaded_types
    ]
    has_remaining_types = len(remaining_required) > 0

    ctx = _sidebar_context(request.user)
    ctx.update({
        'form':               form,
        'user_docs':          user_docs,
        'required_checklist': required_checklist,
        'all_uploaded':       all_uploaded,
        'all_approved':       all_approved,
        'uploaded_types':     uploaded_types,
        'has_remaining_types': has_remaining_types,
    })
    return render(request, 'CareGiverAcc/documents.html', ctx)


@caregiver_required
def reupload_document(request, doc_id):
    """Replace a rejected document with a new file and reset it to pending."""
    doc = get_object_or_404(CaregiverDocument, pk=doc_id, user=request.user)

    if doc.status != CaregiverDocument.STATUS_REJECTED:
        messages.error(request, 'Only rejected documents can be re-uploaded.')
        return redirect('CareGiverAcc:documents')

    if request.method == 'POST' and request.FILES.get('file'):
        # Delete old file from storage
        if doc.file:
            doc.file.delete(save=False)
        doc.file = request.FILES['file']
        doc.status = CaregiverDocument.STATUS_PENDING
        doc.note = ''
        doc.reviewed_at = None
        doc.save()
        messages.success(
            request,
            f'{doc.get_doc_type_display()} re-uploaded successfully. It is now pending admin review.'
        )
    else:
        messages.error(request, 'No file was selected.')

    return redirect('CareGiverAcc:documents')


@caregiver_required
def serve_document(request, doc_id):
    """Serve the caregiver's own document inline in the browser."""
    import mimetypes, os
    from django.http import HttpResponse, Http404
    doc = get_object_or_404(CaregiverDocument, pk=doc_id, user=request.user)
    file_path = doc.file.path
    if not os.path.exists(file_path):
        raise Http404('File not found.')
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = 'application/octet-stream'
    with open(file_path, 'rb') as f:
        response = HttpResponse(f.read(), content_type=mime_type)
    response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
    return response


@caregiver_required
def dismiss_activation_modal(request):
    """
    Permanently dismiss the activation reminder modal.

    Sets CaregiverProfile.activation_modal_dismissed = True in the DB
    so the modal never shows again, even after session expiry or on a
    different device.

    Accepts an optional ?next= query param so the Upload Documents and
    Edit Profile buttons can pass through here before redirecting onward.
    """
    try:
        from Account.models import CaregiverProfile
        profile, _ = CaregiverProfile.objects.get_or_create(user=request.user)
        if not profile.activation_modal_dismissed:
            profile.activation_modal_dismissed = True
            profile.save(update_fields=['activation_modal_dismissed'])
    except Exception:
        pass

    # Also clear the old session key for backwards compatibility
    request.session.pop('caregiver_activation_dismissed', None)

    next_url = request.GET.get('next', '')
    # Safety check — only allow relative URLs (prevent open redirect)
    if next_url and next_url.startswith('/') and not next_url.startswith('//'):
        return redirect(next_url)
    return redirect('CareGiverAcc:dashboard')
