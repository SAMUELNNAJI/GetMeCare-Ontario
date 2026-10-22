"""Candidate matching and WhatsApp delivery helpers.

This module implements the two hands-off automation steps that the
request-notification webhook starts but the rest of the codebase left
unfinished:

1. ``suggest_candidates`` – given a public job request (care type, city,
   hours/week, hourly rate), return the top caregivers from the database
   that best match the request.  The view renders these to the admin
   dashboard for manual approval.
2. ``send_candidate_profile_screenshot`` – send a caregiver's profile
   details to the requesting employer via the WhatsApp gateway.

Both are deliberately provider-agnostic: they only depend on
``GETMECARE.whatsapp.notify_admin`` so an email outage can never suppress
the WhatsApp escalation.
"""

import logging
from decimal import Decimal

from django.conf import settings

from Account.models import CustomUser, CaregiverProfile
from GETMECARE.whatsapp import notify_admin

logger = logging.getLogger(__name__)


def _parse_hpm(value) -> Decimal:
    """Coerce a string/int Decimal to a half-precision decimal."""
    if value is None:
        return Decimal('0')
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0')


def suggest_candidates(
    *,
    care_type: str = '',
    city: str = '',
    hours_per_week: str = '',
    hourly_rate: str = '',
    limit: int = 6,
) -> list[CaregiverProfile]:
    """Return the best-matching active, verified caregivers for a public job request.

    Scoring rules:
      - Care type matches caregiver specialties: +4 pts
      - City match (prefix or contains):         +3 pts
      - Availability flexible or has hours:      +1 pt
      - Rate within 25% of target budget:        +2 pts
      - Rate below target budget:                +1 pt
    Ordered by score desc, then hourly_rate asc.
    """
    candidates = list(
        CaregiverProfile.objects.filter(
            status=CaregiverProfile.STATUS_ACTIVE,
            account_status=CaregiverProfile.ACCOUNT_ACTIVE,
        ).select_related('user')
    )

    try:
        target_rate = _parse_hpm(hourly_rate).quantize(Decimal('0.01'))
    except Exception:
        target_rate = Decimal('0')

    norm_care_type = (care_type or '').lower().strip()
    norm_city = (city or '').lower().strip()

    scored = []
    for profile in candidates:
        score = Decimal('0')
        p_care = (profile.care_type or '').lower()
        if norm_care_type and (norm_care_type in p_care or p_care in norm_care_type):
            score += Decimal('4')

        p_city = (profile.city or '').lower()
        if norm_city and (p_city.startswith(norm_city[:3]) or norm_city in p_city):
            score += Decimal('3')

        if profile.hours_available is None or profile.hours_available == 0:
            score += Decimal('1')

        if target_rate and target_rate > Decimal('0') and profile.hourly_rate:
            if abs(profile.hourly_rate - target_rate) <= target_rate * Decimal('0.25'):
                score += Decimal('2')
            elif profile.hourly_rate < target_rate:
                score += Decimal('1')

        scored.append((score, profile))

    scored.sort(key=lambda item: (-item[0], item[1].hourly_rate if item[1].hourly_rate else Decimal('999')))
    return [profile for _, profile in scored[:limit]]


def format_candidate_screenshot(profile: CaregiverProfile, site_domain: str = 'getmecare-ontario.com') -> str:
    """Render a caregiver's verified profile as a text overview suitable for WhatsApp."""
    user = profile.user
    care_types = ', '.join(profile.care_types_display) if hasattr(profile, 'care_types_display') and profile.care_types_display else (profile.care_type or 'Personal Support & Care')
    skills = ', '.join(profile.skills_list[:4]) if hasattr(profile, 'skills_list') and profile.skills_list else (profile.skills or 'Personal Care, Companionship')
    rate_str = f"${profile.hourly_rate} CAD/hr" if profile.hourly_rate else "Rate on request"
    return (
        f"👩‍⚕️ CAREGIVER CANDIDATE PROFILE — GetMeCare Ontario\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Candidate:  {user.get_full_name()}\n"
        f"Role:       Certified PSW (Admin Vetted)\n"
        f"Location:   {profile.city or 'Ontario'}\n"
        f"Rate:       {rate_str}\n"
        f"Care Focus: {care_types}\n"
        f"Key Skills: {skills}\n"
        f"Status:     ✓ ID Verified & VSC Background Cleared\n"
        f"Caregiver ID: #{profile.pk}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"Platform: https://{site_domain}/caregiver/{profile.pk}/"
    )


def send_candidate_profile_screenshot(
    *,
    profile: CaregiverProfile,
    candidate_phone: str,
    referrer: str,
) -> bool:
    """Send one candidate's profile screenshot to a phone number.

    ``referrer`` is the event name used in the payload so the admin
    dashboard can dedupe/display which request triggered the send.
    """
    message = format_candidate_screenshot(profile)
    try:
        return notify_admin(
            message,
            event='candidate_profile_screenshot',
            payload={
                'caregiver_id': profile.pk,
                'employer_phone': candidate_phone,
                'referrer': referrer,
            },
        )
    except Exception:
        logger.exception(
            'Failed to send candidate profile screenshot: caregiver=%s',
            profile.pk,
        )
        return False


def send_candidate_profile_email(
    *,
    profile: CaregiverProfile,
    job,
    site_domain: str = 'getmecare-ontario.com',
) -> bool:
    """Send candidate profile directly to the employer via email."""
    try:
        from GETMECARE.email_utils import send_single_candidate_profile_to_employer_email
        return send_single_candidate_profile_to_employer_email(
            job=job,
            profile=profile,
            site_domain=site_domain,
        )
    except Exception:
        logger.exception('Failed to email candidate profile: caregiver=%s', profile.pk)
        return False
