"""
Management command: send_reminder_emails

Runs every 48 hours via the APScheduler started in Account/apps.py.
Safe to run manually at any time — skips recipients whose last reminder
was less than 2 days ago.

Caregiver reminders (only sent while status is PENDING or INACTIVE —
never sent to ACTIVE or REJECTED caregivers):
  1. Documents incomplete  → send_document_reminder_email()
  2. Profile incomplete    → send_profile_reminder_email()

Employer reminders (only sent while EmployerProfile.is_active is False):
  3. Account not activated → send_employer_activation_reminder_email()
     Also covers employers who signed up but never created an EmployerProfile
     (their profile is created on first visit to activate_account or dashboard).

Usage:
    python manage.py send_reminder_emails            # live run
    python manage.py send_reminder_emails --dry-run  # print only, no emails
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from Account.models import CaregiverProfile, EmployerProfile, CustomUser
from Account.forms import REQUIRED_DOC_TYPES
from GETMECARE.email_utils import (
    send_document_reminder_email,
    send_profile_reminder_email,
    send_employer_activation_reminder_email,
)

logger = logging.getLogger(__name__)

REMINDER_INTERVAL = timedelta(days=2)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _uploaded_doc_types(profile) -> set:
    return set(
        profile.user.documents.filter(
            doc_type__in=REQUIRED_DOC_TYPES
        ).values_list('doc_type', flat=True).distinct()
    )


def _profile_missing_fields(profile) -> list:
    missing = []
    if not profile.hourly_rate:
        missing.append('Hourly rate')
    if not profile.city:
        missing.append('City / location')
    if not profile.care_type:
        missing.append('Care types (what care you provide)')
    if not profile.skills:
        missing.append('Skills / specialisations')
    if not profile.profile_image:
        missing.append('Profile photo')
    return missing


def _is_due(last_sent, cutoff) -> bool:
    """True when a reminder has never been sent OR was sent before the cutoff."""
    return last_sent is None or last_sent <= cutoff


# ──────────────────────────────────────────────────────────────
# Command
# ──────────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = 'Send every-2-days reminder emails (caregivers: docs/profile; employers: activation)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print who would be emailed without sending anything',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now    = timezone.now()
        cutoff = now - REMINDER_INTERVAL

        doc_sent      = 0
        profile_sent  = 0
        employer_sent = 0

        # ══════════════════════════════════════════════════════
        # CAREGIVER REMINDERS
        # Only PENDING and INACTIVE — explicitly excludes ACTIVE and REJECTED.
        # A caregiver with STATUS_ACTIVE has already been verified;
        # STATUS_REJECTED accounts are not actionable.
        # ══════════════════════════════════════════════════════
        caregiver_profiles = (
            CaregiverProfile.objects
            .filter(status__in=[
                CaregiverProfile.STATUS_PENDING,
                CaregiverProfile.STATUS_INACTIVE,
            ])
            .select_related('user')
            .exclude(user__email='')
        )

        for profile in caregiver_profiles:
            user = profile.user

            # Guard: skip if somehow status slipped to active between query and loop
            if profile.status == CaregiverProfile.STATUS_ACTIVE:
                continue

            # ── 1. Document reminder ──────────────────────────
            uploaded      = _uploaded_doc_types(profile)
            docs_complete = len(uploaded) >= len(REQUIRED_DOC_TYPES)

            if not docs_complete and _is_due(profile.last_doc_reminder_sent, cutoff):
                if dry_run:
                    self.stdout.write(
                        f'[DRY-RUN] Doc reminder → {user.email} '
                        f'({len(uploaded)}/{len(REQUIRED_DOC_TYPES)} docs)'
                    )
                else:
                    ok = send_document_reminder_email(
                        user=user,
                        uploaded_count=len(uploaded),
                        required_count=len(REQUIRED_DOC_TYPES),
                    )
                    if ok:
                        profile.last_doc_reminder_sent = now
                        profile.save(update_fields=['last_doc_reminder_sent'])
                        doc_sent += 1
                        logger.info('Doc reminder sent → %s', user.email)
                    else:
                        logger.warning('Doc reminder FAILED → %s', user.email)

            # ── 2. Profile reminder ───────────────────────────
            missing = _profile_missing_fields(profile)

            if missing and _is_due(profile.last_profile_reminder_sent, cutoff):
                if dry_run:
                    self.stdout.write(
                        f'[DRY-RUN] Profile reminder → {user.email} '
                        f'(missing: {", ".join(missing)})'
                    )
                else:
                    ok = send_profile_reminder_email(
                        user=user,
                        missing_fields=missing,
                    )
                    if ok:
                        profile.last_profile_reminder_sent = now
                        profile.save(update_fields=['last_profile_reminder_sent'])
                        profile_sent += 1
                        logger.info('Profile reminder sent → %s', user.email)
                    else:
                        logger.warning('Profile reminder FAILED → %s', user.email)

        # ══════════════════════════════════════════════════════
        # EMPLOYER ACTIVATION REMINDERS
        # Target: employers whose EmployerProfile.is_active == False.
        # Also catches employer users who never visited the activate page
        # (no EmployerProfile row yet) — we create a lightweight profile
        # on the fly so we can track the last reminder timestamp.
        # ══════════════════════════════════════════════════════
        employer_users = (
            CustomUser.objects
            .filter(role=CustomUser.EMPLOYER, is_staff=False, is_superuser=False)
            .exclude(email='')
        )

        for employer in employer_users:
            # get_or_create so we can always store last_activation_reminder_sent
            ep, _ = EmployerProfile.objects.get_or_create(user=employer)

            # Skip already-activated accounts
            if ep.is_active:
                continue

            if _is_due(ep.last_activation_reminder_sent, cutoff):
                if dry_run:
                    self.stdout.write(
                        f'[DRY-RUN] Employer activation reminder → {employer.email}'
                    )
                else:
                    ok = send_employer_activation_reminder_email(employer)
                    if ok:
                        ep.last_activation_reminder_sent = now
                        ep.save(update_fields=['last_activation_reminder_sent'])
                        employer_sent += 1
                        logger.info('Employer activation reminder sent → %s', employer.email)
                    else:
                        logger.warning('Employer activation reminder FAILED → %s', employer.email)

        # ── Summary ───────────────────────────────────────────
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run complete — no emails sent.'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Reminder run complete — '
                    f'doc: {doc_sent}, '
                    f'profile: {profile_sent}, '
                    f'employer activation: {employer_sent}'
                )
            )
