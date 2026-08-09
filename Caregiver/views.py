from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
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
