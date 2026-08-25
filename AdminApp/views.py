import mimetypes
import os
from django.http import HttpResponse, Http404, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from Account.models import CustomUser, CaregiverProfile, CaregiverDocument, Shift, ShiftLog, EmployerPayment, EmployerProfile, Dispute
from Account.forms import REQUIRED_DOC_TYPES
from django.db.models import Q
from .models import Faq, Service
from .forms import FaqForm, ServiceForm
from GETMECARE.email_utils import (
    send_payout_notification_email,
    send_dispute_resolved_employer_email,
    send_document_rejected_email,
    send_caregiver_activation_email,
)


def admin_required(view_func):
    """Decorator: must be logged in AND be staff/superuser."""
    @login_required(login_url='Account:login')
    def wrapper(request, *args, **kwargs):
        if not (request.user.is_staff or request.user.is_superuser):
            messages.error(request, 'Access denied. Admin account required.')
            return redirect('Account:login')
        return view_func(request, *args, **kwargs)
    wrapper.__name__ = view_func.__name__
    return wrapper


def _admin_sidebar():
    """Counts shown in the admin sidebar nav badges."""
    from Account.models import EmployerPayment, Dispute
    return {
        'pending_docs':            CaregiverDocument.objects.filter(status=CaregiverDocument.STATUS_PENDING).count(),
        'pending_profiles':        CaregiverProfile.objects.filter(status=CaregiverProfile.STATUS_PENDING).count(),
        'employer_payments_count': EmployerPayment.objects.filter(admin_seen=False).count(),
        'payout_queue_count':      ShiftLog.objects.filter(payment_status=ShiftLog.PAY_PENDING).count(),
        'counts': {
            'open': Dispute.objects.filter(status=Dispute.STATUS_OPEN).count(),
        },
    }


@admin_required
def dashboard(request):
    import json
    from datetime import timedelta
    from django.db.models import Count, Q
    from django.db.models.functions import TruncDate

    today = timezone.now().date()

    total_caregivers  = CustomUser.objects.filter(role=CustomUser.CAREGIVER).count()
    total_employers   = CustomUser.objects.filter(role=CustomUser.EMPLOYER).count()
    active_shifts     = Shift.objects.filter(status=Shift.STATUS_IN_PROGRESS).count()
    completed_shifts  = Shift.objects.filter(status=Shift.STATUS_COMPLETED).count()
    recent_users = CustomUser.objects.order_by('-date_joined')[:8]

    q = request.GET.get('q', '').strip()
    if q:
        search_users_qs = CustomUser.objects.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q) |
            Q(role__icontains=q)
        )
        search_users_count = search_users_qs.count()
        recent_users = search_users_qs.order_by('-date_joined')[:8]
    else:
        search_users_count = 0

    # ── Shifts per day — last 14 days (bar chart) ───────────────
    fourteen_days = [today - timedelta(days=i) for i in range(13, -1, -1)]
    shifts_by_day = (
        Shift.objects.filter(start_date__gte=fourteen_days[0])
        .values('start_date')
        .annotate(cnt=Count('id'))
    )
    shift_day_map = {row['start_date']: row['cnt'] for row in shifts_by_day}
    shifts_chart_labels = json.dumps([d.strftime('%b %d') for d in fourteen_days])
    shifts_chart_data   = json.dumps([shift_day_map.get(d, 0) for d in fourteen_days])

    # ── New user registrations — last 30 days (line chart) ──────
    thirty_days = [today - timedelta(days=i) for i in range(29, -1, -1)]
    users_by_day = (
        CustomUser.objects.filter(date_joined__date__gte=thirty_days[0])
        .annotate(day=TruncDate('date_joined'))
        .values('day')
        .annotate(cnt=Count('id'))
    )
    user_day_map = {row['day']: row['cnt'] for row in users_by_day}
    users_chart_labels = json.dumps([d.strftime('%b %d') for d in thirty_days])
    users_chart_data   = json.dumps([user_day_map.get(d, 0) for d in thirty_days])

    # ── Live activity feed — last 30 events ─────────────────────
    activities = []

    # Recent document uploads
    for doc in CaregiverDocument.objects.select_related('user').order_by('-uploaded_at')[:10]:
        activities.append({
            'icon':  'fas fa-file-arrow-up',
            'color': '#c96000',
            'bg':    '#fff3e0',
            'text':  f'{doc.user.get_full_name()} uploaded <strong>{doc.get_doc_type_display()}</strong>',
            'sub':   doc.get_status_display(),
            'time':  doc.uploaded_at,
        })

    # Recent document reviews
    for doc in CaregiverDocument.objects.select_related('user').exclude(
        reviewed_at=None
    ).order_by('-reviewed_at')[:8]:
        verb = 'approved' if doc.status == 'approved' else 'rejected'
        activities.append({
            'icon':  'fas fa-file-circle-check' if doc.status == 'approved' else 'fas fa-file-circle-xmark',
            'color': '#1b7d4f' if doc.status == 'approved' else '#c62828',
            'bg':    '#e6f5ee' if doc.status == 'approved' else '#fdecea',
            'text':  f'Document <strong>{verb}</strong> for {doc.user.get_full_name()}',
            'sub':   doc.get_doc_type_display(),
            'time':  doc.reviewed_at,
        })

    # Recent clock-ins
    for log in ShiftLog.objects.select_related('shift__caregiver').exclude(
        clock_in_time=None
    ).order_by('-clock_in_time')[:6]:
        activities.append({
            'icon':  'fas fa-play-circle',
            'color': '#1a56c4',
            'bg':    '#e8f0fe',
            'text':  f'{log.shift.caregiver.get_full_name()} <strong>clocked in</strong>',
            'sub':   f'Shift #{log.shift.pk}',
            'time':  log.clock_in_time,
        })

    # Recent clock-outs
    for log in ShiftLog.objects.select_related('shift__caregiver').exclude(
        clock_out_time=None
    ).order_by('-clock_out_time')[:6]:
        activities.append({
            'icon':  'fas fa-stop-circle',
            'color': '#7c3aed',
            'bg':    '#f3e8ff',
            'text':  f'{log.shift.caregiver.get_full_name()} <strong>clocked out</strong>',
            'sub':   f'{log.hours_worked or "—"} hrs · ${log.amount_earned or "—"}',
            'time':  log.clock_out_time,
        })

    # Recent new users
    for u in CustomUser.objects.order_by('-date_joined')[:6]:
        activities.append({
            'icon':  'fas fa-user-plus',
            'color': '#1b7d4f',
            'bg':    '#e6f5ee',
            'text':  f'<strong>{u.get_full_name() or u.username}</strong> joined as {u.get_role_display()}',
            'sub':   u.email,
            'time':  u.date_joined,
        })

    # Sort all by time descending, take top 25
    activities.sort(key=lambda a: a['time'] or timezone.now(), reverse=True)
    activities = activities[:25]

    ctx = _admin_sidebar()
    ctx.update({
        'total_caregivers':    total_caregivers,
        'total_employers':     total_employers,
        'active_shifts':       active_shifts,
        'completed_shifts':    completed_shifts,
        'recent_users':        recent_users,
        'shifts_chart_labels': shifts_chart_labels,
        'shifts_chart_data':   shifts_chart_data,
        'users_chart_labels':  users_chart_labels,
        'users_chart_data':    users_chart_data,
        'activities':          activities,
        'search_q':            q,
        'search_users_count':  recent_users.count(),
    })
    return render(request, 'AdminApp/dashboard.html', ctx)


@admin_required
def manage_users(request):
    q = request.GET.get('q', '').strip()
    users = CustomUser.objects.order_by('-date_joined')
    if q:
        users = users.filter(
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q) |
            Q(role__icontains=q)
        )
    ctx = _admin_sidebar()
    ctx['users'] = users
    ctx['search_q'] = q
    return render(request, 'AdminApp/manage-users.html', ctx)


@admin_required
def manage_caregivers(request):
    q = request.GET.get('q', '').strip()
    profiles = CaregiverProfile.objects.select_related('user').order_by('-created_at')
    if q:
        profiles = profiles.filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(user__username__icontains=q) |
            Q(user__email__icontains=q) |
            Q(city__icontains=q) |
            Q(skills__icontains=q) |
            Q(status__icontains=q)
        )
    ctx = _admin_sidebar()
    ctx['profiles'] = profiles
    ctx['doc_types'] = REQUIRED_DOC_TYPES
    ctx['search_q'] = q
    return render(request, 'AdminApp/manage-caregivers.html', ctx)


@admin_required
def manage_employers(request):
    from django.db.models import Q
    profiles = EmployerProfile.objects.select_related('user').exclude(
        Q(user__is_superuser=True) | Q(user__is_staff=True)
    ).order_by('-created_at')
    ctx = _admin_sidebar()
    ctx['profiles'] = profiles
    return render(request, 'AdminApp/manage-employers.html', ctx)


@admin_required
def activate_employer(request, profile_id):
    """Manually activate an employer account without requiring payment."""
    if request.method != 'POST':
        return redirect('AdminApp:manage_employers')

    profile = get_object_or_404(EmployerProfile, pk=profile_id)
    if not profile.is_active:
        profile.is_active          = True
        profile.activation_paid_at = timezone.now()
        profile.payment_reference  = 'admin-activation'
        profile.save()
        messages.success(
            request,
            f'{profile.user.get_full_name()} has been activated as an employer.'
        )
    return redirect('AdminApp:manage_employers')


@admin_required
def review_documents(request):
    pending = CaregiverDocument.objects.filter(
        status=CaregiverDocument.STATUS_PENDING
    ).select_related('user').order_by('-uploaded_at')
    reviewed = CaregiverDocument.objects.exclude(
        status=CaregiverDocument.STATUS_PENDING
    ).select_related('user').order_by('-reviewed_at')[:50]
    ctx = _admin_sidebar()
    ctx.update({'pending': pending, 'reviewed': reviewed})
    return render(request, 'AdminApp/review-documents.html', ctx)


@admin_required
def manage_shifts(request):
    from Account.models import BookingProposal
    from django.db.models import Exists, OuterRef

    # Annotate shifts with whether they came from a negotiation using subquery
    negotiation_exists = BookingProposal.objects.filter(
        status=BookingProposal.STATUS_BOOKED,
        shift=OuterRef('pk'),
    )
    shifts = Shift.objects.annotate(
        from_negotiation=Exists(negotiation_exists)
    ).select_related('caregiver', 'employer').order_by('-created_at')

    pending_payout_count = ShiftLog.objects.filter(
        shift__status=Shift.STATUS_COMPLETED,
        payment_status=ShiftLog.PAY_PENDING,
        clock_out_time__isnull=False,
    ).count()

    ctx = _admin_sidebar()
    ctx['shifts'] = shifts
    ctx['pending_payout_count'] = pending_payout_count
    return render(request, 'AdminApp/manage-shifts.html', ctx)


@admin_required
def payout_queue(request):
    """Admin payout queue — completed shifts awaiting or already paid."""
    from decimal import Decimal as D
    from django.core.paginator import Paginator

    tab = request.GET.get('tab', 'pending')

    pending_logs = list(
        ShiftLog.objects.filter(
            shift__status=Shift.STATUS_COMPLETED,
            payment_status=ShiftLog.PAY_PENDING,
            clock_out_time__isnull=False,
            amount_earned__isnull=False,
        ).select_related(
            'shift', 'shift__caregiver', 'shift__employer',
            'shift__caregiver__caregiver_profile',
        ).order_by('-clock_out_time')
    )
    paid_logs_qs = ShiftLog.objects.filter(
        shift__status=Shift.STATUS_COMPLETED,
        payment_status=ShiftLog.PAY_PAID,
        clock_out_time__isnull=False,
    ).select_related(
        'shift', 'shift__caregiver', 'shift__employer',
        'shift__caregiver__caregiver_profile',
    ).order_by('-clock_out_time')

    # Paginate the paid tab by 15; pending stays unpaginated (needs action buttons visible)
    paginator    = Paginator(paid_logs_qs, 15)
    page_number  = request.GET.get('page', 1)
    paid_page    = paginator.get_page(page_number)

    # Use the full queryset for totals/counts
    paid_logs_all = list(paid_logs_qs)

    total_pending = sum(l.amount_earned or D('0') for l in pending_logs)
    total_paid    = sum(l.amount_earned or D('0') for l in paid_logs_all)

    _ratio = D('15') / D('85')
    admin_earned_pending = sum((l.amount_earned or D('0')) * _ratio for l in pending_logs)
    admin_earned_paid    = sum((l.amount_earned or D('0')) * _ratio for l in paid_logs_all)
    admin_earned_total   = admin_earned_pending + admin_earned_paid

    display_logs = paid_page if tab == 'paid' else pending_logs

    ctx = _admin_sidebar()
    ctx.update({
        'tab':                  tab,
        'display_logs':         display_logs,
        'pending_logs':         pending_logs,
        'paid_page':            paid_page,           # page object for pagination controls
        'pending_count':        len(pending_logs),
        'paid_count':           paid_logs_qs.count(),
        'total_pending':        total_pending,
        'total_paid':           total_paid,
        'admin_earned_pending': admin_earned_pending,
        'admin_earned_paid':    admin_earned_paid,
        'admin_earned_total':   admin_earned_total,
    })
    return render(request, 'AdminApp/payout-queue.html', ctx)


@admin_required
def mark_paid(request, log_pk):
    """Admin marks a ShiftLog payment as paid."""
    if request.method != 'POST':
        return redirect('AdminApp:payout_queue')
    log = get_object_or_404(ShiftLog, pk=log_pk)
    log.payment_status = ShiftLog.PAY_PAID
    log.save(update_fields=['payment_status'])
    # Notify caregiver their money has been sent
    try:
        send_payout_notification_email(log.shift.caregiver, log)
    except Exception:
        import logging as _log
        _log.getLogger(__name__).exception('Payout email failed for log %s', log.pk)
    messages.success(
        request,
        f'Payout for {log.shift.caregiver.get_full_name()} '
        f'(${log.amount_earned}) marked as paid.'
    )
    return redirect('AdminApp:payout_queue')


# ──────────────────────────────────────────────────────────────
# Document approve / reject
# ──────────────────────────────────────────────────────────────
@admin_required
def approve_document(request, doc_id):
    """Approve a single document. If all 5 required docs are now approved,
    automatically move the caregiver profile to pending_admin_review so the
    admin can activate the account."""
    if request.method != 'POST':
        return redirect('AdminApp:review_documents')

    doc = get_object_or_404(CaregiverDocument, pk=doc_id)
    note = request.POST.get('note', '').strip()

    doc.status = CaregiverDocument.STATUS_APPROVED
    doc.note = note
    doc.reviewed_at = timezone.now()
    doc.save()

    # Check whether all required docs for this caregiver are now approved
    caregiver = doc.user
    approved_types = set(
        CaregiverDocument.objects.filter(
            user=caregiver,
            status=CaregiverDocument.STATUS_APPROVED,
        ).values_list('doc_type', flat=True)
    )
    all_required_approved = all(dt in approved_types for dt in REQUIRED_DOC_TYPES)

    if all_required_approved:
        profile, _ = CaregiverProfile.objects.get_or_create(user=caregiver)
        if profile.status not in (CaregiverProfile.STATUS_ACTIVE, CaregiverProfile.STATUS_REJECTED):
            profile.status = CaregiverProfile.STATUS_ACTIVE
            profile.save()

            # Notify the caregiver their account has been activated
            try:
                send_caregiver_activation_email(caregiver)
            except Exception:
                import logging as _log
                _log.getLogger(__name__).exception(
                    'Caregiver activation email failed for user %s', caregiver.pk
                )
        messages.success(
            request,
            f'{doc.get_doc_type_display()} approved. '
            f'All required documents approved — {caregiver.get_full_name()} has been automatically activated.'
        )
    else:
        messages.success(request, f'{doc.get_doc_type_display()} approved.')

    return redirect('AdminApp:review_documents')


@admin_required
def reject_document(request, doc_id):
    """Reject a document and store an admin note explaining why."""
    if request.method != 'POST':
        return redirect('AdminApp:review_documents')

    doc = get_object_or_404(CaregiverDocument, pk=doc_id)
    note = request.POST.get('note', '').strip()

    doc.status = CaregiverDocument.STATUS_REJECTED
    doc.note = note
    doc.reviewed_at = timezone.now()
    doc.save()

    # Notify caregiver their document was rejected and ask them to re-upload
    try:
        send_document_rejected_email(doc.user, doc)
    except Exception:
        import logging as _log
        _log.getLogger(__name__).exception('Doc rejected email failed for doc %s', doc.pk)

    messages.warning(
        request,
        f'{doc.get_doc_type_display()} rejected for {doc.user.get_full_name()}.'
        + (f' Reason: {note}' if note else '')
    )
    return redirect('AdminApp:review_documents')


@admin_required
def revoke_document(request, doc_id):
    """Revoke a previously approved document (marks it rejected + re-queues caregiver review)."""
    if request.method != 'POST':
        return redirect('AdminApp:review_documents')

    doc = get_object_or_404(CaregiverDocument, pk=doc_id)
    note = request.POST.get('note', '').strip()

    doc.status = CaregiverDocument.STATUS_REJECTED
    doc.note = note or 'Approval revoked by admin.'
    doc.reviewed_at = timezone.now()
    doc.save()

    # Notify caregiver their previously-approved document was revoked
    try:
        send_document_rejected_email(doc.user, doc)
    except Exception:
        import logging as _log
        _log.getLogger(__name__).exception('Doc revoke email failed for doc %s', doc.pk)

    # Drop caregiver back to pending review so they must re-upload
    profile = CaregiverProfile.objects.filter(user=doc.user).first()
    if profile and profile.status == CaregiverProfile.STATUS_ACTIVE:
        profile.status = CaregiverProfile.STATUS_PENDING
        profile.save()

    messages.warning(
        request,
        f'{doc.get_doc_type_display()} approval revoked for {doc.user.get_full_name()}. '
        'Caregiver profile moved back to pending review.'
    )
    return redirect('AdminApp:review_documents')


@admin_required
def activate_caregiver(request, profile_id):
    """Manually activate a caregiver whose documents have all been approved."""
    if request.method != 'POST':
        return redirect('AdminApp:manage_caregivers')

    profile = get_object_or_404(CaregiverProfile, pk=profile_id)

    # Guard: all 5 required docs must be approved before activation
    approved_types = set(
        CaregiverDocument.objects.filter(
            user=profile.user,
            status=CaregiverDocument.STATUS_APPROVED,
        ).values_list('doc_type', flat=True)
    )
    missing = [dt for dt in REQUIRED_DOC_TYPES if dt not in approved_types]

    if missing:
        from Account.models import CaregiverDocument as CD
        labels = ', '.join(dict(CD.DOC_TYPE_CHOICES).get(dt, dt) for dt in missing)
        messages.error(
            request,
            f'Cannot activate {profile.user.get_full_name()} — '
            f'the following required documents have not been approved yet: {labels}.'
        )
        return redirect('AdminApp:manage_caregivers')

    was_active = profile.status == CaregiverProfile.STATUS_ACTIVE
    profile.status = CaregiverProfile.STATUS_ACTIVE
    profile.save()

    # Notify the caregiver their account has been activated — only when this
    # click actually changed the status (avoids duplicate emails on re-clicks).
    if not was_active:
        try:
            send_caregiver_activation_email(profile.user)
        except Exception:
            import logging as _log
            _log.getLogger(__name__).exception(
                'Caregiver activation email failed for user %s', profile.user.pk
            )

    messages.success(
        request,
        f'{profile.user.get_full_name()} has been activated as a verified caregiver.'
    )
    return redirect('AdminApp:manage_caregivers')


@admin_required
def delete_user(request, user_id):
    """Delete a user account. Admins cannot delete themselves."""
    if request.method != 'POST':
        return redirect('AdminApp:manage_users')

    user = get_object_or_404(CustomUser, pk=user_id)

    # Prevent admins from deleting themselves
    if user.id == request.user.id:
        messages.error(request, 'You cannot delete your own account.')
        return redirect('AdminApp:manage_users')

    # Prevent deleting superusers (extra safety)
    if user.is_superuser:
        messages.error(request, 'Cannot delete superuser accounts.')
        return redirect('AdminApp:manage_users')

    user_name = user.get_full_name() or user.username
    user.delete()
    messages.success(request, f'User "{user_name}" has been deleted.')
    return redirect('AdminApp:manage_users')


@admin_required
def serve_document(request, doc_id):
    """Serve a caregiver document inline in the browser so it previews instead of downloading.

    Works with both local FileSystemStorage and cloud backends (e.g. ImageKit)
    because it reads through the storage API instead of using .path directly.
    """
    doc = get_object_or_404(CaregiverDocument, pk=doc_id)

    if not doc.file:
        raise Http404('No file attached to this document.')

    # For cloud storage backends (ImageKit, S3, etc.) .path is not supported.
    # Redirect to the file's public URL instead of trying to stream it ourselves.
    storage_class = type(doc.file.storage).__name__  # noqa: F841 (kept for debugging)

    # If the backend supports absolute paths it's local disk — stream the file.
    # Otherwise redirect to the cloud URL.
    try:
        file_path = doc.file.path          # raises NotImplementedError on cloud backends
        if not os.path.exists(file_path):
            raise Http404('Document file not found.')
        mime_type, _ = mimetypes.guess_type(file_path)
        mime_type = mime_type or 'application/octet-stream'
        with open(file_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type=mime_type)
        filename = os.path.basename(file_path)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    except NotImplementedError:
        # Cloud storage — redirect to the hosted URL
        url = doc.file.url
        if not url:
            raise Http404('Document file not found.')
        return redirect(url)


@admin_required
def employer_payments(request):
    """Admin view — all employer payments (activation fees + shift bookings)."""
    from decimal import Decimal as D

    # Mark all unseen payments as seen now that the admin is viewing this page
    EmployerPayment.objects.filter(admin_seen=False).update(admin_seen=True)

    tab = request.GET.get('tab', 'all')

    all_payments = EmployerPayment.objects.select_related(
        'employer', 'shift', 'shift__caregiver'
    ).order_by('-paid_at')

    if tab == 'activation':
        display_payments = all_payments.filter(payment_type=EmployerPayment.TYPE_ACTIVATION)
    elif tab == 'booking':
        display_payments = all_payments.filter(payment_type=EmployerPayment.TYPE_BOOKING)
    else:
        display_payments = all_payments

    total_activation = all_payments.filter(
        payment_type=EmployerPayment.TYPE_ACTIVATION,
        status=EmployerPayment.STATUS_COMPLETED,
    )
    total_booking = all_payments.filter(
        payment_type=EmployerPayment.TYPE_BOOKING,
        status=EmployerPayment.STATUS_COMPLETED,
    )

    sum_activation = sum(p.amount for p in total_activation) or D('0')
    sum_booking    = sum(p.amount for p in total_booking)    or D('0')
    sum_total      = sum_activation + sum_booking

    active_employers = EmployerProfile.objects.filter(is_active=True).count()

    ctx = _admin_sidebar()
    ctx.update({
        'tab':              tab,
        'display_payments': display_payments,
        'sum_activation':   sum_activation,
        'sum_booking':      sum_booking,
        'sum_total':        sum_total,
        'active_employers': active_employers,
    })
    return render(request, 'AdminApp/employer-payments.html', ctx)


@admin_required
def dispute_list(request):
    """Admin — view and filter all disputes."""
    status_filter = request.GET.get('status', 'all')

    disputes_qs = Dispute.objects.select_related(
        'employer', 'caregiver', 'shift', 'payment'
    ).order_by('-created_at')

    if status_filter != 'all':
        disputes_qs = disputes_qs.filter(status=status_filter)

    counts = {
        'all':          Dispute.objects.count(),
        'open':         Dispute.objects.filter(status=Dispute.STATUS_OPEN).count(),
        'under_review': Dispute.objects.filter(status=Dispute.STATUS_UNDER_REVIEW).count(),
        'resolved':     Dispute.objects.filter(status=Dispute.STATUS_RESOLVED).count(),
        'dismissed':    Dispute.objects.filter(status=Dispute.STATUS_DISMISSED).count(),
    }

    ctx = _admin_sidebar()
    ctx.update({
        'disputes':      disputes_qs,
        'status_filter': status_filter,
        'counts':        counts,
        'status_choices': Dispute.STATUS_CHOICES,
    })
    return render(request, 'AdminApp/disputes.html', ctx)


@admin_required
def dispute_detail(request, dispute_pk):
    """Admin — view full dispute details and update status / add note."""
    dispute = get_object_or_404(Dispute, pk=dispute_pk)

    if request.method == 'POST':
        new_status = request.POST.get('status', '').strip()
        admin_note = request.POST.get('admin_note', '').strip()

        valid_statuses = [s[0] for s in Dispute.STATUS_CHOICES]
        if new_status not in valid_statuses:
            messages.error(request, 'Invalid status selected.')
        else:
            dispute.status     = new_status
            dispute.admin_note = admin_note
            if new_status in (Dispute.STATUS_RESOLVED, Dispute.STATUS_DISMISSED):
                dispute.resolved_at = timezone.now()
            else:
                dispute.resolved_at = None
            dispute.save()
            # Notify employer when dispute is closed
            if new_status in (Dispute.STATUS_RESOLVED, Dispute.STATUS_DISMISSED):
                try:
                    send_dispute_resolved_employer_email(dispute)
                except Exception:
                    import logging as _log
                    _log.getLogger(__name__).exception(
                        'Dispute resolved email failed for dispute %s', dispute.pk
                    )
            messages.success(
                request,
                f'Dispute #{dispute.pk} updated to "{dispute.get_status_display()}".'
            )
            return redirect('AdminApp:dispute_detail', dispute_pk=dispute.pk)

    ctx = _admin_sidebar()
    ctx.update({
        'dispute':        dispute,
        'status_choices': Dispute.STATUS_CHOICES,
    })
    return render(request, 'AdminApp/dispute-detail.html', ctx)


# ──────────────────────────────────────────────────────────────
# FAQ management
# ──────────────────────────────────────────────────────────────
@admin_required
def faq_list(request):
    """List every FAQ with an optional search filter."""
    q = request.GET.get('q', '').strip()
    faqs = Faq.objects.all().order_by('order', 'category', 'question')
    if q:
        faqs = faqs.filter(
            Q(question__icontains=q) | Q(answer__icontains=q)
        )
    ctx = _admin_sidebar()
    ctx['faqs'] = faqs
    ctx['search_q'] = q
    return render(request, 'AdminApp/faq-list.html', ctx)


@admin_required
def faq_edit(request, faq_id=None):
    """Create or update an FAQ.  ``faq_id=None`` → create."""
    if faq_id is not None:
        faq = get_object_or_404(Faq, pk=faq_id)
    else:
        faq = None

    if request.method == 'POST':
        form = FaqForm(request.POST, instance=faq)
        if form.is_valid():
            form.save()
            if faq:
                messages.success(request, 'FAQ updated successfully.')
            else:
                messages.success(request, 'FAQ added successfully.')
            return redirect('AdminApp:faq_list')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = FaqForm(instance=faq)

    ctx = _admin_sidebar()
    ctx['form'] = form
    ctx['faq'] = faq
    return render(request, 'AdminApp/faq-form.html', ctx)


@admin_required
def faq_delete(request, faq_id):
    """Delete an FAQ (POST only)."""
    if request.method != 'POST':
        return redirect('AdminApp:faq_list')
    faq = get_object_or_404(Faq, pk=faq_id)
    faq.delete()
    messages.success(request, f'FAQ "{faq.question[:50]}" deleted.')
    return redirect('AdminApp:faq_list')


def public_faqs(request):
    """Return active FAQs as JSON for public consumption."""
    from django.utils.html import escape
    faqs = Faq.objects.filter(is_active=True).order_by('order', 'category', 'question')
    data = [
        {
            'id': faq.id,
            'question': escape(faq.question),
            'answer': escape(faq.answer),
            'category': faq.category,
            'order': faq.order,
        }
        for faq in faqs
    ]
    return JsonResponse({'faqs': data})


# ──────────────────────────────────────────────────────────────
# Service management
# ──────────────────────────────────────────────────────────────
@admin_required
def service_list(request):
    """List every service with an optional search filter."""
    q = request.GET.get('q', '').strip()
    services = Service.objects.all().order_by('order', 'title')
    if q:
        services = services.filter(
            Q(title__icontains=q) | Q(description__icontains=q) | Q(slug__icontains=q)
        )
    ctx = _admin_sidebar()
    ctx['services'] = services
    ctx['search_q'] = q
    return render(request, 'AdminApp/service-list.html', ctx)


@admin_required
def service_edit(request, service_id=None):
    """Create or update a service.  ``service_id=None`` → create."""
    if service_id is not None:
        service = get_object_or_404(Service, pk=service_id)
    else:
        service = None

    if request.method == 'POST':
        form = ServiceForm(request.POST, request.FILES, instance=service)
        if form.is_valid():
            form.save()
            if service:
                messages.success(request, 'Service updated successfully.')
            else:
                messages.success(request, 'Service added successfully.')
            return redirect('AdminApp:service_list')
        messages.error(request, 'Please correct the errors below.')
    else:
        form = ServiceForm(instance=service)

    ctx = _admin_sidebar()
    ctx['form'] = form
    ctx['service'] = service
    return render(request, 'AdminApp/service-form.html', ctx)


@admin_required
def service_delete(request, service_id):
    """Delete a service (POST only)."""
    if request.method != 'POST':
        return redirect('AdminApp:service_list')
    service = get_object_or_404(Service, pk=service_id)
    service.delete()
    messages.success(request, f'Service "{service.title}" deleted.')
    return redirect('AdminApp:service_list')


def public_services(request):
    """Return active services as JSON for public consumption."""
    from django.utils.html import escape
    services = Service.objects.filter(is_active=True).order_by('order', 'title')
    data = []
    for s in services:
        item = {
            'id': s.id,
            'title': escape(s.title),
            'slug': s.slug,
            'short_description': escape(s.short_description),
            'description': s.description,
            'icon': s.icon or 'fa-hand-holding-heart',
            'rate': escape(s.rate) if s.rate else '',
            'rate_from': escape(s.rate_from) if s.rate_from else '',
            'rate_amount': escape(s.rate_amount) if s.rate_amount else '',
            'tag': escape(s.tag) if s.tag else '',
            'tag_color': s.tag_color,
            'order': s.order,
            'image_url': s.image.url if s.image else '',
        }
        data.append(item)
    return JsonResponse({'services': data})
