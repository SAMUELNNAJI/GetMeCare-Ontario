from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum
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
    checklist = [
        {'label': 'Identity verified',        'done': 'government_id'           in doc_types},
        {'label': 'PSW certificate uploaded', 'done': 'psw_certificate'         in doc_types},
        {'label': 'Vulnerable sector check',  'done': 'vulnerable_sector_check' in doc_types},
        {'label': 'Compliance interview',     'done': profile.status == 'active'},
        {'label': 'Direct deposit details',   'done': False},
    ]
    onboarding_pct = int(sum(1 for c in checklist if c['done']) / len(checklist) * 100)
    return {
        'profile':         profile,
        'total_earned':    f"{total_earned:.2f}",
        'completed_count': completed_count,
        'onboarding_pct':  onboarding_pct,
        'checklist':       checklist,
    }


@caregiver_required
def dashboard(request):
    import json
    from datetime import timedelta

    user  = request.user
    today = timezone.now().date()
    now   = timezone.now()

    ctx = _sidebar_context(user)
    profile = ctx['profile']

    upcoming = Shift.objects.filter(
        caregiver=user,
        status=Shift.STATUS_SCHEDULED,
        start_date__gte=today,
    ).order_by('start_date', 'start_time')[:5]

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
    # Find Monday of the current week
    monday = today - timedelta(days=today.weekday())
    week_days = [monday + timedelta(days=i) for i in range(7)]
    day_labels = [d.strftime('%a').upper() for d in week_days]

    week_logs = ShiftLog.objects.filter(
        shift__caregiver=user,
        clock_out_time__date__gte=monday,
        clock_out_time__date__lte=monday + timedelta(days=6),
    ).select_related('shift')

    # Build a dict: date -> total earned that day
    day_totals = {d: Decimal('0.00') for d in week_days}
    for log in week_logs:
        if log.clock_out_time and log.amount_earned:
            d = log.clock_out_time.date()
            if d in day_totals:
                day_totals[d] += log.amount_earned

    weekly_data   = [float(day_totals[d]) for d in week_days]
    weekly_total  = sum(weekly_data)
    weekly_labels = day_labels

    # Compare to previous week for % change badge
    prev_monday = monday - timedelta(days=7)
    prev_logs = ShiftLog.objects.filter(
        shift__caregiver=user,
        clock_out_time__date__gte=prev_monday,
        clock_out_time__date__lte=prev_monday + timedelta(days=6),
    )
    prev_total = float(
        prev_logs.aggregate(t=Sum('amount_earned'))['t'] or Decimal('0.00')
    )
    if prev_total > 0:
        week_change_pct = round((weekly_total - prev_total) / prev_total * 100, 1)
    else:
        week_change_pct = None

    hour = now.hour
    greeting = 'Good morning' if hour < 12 else ('Good afternoon' if hour < 17 else 'Good evening')

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
        'latest_jobs':       JobPosting.objects.filter(status=JobPosting.STATUS_OPEN).order_by('-created_at')[:3],
    })
    return render(request, 'CareGiverAcc/dashboard.html', ctx)


@caregiver_required
def my_schedule(request):
    today = timezone.now().date()

    upcoming = Shift.objects.filter(
        caregiver=request.user,
        status__in=[Shift.STATUS_SCHEDULED, Shift.STATUS_IN_PROGRESS],
        start_date__gte=today,
    ).order_by('start_date', 'start_time')

    shift_history = ShiftLog.objects.filter(
        shift__caregiver=request.user,
        shift__status=Shift.STATUS_COMPLETED,
    ).select_related('shift').order_by('-shift__start_date')[:20]

    ctx = _sidebar_context(request.user)
    ctx.update({'shifts': upcoming, 'shift_history': shift_history, 'today': today})
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

    user_docs     = CaregiverDocument.objects.filter(user=request.user)
    uploaded_types = set(user_docs.values_list('doc_type', flat=True))

    # Build per-type status map for the required checklist
    latest_by_type = {}
    for doc in user_docs:
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
