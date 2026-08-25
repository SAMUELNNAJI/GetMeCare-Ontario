"""
Management command: send_profile_photo_reminders

Runs every 24 hours via the APScheduler started in Account/apps.py.
Targets caregivers who have NOT uploaded a profile photo yet.

Once a caregiver uploads a photo (CaregiverProfile.profile_image set),
the profile is automatically excluded — no more photo reminder emails.
This works for EVERY caregiver status (pending, inactive, active, rejected):
the only requirement is that a photo is missing.

Usage:
    python manage.py send_profile_photo_reminders           # live run
    python manage.py send_profile_photo_reminders --dry-run # print only, no emails
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from Account.models import CaregiverProfile, CustomUser
from GETMECARE.email_utils import send_profile_photo_reminder_email

logger = logging.getLogger(__name__)

REMINDER_INTERVAL = timedelta(hours=24)


def _is_due(last_sent, cutoff) -> bool:
    """True when a reminder has never been sent OR was sent before the cutoff."""
    return last_sent is None or last_sent <= cutoff


class Command(BaseCommand):
    help = 'Send every-24-hours reminder emails to caregivers without a profile photo'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print who would be emailed without sending anything',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        now     = timezone.now()
        cutoff  = now - REMINDER_INTERVAL

        sent = 0
        skipped_photo_uploaded = 0

        # Only caregivers without a profile photo. Note: Django's FileField
        # stores "no value" as an empty string '' (new rows) or NULL (old rows),
        # so we must match BOTH. Once profile_image holds a real file path this
        # queryset excludes them automatically → reminders stop.
        profiles = (
            CaregiverProfile.objects
            .filter(
                user__role=CustomUser.CAREGIVER,
            )
            .filter(Q(profile_image__isnull=True) | Q(profile_image=''))
            .select_related('user')
            .exclude(user__email='')
            .exclude(user__is_staff=True)
            .exclude(user__is_superuser=True)
        )

        for profile in profiles:
            user = profile.user

            # Safety guard: skip if a photo appeared between query and loop
            if getattr(profile, 'profile_image', None):
                skipped_photo_uploaded += 1
                continue

            if _is_due(profile.last_profile_photo_reminder_sent, cutoff):
                if dry_run:
                    self.stdout.write(
                        f'[DRY-RUN] Profile photo reminder -> {user.email}'
                    )
                else:
                    ok = send_profile_photo_reminder_email(user)
                    if ok:
                        profile.last_profile_photo_reminder_sent = now
                        profile.save(update_fields=['last_profile_photo_reminder_sent'])
                        sent += 1
                        logger.info('Profile photo reminder sent → %s', user.email)
                    else:
                        logger.warning('Profile photo reminder FAILED → %s', user.email)

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run complete — no emails sent.'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Profile-photo reminder run complete — sent: {sent}, '
                    f'(photo already present: {skipped_photo_uploaded})'
                )
            )