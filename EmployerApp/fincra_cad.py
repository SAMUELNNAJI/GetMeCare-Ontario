"""
Fincra CAD (Interac e-Transfer) integration for GetMeCare.

Collects Canadian Dollars from employers via Interac e-Transfer.  Fincra
issues the merchant a unique Interac collection alias (e.g. merchant@fincra.ca)
registered for Autodeposit.  Employers e-Transfer money to that alias and the
funds are credited to the merchant's Fincra CAD wallet; Fincra then notifies us
with a ``collection.successful`` webhook.

API endpoints used
------------------
- Create CAD Collection Account : POST /profile/virtual-accounts/requests
- Get Account by ID            : GET  /profile/virtual-accounts/{id}
- Get Accounts by Currency     : GET  /profile/virtual-accounts/?currency=CAD

Deposits (payin/collection) webhook events
------------------------------------------
- collection.successful — funds received in our virtual account
- collection.failed     — a payin failed / was declined
"""

import json
import logging
import re
import uuid
from decimal import Decimal, InvalidOperation

import requests
from django.conf import settings
from django.utils import timezone

from Account.models import (
    EmployerProfile,
    EmployerPayment,
    FincraCadAccount,
    FincraCollection,
    InteracPaymentRequest,
)
from GETMECARE.email_utils import (
    send_activation_confirmation_email,
    send_shift_payment_caregiver_email,
)
from EmployerApp.fincra_payments import _api_url, _headers

logger = logging.getLogger(__name__)

# Matches our generated reference codes, e.g. GMCR-ITR-A1B2C3D4
REFERENCE_PATTERN = re.compile(r'GMCR-ITR-[A-Z0-9-]+')


# ──────────────────────────────────────────────────────────────
# Small helpers
# ──────────────────────────────────────────────────────────────

def _setting(name, default=''):
    return getattr(settings, name, None) or default


def generate_interac_reference() -> str:
    return f'GMCR-ITR-{uuid.uuid4().hex[:8].upper()}'


def get_active_cad_account():
    """Return the current approved CAD collection account, or None."""
    return FincraCadAccount.objects.filter(
        currency='CAD', status=FincraCadAccount.STATUS_APPROVED,
    ).first()


# ──────────────────────────────────────────────────────────────
# Retrieval / creation of the CAD collection account
# ──────────────────────────────────────────────────────────────

def _account_id_from_response(data: dict) -> str:
    """Extract the virtual-account id from a create/fetch response defensively."""
    d = data.get('data', data)
    if isinstance(d, dict):
        for key in ('_id', 'id', 'virtualAccountId'):
            if d.get(key):
                return str(d[key])
        nested = d.get('virtualAccount') or {}
        if isinstance(nested, dict):
            for key in ('_id', 'id'):
                if nested.get(key):
                    return str(nested[key])
    return ''


def fetch_cad_account(account_id: str) -> dict:
    """GET the CAD collection account by id (includes assigned Interac email)."""
    resp = requests.get(
        _api_url(f'/profile/virtual-accounts/{account_id}'),
        headers=_headers(),
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def list_cad_accounts(currency: str = 'CAD') -> list:
    """List collection accounts for a currency (CAD returns Interac emails)."""
    resp = requests.get(
        _api_url('/profile/virtual-accounts/'),
        headers=_headers(),
        params={'currency': currency},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    data = body.get('data', {})
    if isinstance(data, list):
        return data
    return data.get('results', []) if isinstance(data, dict) else []


def create_cad_collection_account() -> dict:
    """Request a new CAD collection account (KYC taken from settings).

    Returns the parsed Fincra response.  The account is approved asynchronously
    by Fincra — call :func:`sync_cad_account` later to pick up the alias.
    """
    _load_json = lambda raw: json.loads(raw) if raw.strip() else None

    kyc = {
        'firstName': _setting('FINCRA_CAD_KYC_FIRST_NAME'),
        'lastName': _setting('FINCRA_CAD_KYC_LAST_NAME'),
        'otherName': _setting('FINCRA_CAD_KYC_OTHER_NAME'),
        'email': _setting('FINCRA_CAD_KYC_EMAIL'),
        'phone': _setting('FINCRA_CAD_KYC_PHONE'),
        'nationality': _setting('FINCRA_CAD_KYC_NATIONALITY'),
        'birthDate': _setting('FINCRA_CAD_KYC_BIRTH_DATE'),
        'occupation': _setting('FINCRA_CAD_KYC_OCCUPATION'),
        'accountDestination': _setting('FINCRA_CAD_KYC_ACCOUNT_DESTINATION', 'wallet'),
        'taxCountry': _setting('FINCRA_CAD_KYC_TAX_COUNTRY'),
        'taxNumber': _setting('FINCRA_CAD_KYC_TAX_NUMBER'),
        'monthlyTransactionVolume': _setting('FINCRA_CAD_KYC_MONTHLY_TX_VOLUME'),
        'monthlyTransactionCount': _setting('FINCRA_CAD_KYC_MONTHLY_TX_COUNT'),
        'sourceOfIncome': _setting('FINCRA_CAD_KYC_SOURCE_OF_INCOME'),
        'employmentStatus': _setting('FINCRA_CAD_KYC_EMPLOYMENT_STATUS'),
    }

    # JSON-structured fields (parse/validate each defensively)
    addr = _load_json(_setting('FINCRA_CAD_KYC_ADDRESS'))
    if addr:
        kyc['address'] = addr
    income = _load_json(_setting('FINCRA_CAD_KYC_INCOME_BAND'))
    if income:
        kyc['incomeBand'] = income
    doc = _load_json(_setting('FINCRA_CAD_KYC_DOCUMENT'))
    if doc:
        kyc['document'] = doc
    # Allow an override to merge a complete KYC block wholesale
    override = _load_json(_setting('FINCRA_CAD_KYC_JSON'))
    if override:
        kyc.update(override)

    means_of_id = _load_json(_setting('FINCRA_CAD_MEANS_OF_ID', '[]'))
    if not isinstance(means_of_id, list):
        means_of_id = []

    payload = {
        'accountType': _setting('FINCRA_CAD_ACCOUNT_TYPE', 'corporate'),
        'currency': 'CAD',
        'KYCInformation': kyc,
        'meansOfId': means_of_id,
        'utilityBill': _setting('FINCRA_CAD_UTILITY_BILL'),
        'purpose': _setting(
            'FINCRA_CAD_PURPOSE',
            'Collect account activation and shift-booking payments from '
            'Canadian employers via Interac e-Transfer.',
        ),
        'emerchantReference': 'GETMECARE-CAD',
        'isTermsAccepted': True,
    }
    if _setting('FINCRA_CAD_BANK_STATEMENT'):
        payload['bankStatement'] = _setting('FINCRA_CAD_BANK_STATEMENT')

    logger.info('Creating Fincra CAD collection account (accountType=%s)',
                payload['accountType'])

    resp = requests.post(
        _api_url('/profile/virtual-accounts/requests'),
        json=payload,
        headers=_headers(),
        timeout=30,
    )

    if resp.status_code >= 400:
        logger.error('Fincra create CAD account failed [%s]: %s',
                     resp.status_code, resp.text)
        raise ValueError(f'Fincra create CAD account HTTP {resp.status_code}: {resp.text[:500]}')

    body = resp.json()
    if body.get('status') is False:
        msg = body.get('message', 'Fincra rejected the CAD account request.')
        logger.error('Fincra create CAD account rejected: %s', body)
        raise ValueError(msg)

    return body


def sync_cad_account(force_create: bool = False) -> tuple:
    """Create (if needed) or refresh the CAD account; return (account, changed).

    - If an account id is configured in settings or stored in the model, fetch it
      and update status / interac alias.
    - Otherwise create a new account request.
    """
    # 1) Prefer the row already in the DB
    account = FincraCadAccount.objects.order_by('-created_at').first()

    # 2) If settings point to an account id we don't have stored yet, seed it
    configured_id = _setting('FINCRA_CAD_ACCOUNT_ID')
    if not account and configured_id:
        account = FincraCadAccount.objects.create(account_id=configured_id)

    # 3) No account at all → request a new one
    if not account:
        body = create_cad_collection_account()
        account_id = _account_id_from_response(body)
        if not account_id:
            raise ValueError('Fincra did not return an account id: %s' % str(body)[:300])
        account = FincraCadAccount.objects.create(account_id=account_id)
        logger.info('Created Fincra CAD account request: %s', account_id)

    # 4) Fetch latest details from Fincra
    changed = False
    try:
        body = fetch_cad_account(account.account_id)
    except Exception as exc:
        logger.warning('Fincra sync (fetch) failed for %s: %s', account.account_id, exc)
        return account, changed

    account.raw_data = body
    info = (body.get('data') or {})
    account_info = info.get('accountInformation') or {}

    # Approved → grab the Interac alias
    interac_email = (
        (account_info.get('otherInfo') or {}).get('interacEmail')
        or _setting('FINCRA_CAD_ACCOUNT_EMAIL')
    )
    if interac_email and interac_email != account.interac_email:
        account.interac_email = interac_email
        changed = True

    # Status heuristics
    raw_status = str(info.get('status') or account_info.get('status') or '').lower()
    if interac_email:
        new_status = FincraCadAccount.STATUS_APPROVED
    elif raw_status in ('pending', 'processing', 'in_review'):
        new_status = FincraCadAccount.STATUS_PENDING
    elif raw_status in ('failed', 'rejected', 'declined'):
        new_status = FincraCadAccount.STATUS_FAILED
    else:
        new_status = account.status or FincraCadAccount.STATUS_PENDING

    if new_status != account.status:
        account.status = new_status
        changed = True

    account.save()
    return account, changed


# ──────────────────────────────────────────────────────────────
# Per-employer Interac payment requests (for attribution)
# ──────────────────────────────────────────────────────────────

def get_or_create_interac_request(user, purpose, amount, shift=None) -> InteracPaymentRequest:
    """Return the employer's pending Interac request, (re)creating one if needed."""
    existing = (
        InteracPaymentRequest.objects
        .filter(user=user, purpose=purpose, status=InteracPaymentRequest.STATUS_PENDING)
        .order_by('-created_at')
        .first()
    )
    if existing and (not shift or existing.shift_id == shift.pk):
        return existing
    return InteracPaymentRequest.objects.create(
        user=user,
        purpose=purpose,
        reference=generate_interac_reference(),
        amount=amount,
        shift=shift,
    )


def get_interac_payment_info(user, purpose, amount, shift=None):
    """Return template payload for the Interac option, or None if not configured."""
    account = get_active_cad_account()
    if not account or not account.interac_email:
        return None
    req = get_or_create_interac_request(user, purpose, amount, shift)
    return {
        'alias': account.interac_email,
        'reference': req.reference,
        'amount': amount,
    }


# ──────────────────────────────────────────────────────────────
# Webhook processing  (collection.successful / collection.failed)
# ──────────────────────────────────────────────────────────────

def handle_collection_webhook(data: dict) -> bool:
    """Process a ``collection.successful`` payload.

    Returns True if the deposit was matched to an employer and settled,
    False if it could not be matched automatically (recorded for reconciliation).
    """
    session_id = data.get('sessionId') or data.get('reference') or ''
    if not session_id:
        logger.warning('Fincra collection webhook missing sessionId/reference')
        return False

    # Idempotency — each deposit is processed exactly once
    if FincraCollection.objects.filter(session_id=session_id).exists():
        logger.info('Fincra collection %s already processed — skipping', session_id)
        return True

    try:
        amount_received = Decimal(str(data.get('amountReceived') or data.get('destinationAmount') or ''))
    except (InvalidOperation, ValueError):
        amount_received = None
    try:
        fee = Decimal(str(data.get('fee') or 0))
    except (InvalidOperation, ValueError):
        fee = None

    record = FincraCollection.objects.create(
        session_id      = session_id,
        virtual_account = str(data.get('virtualAccount') or ''),
        amount_received = amount_received,
        fee             = fee,
        source_currency = str(data.get('sourceCurrency') or data.get('destinationCurrency') or ''),
        customer_name   = str(data.get('customerName') or ''),
        description     = str(data.get('description') or ''),
        reference       = str(data.get('reference') or ''),
        status          = str(data.get('status') or 'successful'),
    )

    matched = _try_match_by_reference(data, record)
    if not matched:
        matched = _try_match_by_amount(data, record)

    if matched:
        record.processed = True
        record.note = record.note or 'Matched automatically.'
        record.save(update_fields=['processed', 'note'])
        logger.info('Fincra collection %s matched (note=%s)', session_id, record.note)
        return True

    logger.warning(
        'Fincra collection %s unmatched — %s sent %.2f %s. Reconcile manually.',
        session_id, record.customer_name,
        amount_received or Decimal('0'), record.source_currency,
    )
    return False


def log_failed_collection(data: dict) -> None:
    """Record a ``collection.failed`` event (informational only)."""
    try:
        FincraCollection.objects.get_or_create(
            session_id = data.get('sessionId') or data.get('reference') or f'failed-{timezone.now().timestamp()}',
            defaults={
                'virtual_account': str(data.get('virtualAccount') or ''),
                'amount_received': None,
                'customer_name':   str(data.get('customerName') or ''),
                'description':     str(data.get('description') or ''),
                'status':          str(data.get('status') or 'failed'),
                'processed':       False,
                'note':            f'reason: {data.get("reason", "")}',
            },
        )
    except Exception:
        logger.exception('Failed to record Fincra collection.failed event')


def _try_match_by_reference(data: dict, record: FincraCollection) -> bool:
    """Match the e-Transfer to an employer via the reference code in the message."""
    haystack = ' '.join([
        str(data.get('description') or ''),
        str(data.get('customerName') or ''),
        str(data.get('sessionId') or ''),
        str(data.get('reference') or ''),
    ])
    refs = set(REFERENCE_PATTERN.findall(haystack))
    for ref in refs:
        req = InteracPaymentRequest.objects.filter(
            reference=ref, status=InteracPaymentRequest.STATUS_PENDING,
        ).first()
        if req:
            _settle_request(req, data, record)
            return True
    return False


def _try_match_by_amount(data: dict, record: FincraCollection) -> bool:
    """Fallback: match a fixed activation fee to the oldest pending activation."""
    if record.amount_received is None:
        return False
    req = (
        InteracPaymentRequest.objects
        .filter(
            purpose=InteracPaymentRequest.PURPOSE_ACTIVATION,
            status=InteracPaymentRequest.STATUS_PENDING,
            amount=record.amount_received,
        )
        .order_by('created_at')
        .first()
    )
    if req:
        _settle_request(req, data, record)
        return True
    return False


def _settle_request(req: InteracPaymentRequest, data: dict, record: FincraCollection) -> None:
    """Activate the employer / confirm the booking and create the payment record."""
    user = req.user

    if req.purpose == InteracPaymentRequest.PURPOSE_ACTIVATION:
        profile, _ = EmployerProfile.objects.get_or_create(user=user)
        if not profile.is_active:
            profile.is_active          = True
            profile.activation_paid_at = timezone.now()
            profile.payment_reference  = req.reference
            profile.save()

        payment, _created = EmployerPayment.objects.get_or_create(
            employer          = user,
            payment_type      = EmployerPayment.TYPE_ACTIVATION,
            payment_reference = req.reference,
            defaults={
                'amount':      req.amount,
                'status':      EmployerPayment.STATUS_COMPLETED,
                'description': f'One-time account activation fee (Interac e-Transfer, session {record.session_id})',
            },
        )
        try:
            send_activation_confirmation_email(user, payment)
        except Exception:
            logger.exception('Interac activation email failed for user %s', user.pk)

    else:  # booking
        shift = req.shift
        if shift:
            try:
                proposal = getattr(shift, 'booking_proposal', None)
                if proposal and proposal.status != 'booked':
                    proposal.status = 'booked'
                    proposal.save(update_fields=['status', 'updated_at'])
            except Exception:
                pass

        payment, _created = EmployerPayment.objects.get_or_create(
            employer          = user,
            payment_type      = EmployerPayment.TYPE_BOOKING,
            payment_reference = req.reference,
            defaults={
                'amount': req.amount,
                'status': EmployerPayment.STATUS_COMPLETED,
                'shift':  shift,
                'description': (
                    f'Shift #{shift.pk} — {shift.caregiver.get_full_name() if shift else "—"}, '
                    f'paid via Interac e-Transfer (session {record.session_id})'
                ),
            },
        )
        if shift:
            try:
                send_shift_payment_caregiver_email(shift.caregiver, shift)
            except Exception:
                logger.exception('Interac booking caregiver email failed for shift %s', shift.pk)

    req.status = InteracPaymentRequest.STATUS_PAID
    req.paid_at = timezone.now()
    req.save(update_fields=['status', 'paid_at'])
    record.note = f'Matched {req.reference} ({req.get_purpose_display()}) for {user.get_full_name()}'