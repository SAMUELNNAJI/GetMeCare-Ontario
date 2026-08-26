"""
Management command: fincra_setup_cad

Create (or refresh) the Fincra CAD (Interac e-Transfer) collection account.

Usage:
    python manage.py fincra_setup_cad            # create/refresh account
    python manage.py fincra_setup_cad --refresh  # force refresh from Fincra
    python manage.py fincra_setup_cad --show     # print current account + alias
"""

import logging

from django.core.management.base import BaseCommand

from Account.models import FincraCadAccount
from EmployerApp.fincra_cad import sync_cad_account

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create or refresh the Fincra CAD (Interac e-Transfer) collection account'

    def add_arguments(self, parser):
        parser.add_argument(
            '--refresh', action='store_true',
            help='Force a refresh of the account details from Fincra',
        )
        parser.add_argument(
            '--show', action='store_true',
            help='Print the current stored account information and exit',
        )

    def handle(self, *args, **options):
        if options['show']:
            for acc in FincraCadAccount.objects.order_by('-created_at'):
                self.stdout.write(
                    f'[{acc.currency}] id={acc.account_id} status={acc.status} '
                    f'interac={acc.interac_email} created={acc.created_at:%Y-%m-%d %H:%M}'
                )
            return

        try:
            account, changed = sync_cad_account(force_create=options['refresh'])
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f'CAD account setup failed: {exc}'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'CAD account {account.account_id} — status: {account.get_status_display()}'
        ))
        if account.interac_email:
            self.stdout.write(self.style.SUCCESS(
                f'Interac e-Transfer alias: {account.interac_email}'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'No Interac alias yet — Fincra approves the account asynchronously. '
                'Re-run this command later to pick up the alias.'
            ))
        if changed:
            self.stdout.write(self.style.WARNING('Account details changed in DB.'))
        else:
            self.stdout.write('No changes to account details.')