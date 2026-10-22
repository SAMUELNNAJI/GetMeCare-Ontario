import time

from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Avg, Count, Q
from Account.models import CaregiverProfile, JobPosting, Shift
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
    ).select_related('user').annotate(
        avg_rating=Avg(
            'user__received_caregiver_reviews__rating',
            filter=Q(user__received_caregiver_reviews__shift__status=Shift.STATUS_COMPLETED),
        ),
        review_count=Count(
            'user__received_caregiver_reviews',
            filter=Q(user__received_caregiver_reviews__shift__status=Shift.STATUS_COMPLETED),
        ),
    ).order_by('user__first_name')

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
    from Caregiver.antispam import generate_contact_challenge, check_contact_submission
    from django.contrib import messages as dj_messages

    if request.method == 'POST':
        is_valid, err_msg, is_bot = check_contact_submission(request)

        # ── Honeypot or bot caught: fake success silently (bots move on, zero spam sent) ──
        if is_bot:
            dj_messages.success(request, "Your message has been sent! We'll get back to you within 1–2 business days.")
            n1, n2, tok = generate_contact_challenge()
            return render(request, 'Caregiver/contact.html', {
                'captcha_n1': n1, 'captcha_n2': n2, 'captcha_token': tok
            })

        # ── Verification failed ──
        if not is_valid:
            dj_messages.error(request, err_msg)
            n1, n2, tok = generate_contact_challenge()
            return render(request, 'Caregiver/contact.html', {
                'captcha_n1': n1, 'captcha_n2': n2, 'captcha_token': tok,
                'form_data': request.POST,
            })

        first_name = request.POST.get('firstName', '').strip()
        last_name  = request.POST.get('lastName', '').strip()
        email      = request.POST.get('email', '').strip()
        phone      = request.POST.get('phone', '').strip()
        role       = request.POST.get('role', '').strip()
        subject    = request.POST.get('subject', '').strip()
        message    = request.POST.get('message', '').strip()

        if first_name and last_name and email and role and subject and message:
            plain_body = (
                f"New verified contact form inquiry:\n\n"
                f"Name: {first_name} {last_name}\n"
                f"Email: {email}\n"
                f"Phone: {phone or 'Not provided'}\n"
                f"Role: {role}\n\n"
                f"Subject: {subject}\n\n"
                f"Message:\n{message}"
            )

            ok = False
            try:
                from django.conf import settings as _s
                from django.core.mail import get_connection, EmailMessage

                gmail_user = getattr(_s, 'GMAIL_USER', '') or CONTACT_FORM_INBOX
                gmail_pass = getattr(_s, 'GMAIL_APP_PASSWORD', '')

                clean_pass = (gmail_pass or '').replace(' ', '').strip()
                if len(clean_pass) >= 32 and clean_pass[:16] == clean_pass[16:32]:
                    clean_pass = clean_pass[:16]

                if not gmail_user or not clean_pass:
                    import logging as _log
                    _log.getLogger(__name__).error(
                        "Contact form cannot send via Gmail: GMAIL_USER or GMAIL_APP_PASSWORD missing."
                    )
                else:
                    try:
                        conn = get_connection(
                            backend='django.core.mail.backends.smtp.EmailBackend',
                            host='smtp.gmail.com',
                            port=587,
                            username=gmail_user,
                            password=clean_pass,
                            use_tls=True,
                            timeout=15,
                        )
                        email_msg = EmailMessage(
                            subject=f'[Contact Form] {subject} — {first_name} {last_name}',
                            body=plain_body,
                            from_email=gmail_user,
                            to=[CONTACT_FORM_INBOX],
                            reply_to=[email],
                            connection=conn,
                        )
                        email_msg.send(fail_silently=False)
                        ok = True
                    except Exception:
                        # Fallback to SSL 465
                        conn_ssl = get_connection(
                            backend='django.core.mail.backends.smtp.EmailBackend',
                            host='smtp.gmail.com',
                            port=465,
                            username=gmail_user,
                            password=clean_pass,
                            use_ssl=True,
                            timeout=15,
                        )
                        email_msg = EmailMessage(
                            subject=f'[Contact Form] {subject} — {first_name} {last_name}',
                            body=plain_body,
                            from_email=gmail_user,
                            to=[CONTACT_FORM_INBOX],
                            reply_to=[email],
                            connection=conn_ssl,
                        )
                        email_msg.send(fail_silently=False)
                        ok = True
            except Exception as exc:
                import logging as _log
                _log.getLogger(__name__).exception('Contact form email failed via Gmail: %s', exc)
                ok = False

            if ok:
                dj_messages.success(request, "Your message has been sent! We'll get back to you within 1–2 business days.")
            else:
                dj_messages.error(request, "Sorry, there was a problem sending your message. Please email us directly at getmecareontario@gmail.com.")
        else:
            dj_messages.error(request, 'Please fill in all required fields.')

        n1, n2, tok = generate_contact_challenge()
        return render(request, 'Caregiver/contact.html', {
            'captcha_n1': n1, 'captcha_n2': n2, 'captcha_token': tok
        })

    # GET request
    n1, n2, tok = generate_contact_challenge()
    return render(request, 'Caregiver/contact.html', {
        'captcha_n1': n1, 'captcha_n2': n2, 'captcha_token': tok
    })


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
    # Star-fill percentage for the 1-5 public credibility rating (real data,
    # averaged from completed-shift employer reviews only).
    try:
        rating_value = profile.rating or 0
    except Exception:
        rating_value = 0
    rating_pct = int(round(float(rating_value) / 5 * 100))

    return render(request, 'Caregiver/caregiver-profile.html', {
        'profile': profile,
        'rating_pct': rating_pct,
    })
