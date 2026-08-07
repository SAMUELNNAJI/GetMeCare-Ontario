"""
Fincra Payment Gateway integration for GetMeCare.

Handles:
  - Initiating hosted checkout sessions
  - Verifying payment status after redirect
  - Validating incoming webhook signatures (HMAC-SHA512)

Docs: https://docs.fincra.com/reference/initiate-checkout
"""

import hmac
import hashlib
import logging
import uuid

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Internal helpers ─────────────────────────────────────────────────────────

def _api_url(path: str) -> str:
    """Build a full Fincra API URL from the configured base URL."""
    base = (settings.FINCRA_BASE_URL or 'https://sandboxapi.fincra.com').rstrip('/')
    return f"{base}/{path.lstrip('/')}"


def _resolve_checkout_amount(amount_usd: float) -> tuple[float, str]:
    """Convert a USD amount to the best checkout currency.

    USD only supports *card* on Fincra.  NGN supports card, bank_transfer,
    and payAttitude — giving the customer far more payment options.

    When FINCRA_CURRENCY is NGN (default), the USD amount is multiplied
    by ``FINCRA_USD_TO_NGN_RATE`` to produce the NGN charge.

    Returns
    -------
    tuple[float, str]
        (converted_amount, currency_code)
    """
    currency = (settings.FINCRA_CURRENCY or 'NGN').upper()

    if currency == 'USD':
        # USD — no conversion, but only card is available
        return round(amount_usd, 2), 'USD'

    # NGN (or any other currency) — apply the conversion rate
    rate = float(getattr(settings, 'FINCRA_USD_TO_NGN_RATE', 1580) or 1580)
    converted = round(amount_usd * rate, 2)
    return converted, currency


def _headers(include_business_id: bool = False) -> dict:
    """Common request headers for Fincra API calls."""
    headers = {
        'api-key':     settings.FINCRA_SECRET_KEY or '',
        'x-pub-key':   settings.FINCRA_PUBLIC_KEY or '',
        'Content-Type': 'application/json',
    }
    if include_business_id and settings.FINCRA_BUSINESS_ID:
        headers['x-business-id'] = settings.FINCRA_BUSINESS_ID
    return headers


# ── Public API ────────────────────────────────────────────────────────────────

def generate_reference(prefix: str = 'GMCR') -> str:
    """
    Generate a unique merchant reference for a Fincra checkout.

    Format: GMCR-<prefix>-<uuid4[:12]>
    Example: GMCR-ACT-a1b2c3d4e5f6
    """
    unique = uuid.uuid4().hex[:12]
    return f'GMCR-{prefix}-{unique}'


def initiate_checkout(
    *,
    amount: float,
    customer_name: str,
    customer_email: str,
    reference: str,
    redirect_url: str,
    metadata: dict | None = None,
    payment_methods: list[str] | None = None,
    description: str = '',
) -> dict:
    """
    Create a hosted Fincra checkout session.

    Parameters
    ----------
    amount : float
        The charge amount in the currency unit (e.g. 49.99 USD).
    customer_name : str
        Full name in "Firstname Lastname" format.
    customer_email : str
        Customer's email address.
    reference : str
        Unique merchant reference (use generate_reference()).
    redirect_url : str
        Where Fincra sends the customer after payment.
    metadata : dict, optional
        Arbitrary key/value pairs stored with the transaction.
    payment_methods : list[str], optional
        Methods shown on the checkout page.
        Defaults to ["card", "bank_transfer"].
    description : str, optional
        Human-readable description for the transaction.

    Returns
    -------
    dict
        Full Fincra response body.  Access the redirect link via:
        response["data"]["link"]

    Raises
    ------
    requests.HTTPError
        On non-2xx HTTP responses from Fincra.
    """
    # Convert USD price to the checkout currency (NGN by default for full
    # payment-method support: card, bank_transfer, payAttitude).
    charge_amount, currency = _resolve_checkout_amount(amount)

    payload = {
        'currency':    currency,
        'amount':      charge_amount,
        'customer': {
            'name':  customer_name,
            'email': customer_email,
        },
        'reference':   reference,
        'redirectUrl': redirect_url,
        'feeBearer':   'business',
        'paymentMethods': payment_methods or ['card'],
    }
    if metadata:
        payload['metadata'] = metadata
    if description:
        payload['description'] = description

    logger.info(
        "Initiating Fincra checkout: ref=%s amount=%s %s (original $%s USD)",
        reference, charge_amount, currency, amount,
    )

    resp = requests.post(
        _api_url('/checkout/payments'),
        json=payload,
        headers=_headers(),
        timeout=30,
    )

    if resp.status_code >= 400:
        logger.error(
            "Fincra checkout failed [%s]: %s", resp.status_code, resp.text
        )
        raise ValueError(
            f'Fincra returned HTTP {resp.status_code}: {resp.text[:300]}'
        )

    data = resp.json()

    if not data.get('status'):
        msg = data.get('message', 'Fincra rejected the checkout request.')
        logger.error("Fincra returned status=false: %s", data)
        raise ValueError(msg)

    logger.info(
        "Fincra checkout created: ref=%s link=%s",
        reference, data.get('data', {}).get('link'),
    )
    return data


def verify_payment(reference: str) -> dict:
    """
    Verify the status of a checkout payment by merchant reference.

    Parameters
    ----------
    reference : str
        The merchant reference passed when initiating the checkout.

    Returns
    -------
    dict
        Fincra response body.  Key fields:
        - data.status   : "success" | "failed" | "pending"
        - data.amount   : amount charged
        - data.reference: Fincra's own transaction reference
    """
    logger.info("Verifying Fincra payment: merchant_ref=%s", reference)

    resp = requests.get(
        _api_url(f'/checkout/payments/merchant-reference/{reference}'),
        headers=_headers(include_business_id=True),
        timeout=30,
    )

    if resp.status_code >= 400:
        logger.error(
            "Fincra verify failed [%s]: %s", resp.status_code, resp.text
        )

    resp.raise_for_status()
    return resp.json()


def validate_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """
    Verify that a webhook was genuinely sent by Fincra.

    Uses HMAC-SHA512 with the configured webhook encryption key.

    Parameters
    ----------
    payload_bytes : bytes
        Raw request body (request.body in Django).
    signature_header : str
        Value of the ``signature`` HTTP header from Fincra.

    Returns
    -------
    bool
        True if the computed HMAC matches the provided signature.
    """
    if not signature_header:
        logger.warning("Fincra webhook received with empty signature header.")
        return False

    key = (settings.FINCRA_WEBHOOK_KEY or '').encode('utf-8')
    computed = hmac.new(key, payload_bytes, hashlib.sha512).hexdigest()

    is_valid = hmac.compare_digest(computed, signature_header)
    if not is_valid:
        logger.warning(
            "Fincra webhook signature mismatch.  Expected=%s Got=%s",
            signature_header[:12] + '…',
            computed[:12] + '…',
        )
    return is_valid
