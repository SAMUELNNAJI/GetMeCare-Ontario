"""
Management command: fincra_check_auth

Diagnose Fincra API authentication problems.

Usage:
    python manage.py fincra_check_auth            # test sandbox credentials
    python manage.py fincra_check_auth --live     # also test against production API
"""

import requests

from django.conf import settings
from django.core.management.base import BaseCommand


def _mask(value: str) -> str:
    if not value:
        return '(NOT SET)'
    if len(value) <= 10:
        return value[:4] + '…'
    return f'{value[:8]}…{value[-4:]} (len={len(value)})'


def _probe(base_url: str, api_key: str, pub_key: str, business_id: str,
           attempts: int = 3) -> dict:
    """Make a lightweight authenticated call and classify the result."""
    headers = {
        'api-key': api_key or '',
        'x-pub-key': pub_key or '',
        'Content-Type': 'application/json',
    }
    if business_id:
        headers['x-business-id'] = business_id

    resp = None
    last_exc = None
    for _ in range(attempts):
        try:
            resp = requests.get(
                f"{base_url.rstrip('/')}/profile/virtual-accounts/",
                headers=headers,
                timeout=20,
            )
            break
        except Exception as exc:
            last_exc = exc

    if resp is None:
        return {'ok': False,
                'reason': f'Network error after {attempts} attempts: {last_exc}'}

    body = ''
    try:
        body = resp.text[:300]
    except Exception:
        pass

    if resp.status_code < 300:
        return {'ok': True, 'detail': body}

    msg = ''
    if '"message"' in body:
        # crude extract of the message field
        import json
        try:
            msg = json.loads(resp.text).get('message', '')
        except Exception:
            msg = ''

    if 'No API key found' in (msg or body):
        reason = ('Fincra did not receive an api-key header. '
                  'Check that FINCRA_SECRET_KEY is set and non-empty.')
    elif resp.status_code == 401:
        reason = ('Keys REJECTED (401 Unauthorized). The secret/public key pair '
                  'is invalid for this environment — usually caused by mixing a '
                  'LIVE key with a TEST key, or using stale/regenerated keys.')
    else:
        # Any non-401 response (200, 404, 422 …) proves the API ACCEPTED the key.
        return {'ok': True,
                'detail': f'Authenticated (HTTP {resp.status_code} — endpoint-level '
                          f'response, not an auth failure): {body[:150]}'}

    return {'ok': False, 'reason': reason, 'status': resp.status_code, 'body': body}


class Command(BaseCommand):
    help = 'Diagnose Fincra API authentication (401 errors etc.)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--live', action='store_true',
            help='Also probe the production API (https://api.fincra.com)',
        )

    def handle(self, *args, **options):
        api_key   = settings.FINCRA_SECRET_KEY or ''
        pub_key   = settings.FINCRA_PUBLIC_KEY or ''
        biz_id    = settings.FINCRA_BUSINESS_ID or ''
        base_url  = settings.FINCRA_BASE_URL or 'https://sandboxapi.fincra.com'

        self.stdout.write(self.style.MIGRATE_HEADING('── Current configuration ──'))
        self.stdout.write(f'Base URL       : {base_url}')
        self.stdout.write(f'Secret key     : {_mask(api_key)}')
        self.stdout.write(f'Public key     : {_mask(pub_key)}')
        self.stdout.write(f'Business ID    : {biz_id or "(NOT SET)"}')
        self.stdout.write(f'Currency       : {settings.FINCRA_CURRENCY}')
        self.stdout.write('')

        # Environment consistency warnings
        is_test_pub = pub_key.startswith('pk_test')
        is_sandbox  = 'sandbox' in base_url
        if is_test_pub != is_sandbox:
            self.stdout.write(self.style.ERROR(
                '⚠ MISMATCH: public key looks '
                + ('TEST (pk_test_)' if is_test_pub else 'LIVE (pk_live/other)')
                + f' but Base URL is {"SANDBOX" if is_sandbox else "PRODUCTION"}.'
            ))
            self.stdout.write('')
        if not api_key:
            self.stdout.write(self.style.ERROR('✗ FINCRA_SECRET_KEY is empty — every call will fail.'))

        self.stdout.write(self.style.MIGRATE_HEADING(f'── Probing {base_url} ──'))
        result = _probe(base_url, api_key, pub_key, biz_id)
        if result['ok']:
            self.stdout.write(self.style.SUCCESS(
                f'✓ Authentication SUCCESSFUL against {base_url}'))
        else:
            self.stdout.write(self.style.ERROR(f'✗ FAILED: {result["reason"]}'))
            if result.get('body'):
                self.stdout.write(f'  Response: {result["body"]}')

        if options['live']:
            self.stdout.write('')
            self.stdout.write(self.style.MIGRATE_HEADING(
                '── Probing https://api.fincra.com (production) ──'))
            result2 = _probe('https://api.fincra.com', api_key, pub_key, biz_id)
            if result2['ok']:
                self.stdout.write(self.style.SUCCESS(
                    '✓ Your SECRET KEY works on PRODUCTION → it is a LIVE key!'
                    ' Point FINCRA_BASE_URL=https://api.fincra.com to use it,'
                    ' or copy the TEST secret key instead.'))
            else:
                self.stdout.write(self.style.WARNING(
                    f'✗ Not valid on production either ({result2.get("reason", "")})'))

        self.stdout.write('')
        self.stdout.write(self.style.MIGRATE_HEADING('How to fix 401s'))
        self.stdout.write(
            ' 1. Open Fincra dashboard → Settings → API.\n'
            ' 2. Toggle to the SAME mode you intend to use (Test or Live).\n'
            ' 3. Copy the SECRET key AND the PUBLIC key from THAT SAME view.\n'
            ' 4. Put them in .env:\n'
            '      FINCRA_SECRET_KEY=<secret of that mode>\n'
            '      FINCRA_PUBLIC_KEY=<public key of that mode>\n'
            f'      FINCRA_BASE_URL={"https://sandboxapi.fincra.com (for test)" if is_sandbox else "https://api.fincra.com (for live)"}\n'
            ' 5. Save .env and RESTART the Django server (env loads at startup).\n'
            ' 6. Re-run: python manage.py fincra_check_auth'
        )