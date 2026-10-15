"""
Management command: send_first_job_reminders

Runs every 24 hours via the APScheduler started in Account/apps.py.
Targets employers who have NEVER created a JobPosting (new signups AND
old employers who signed up but never posted).

Once an employer creates their first JobPosting (any status), they are
automatically excluded — the daily reminder emails stop on their own.

Usage:
    python manage.py send_first_job_reminders           # live run
    python manage.py send_first_job_reminders --dry-run # print only, no emails
"""

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from Account.models import CustomUser, EmployerProfile, JobPosting
from GETMECARE.email_utils import send_first_job_post_reminder_email

logger = logging.getLogger(__name__)

REMINDER_INTERVAL = timedelta(hours=24)


def _is_due(last_sent, cutoff) -> bool:
    """True when a reminder has never been sent OR was sent before the cutoff."""
    return last_sent is None or last_sent <= cutoff


class Command(BaseCommand):
    help = 'Send every-24-hours reminder emails to employers with zero job postings'

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

        sent    = 0
        skipped_posted = 0

        employers = (
            CustomUser.objects
            .filter(role=CustomUser.EMPLOYER, is_staff=False, is_superuser=False)
            .exclude(email='')
        )

        for employer in employers:
            # STOP condition: any JobPosting row (open/filled/closed) → no more emails
            if JobPosting.objects.filter(employer=employer).exists():
                skipped_posted += 1
                continue

            ep, _ = EmployerProfile.objects.get_or_create(user=employer)

            if not _is_due(ep.last_first_job_reminder_sent, cutoff):
                continue

            days_waiting = None
            try:
                days_waiting = max((now.date() - employer.date_joined.date()).days, 0)
            except Exception:
                days_waiting = None

            if dry_run:
                self.stdout.write(
                    f'[DRY-RUN] First-job reminder -> {employer.email}'
                )
                continue

            ok = send_first_job_post_reminder_email(employer, days_waiting=days_waiting)
            if ok:
                ep.last_first_job_reminder_sent = now
                ep.save(update_fields=['last_first_job_reminder_sent'])
                sent += 1
                logger.info('First-job reminder sent → %s', employer.email)
            else:
                logger.warning('First-job reminder FAILED → %s', employer.email)

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run complete — no emails sent.'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'First-job reminder run complete — sent: {sent}, '
                    f'(already posted, skipped: {skipped_posted})'
                )
            )
