"""
Management command: send_whatsapp_reminders

Sends reminder emails to users (caregivers and employers) who registered without a WhatsApp number.
The email contains a direct link to /account/add-whatsapp/ where old users can save their number.

Usage:
    python manage.py send_whatsapp_reminders
    python manage.py send_whatsapp_reminders --dry-run
"""

import re
import logging
from django.core.management.base import BaseCommand
from Account.models import CustomUser
from GETMECARE.email_utils import send_whatsapp_reminder_email

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send WhatsApp setup reminder emails to users without a valid WhatsApp number'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview users who would receive the reminder without sending emails',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        users = CustomUser.objects.filter(is_active=True)

        targets = []
        for user in users:
            phone = (user.phone or '').strip()
            digits = re.sub(r'\D', '', phone)
            if len(digits) < 7:
                targets.append(user)

        self.stdout.write(f"Found {len(targets)} active user(s) missing a valid WhatsApp number.")

        sent_count = 0
        error_count = 0

        for user in targets:
            role = 'Caregiver' if getattr(user, 'is_caregiver', False) else ('Employer' if getattr(user, 'is_employer', False) else 'User')
            if dry_run:
                self.stdout.write(f"[DRY-RUN] Would email: {user.email} ({user.get_full_name() or 'N/A'}, Role: {role})")
            else:
                try:
                    success = send_whatsapp_reminder_email(user)
                    if success:
                        sent_count += 1
                        self.stdout.write(self.style.SUCCESS(f"Sent reminder to {user.email}"))
                    else:
                        error_count += 1
                        self.stdout.write(self.style.WARNING(f"Failed to send to {user.email}"))
                except Exception as exc:
                    error_count += 1
                    logger.exception(f"Error emailing {user.email}: {exc}")
                    self.stdout.write(self.style.ERROR(f"Error emailing {user.email}: {exc}"))

        if dry_run:
            self.stdout.write(self.style.SUCCESS(f"[DRY-RUN Complete] {len(targets)} user(s) identified."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Finished. Sent: {sent_count}, Failed: {error_count}"))
