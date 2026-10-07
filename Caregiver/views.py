import time

from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from Account.models import CaregiverProfile, JobPosting
from AdminApp.models import Faq, Service

# Contact-form submissions are delivered to this inbox (admin notification).
CONTACT_FORM_INBOX = 'getmecareontario@gmail.com'


def home(request):
    verified_caregivers = CaregiverProfile.objects.filter(
        status=CaregiverProfile.STATUS_ACTIVE,
        account_status='active',
    ).select_related('user').order_by('-created_at')[:3]
    return render(request, 'Caregiver/index.html', {
        'verified_caregivers': verified_caregivers,
    })


def browse(request):
    """Browse caregivers — paginated 20, with city / care-type / rate filters."""
    qs = CaregiverProfile.objects.filter(
        status=CaregiverProfile.STATUS_ACTIVE,
        account_status='active',
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
        .filter(status=CaregiverProfile.STATUS_ACTIVE, account_status='active')
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
    faqs = Faq.objects.filter(is_active=True).order_by('order', 'category', 'question')
    return render(request, 'Caregiver/how_it_works.html', {'faqs': faqs})


def services(request):
    services = Service.objects.filter(is_active=True).order_by('order', 'title')
    return render(request, 'Caregiver/services.html', {'services': services})


def contact(request):
    if request.method == 'POST':
        first_name = request.POST.get('firstName', '').strip()
        last_name  = request.POST.get('lastName', '').strip()
        email      = request.POST.get('email', '').strip()
        phone      = request.POST.get('phone', '').strip()
        role       = request.POST.get('role', '').strip()
        subject    = request.POST.get('subject', '').strip()
        message    = request.POST.get('message', '').strip()

        from django.contrib import messages as dj_messages

        # ── 1. Honeypot: bots fill in the hidden "website" field ──
        honeypot = request.POST.get('website', '').strip()
        if honeypot:
            # Silently succeed — don't tell bots they were blocked
            dj_messages.success(request, "Your message has been sent! We'll get back to you within 1–2 business days.")
            return render(request, 'Caregiver/contact.html')

        # ── 2. Timing check: reject if submitted in under 4 seconds ──
        try:
            loaded_at = int(request.POST.get('form_loaded_at', 0))
            elapsed   = int(time.time()) - loaded_at
        except (ValueError, TypeError):
            elapsed = 999
        if elapsed < 4:
            dj_messages.success(request, "Your message has been sent! We'll get back to you within 1–2 business days.")
            return render(request, 'Caregiver/contact.html')

        # ── 3. Rate limit: max 3 submissions per IP per hour ──
        import hashlib
        from django.core.cache import cache
        ip_raw   = (request.META.get('HTTP_X_FORWARDED_FOR') or request.META.get('REMOTE_ADDR', '')).split(',')[0].strip()
        ip_key   = 'contact_rl_' + hashlib.md5(ip_raw.encode()).hexdigest()
        rl_count = cache.get(ip_key, 0)
        if rl_count >= 3:
            dj_messages.error(request, 'Too many messages sent. Please wait a while before trying again.')
            return render(request, 'Caregiver/contact.html')
        cache.set(ip_key, rl_count + 1, timeout=3600)  # 1 hour window

        if first_name and last_name and email and role and subject and message:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart

            # ── Send directly via Gmail SMTP — bypasses ZeptoMail entirely ──
            plain_body = (
                f"New contact form submission\n\n"
                f"Name: {first_name} {last_name}\n"
                f"Email: {email}\n"
                f"Phone: {phone or 'Not provided'}\n"
                f"Role: {role}\n\n"
                f"Subject: {subject}\n\n"
                f"Message:\n{message}"
            )

            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'[Contact Form] {subject} — {first_name} {last_name}'
            msg['From']    = CONTACT_FORM_INBOX
            msg['To']      = CONTACT_FORM_INBOX
            msg['Reply-To'] = email  # reply goes straight to the visitor

            msg.attach(MIMEText(plain_body, 'plain'))

            ok = False
            try:
                from django.conf import settings as _s
                gmail_user = getattr(_s, 'GMAIL_USER', '')
                gmail_pass = getattr(_s, 'GMAIL_APP_PASSWORD', '')
                if gmail_user and gmail_pass:
                    with smtplib.SMTP_SSL('smtp.gmail.com', 465, timeout=15) as server:
                        server.login(gmail_user, gmail_pass)
                        server.sendmail(gmail_user, [CONTACT_FORM_INBOX], msg.as_string())
                    ok = True
                else:
                    # Fallback: still use Django mail if Gmail not configured
                    from GETMECARE.email_utils import send_transactional_email, _wrap, SITE_NAME as SN
                    ok = send_transactional_email(
                        subject    = f'[Contact Form] {subject} — {first_name} {last_name}',
                        to_email   = CONTACT_FORM_INBOX,
                        html_body  = _wrap(f'<h2>Contact Form</h2><pre>{plain_body}</pre>'),
                        plain_body = plain_body,
                    )
            except Exception:
                import logging as _log
                _log.getLogger(__name__).exception('Contact form email failed')
                ok = False

            if ok:
                dj_messages.success(request, "Your message has been sent! We'll get back to you within 1–2 business days.")
            else:
                dj_messages.error(request, "Sorry, there was a problem sending your message. Please email us directly at getmecareontario@gmail.com.")
        else:
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
        account_status='active',
    )
    return render(request, 'Caregiver/caregiver-profile.html', {
        'profile': profile,
    })
