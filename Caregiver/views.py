from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from Account.models import CaregiverProfile, JobPosting


def home(request):
    verified_caregivers = CaregiverProfile.objects.filter(
        status=CaregiverProfile.STATUS_ACTIVE
    ).select_related('user').order_by('-created_at')[:3]
    return render(request, 'Caregiver/index.html', {
        'verified_caregivers': verified_caregivers,
    })


def browse(request):
    """Browse caregivers — paginated 20, with city / care-type / rate filters."""
    qs = CaregiverProfile.objects.filter(
        status=CaregiverProfile.STATUS_ACTIVE
    ).select_related('user').order_by('user__first_name')

    # ── Filters ──────────────────────────────────────────────
    city      = request.GET.get('city', '').strip()
    care_type = request.GET.get('care_type', '').strip()
    rate_min  = request.GET.get('rate_min', '')
    rate_max  = request.GET.get('rate_max', '')
    sort      = request.GET.get('sort', '')

    if city:
        qs = qs.filter(city__icontains=city)
    if care_type:
        qs = qs.filter(skills__icontains=care_type)
    if rate_min:
        try:
            qs = qs.filter(hourly_rate__gte=float(rate_min))
        except ValueError:
            pass
    if rate_max:
        try:
            qs = qs.filter(hourly_rate__lte=float(rate_max))
        except ValueError:
            pass

    if sort == 'rate_asc':
        qs = qs.order_by('hourly_rate')
    elif sort == 'rate_desc':
        qs = qs.order_by('-hourly_rate')
    elif sort == 'newest':
        qs = qs.order_by('-created_at')
    # default: alphabetical (already set above)

    paginator  = Paginator(qs, 20)
    page_num   = request.GET.get('page', 1)
    page_obj   = paginator.get_page(page_num)

    # Build distinct city list for filter sidebar
    cities = (
        CaregiverProfile.objects
        .filter(status=CaregiverProfile.STATUS_ACTIVE)
        .exclude(city='')
        .values_list('city', flat=True)
        .distinct()
        .order_by('city')
    )

    return render(request, 'Caregiver/browse.html', {
        'page_obj':   page_obj,
        'total':      paginator.count,
        'city':       city,
        'care_type':  care_type,
        'rate_min':   rate_min,
        'rate_max':   rate_max,
        'sort':       sort,
        'cities':     cities,
    })


def browse_jobs(request):
    """Browse open job postings — paginated 30, with city / care-type / schedule filters."""
    qs = JobPosting.objects.filter(
        status=JobPosting.STATUS_OPEN
    ).select_related('employer').order_by('-created_at')

    # ── Filters ──────────────────────────────────────────────
    city      = request.GET.get('city', '').strip()
    care_type = request.GET.get('care_type', '').strip()
    schedule  = request.GET.get('schedule', '').strip()
    rate_min  = request.GET.get('rate_min', '')
    rate_max  = request.GET.get('rate_max', '')
    sort      = request.GET.get('sort', '')

    if city:
        qs = qs.filter(city__icontains=city)
    if care_type:
        qs = qs.filter(care_type=care_type)
    if schedule:
        qs = qs.filter(schedule=schedule)
    if rate_min:
        try:
            qs = qs.filter(hourly_rate__gte=float(rate_min))
        except ValueError:
            pass
    if rate_max:
        try:
            qs = qs.filter(hourly_rate__lte=float(rate_max))
        except ValueError:
            pass

    if sort == 'rate_asc':
        qs = qs.order_by('hourly_rate')
    elif sort == 'rate_desc':
        qs = qs.order_by('-hourly_rate')
    elif sort == 'oldest':
        qs = qs.order_by('created_at')
    # default: newest first (already set above)

    paginator = Paginator(qs, 30)
    page_num  = request.GET.get('page', 1)
    page_obj  = paginator.get_page(page_num)

    # Distinct cities for sidebar
    cities = (
        JobPosting.objects
        .filter(status=JobPosting.STATUS_OPEN)
        .exclude(city='')
        .values_list('city', flat=True)
        .distinct()
        .order_by('city')
    )

    return render(request, 'Caregiver/browse-jobs.html', {
        'page_obj':   page_obj,
        'total':      paginator.count,
        'city':       city,
        'care_type':  care_type,
        'schedule':   schedule,
        'rate_min':   rate_min,
        'rate_max':   rate_max,
        'sort':       sort,
        'cities':     cities,
        'care_type_choices': JobPosting.CARE_TYPE_CHOICES,
        'schedule_choices':  JobPosting.SCHEDULE_CHOICES,
    })


def how_it_works(request):
    return render(request, 'Caregiver/how_it_works.html')


def services(request):
    return render(request, 'Caregiver/services.html')


def contact(request):
    if request.method == 'POST':
        first_name = request.POST.get('firstName', '').strip()
        last_name  = request.POST.get('lastName', '').strip()
        email      = request.POST.get('email', '').strip()
        phone      = request.POST.get('phone', '').strip()
        role       = request.POST.get('role', '').strip()
        subject    = request.POST.get('subject', '').strip()
        message    = request.POST.get('message', '').strip()

        if first_name and last_name and email and role and subject and message:
            from GETMECARE.email_utils import send_transactional_email, _wrap, ADMIN_EMAIL, SITE_NAME

            # ── Branded HTML email to admin ───────────────────
            html_content = f"""
            <h2>New Contact Form Submission</h2>
            <p>A visitor has submitted the contact form on <strong>{SITE_NAME}</strong>.</p>
            <div class="info-box">
              <p><strong>Name:</strong> {first_name} {last_name}</p>
              <p><strong>Email:</strong> <a href="mailto:{email}">{email}</a></p>
              <p><strong>Phone:</strong> {phone if phone else 'Not provided'}</p>
              <p><strong>Role:</strong> {role}</p>
              <p><strong>Subject:</strong> {subject}</p>
            </div>
            <p><strong>Message:</strong></p>
            <div class="info-box" style="white-space:pre-wrap;">{message}</div>
            <p style="margin-top:16px;">
              Reply directly to this email or write to
              <a href="mailto:{email}">{email}</a> to respond.
            </p>
            """

            ok = send_transactional_email(
                subject   = f'[Contact Form] {subject} — {first_name} {last_name}',
                to_email  = ADMIN_EMAIL,          # always info@getmecare-ontario.com
                html_body = _wrap(html_content),
                plain_body = (
                    f"New contact form submission\n\n"
                    f"Name: {first_name} {last_name}\n"
                    f"Email: {email}\n"
                    f"Phone: {phone or 'Not provided'}\n"
                    f"Role: {role}\n\n"
                    f"Subject: {subject}\n\n"
                    f"Message:\n{message}"
                ),
            )

            # ── Auto-reply to sender ──────────────────────────
            reply_content = f"""
            <h2>We received your message!</h2>
            <p>Hi {first_name}, thank you for reaching out to {SITE_NAME}.</p>
            <p>We have received your message and our team will get back to you
               within <strong>1–2 business days</strong>.</p>
            <div class="info-box">
              <p><strong>Your subject:</strong> {subject}</p>
            </div>
            <p>If your matter is urgent, you can also email us directly at
               <a href="mailto:{ADMIN_EMAIL}">{ADMIN_EMAIL}</a>.</p>
            """
            send_transactional_email(
                subject   = f'[{SITE_NAME}] We received your message — {subject}',
                to_email  = email,
                html_body = _wrap(reply_content),
            )

            if ok:
                from django.contrib import messages as dj_messages
                dj_messages.success(request, "Your message has been sent! We'll get back to you within 1–2 business days.")
            else:
                from django.contrib import messages as dj_messages
                dj_messages.error(request, "Sorry, there was a problem sending your message. Please email us directly at info@getmecare-ontario.com.")
        else:
            from django.contrib import messages as dj_messages
            dj_messages.error(request, 'Please fill in all required fields.')

        return render(request, 'Caregiver/contact.html')

    return render(request, 'Caregiver/contact.html')


def privacy(request):
    return render(request, 'Caregiver/privacy.html')


def terms(request):
    return render(request, 'Caregiver/terms.html')


def caregiver_profile(request, pk):
    """Public profile page for a single active caregiver."""
    profile = get_object_or_404(
        CaregiverProfile.objects.select_related('user'),
        pk=pk,
        status=CaregiverProfile.STATUS_ACTIVE,
    )
    return render(request, 'Caregiver/caregiver-profile.html', {
        'profile': profile,
    })
