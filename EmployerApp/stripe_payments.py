"""
Stripe payment gateway integration for GetMeCare.

Handles:
  - Creating hosted Stripe Checkout sessions (card payments, CAD)
  - Verifying payment status after the customer returns from checkout
  - Validating incoming webhook signatures (Stripe-Signature header)

Docs: https://docs.stripe.com/payments/checkout
"""

import logging
import uuid

import stripe
from django.conf import settings

logger = logging.getLogger(__name__)


# ── Internal helpers ─────────────────────────────────────────────────────────

def _configure() -> None:
    """Point the stripe SDK at the configured secret key."""
    api_key = settings.STRIPE_SECRET_KEY or ''
    if not api_key:
        raise ValueError('STRIPE_SECRET_KEY is not configured.')
    stripe.api_key = api_key


def _to_minor_units(amount) -> int:
    """Convert a CAD amount (e.g. 39.99) to Stripe minor units (3999 cents)."""
    return int(round(float(amount) * 100))


# ── Public API ────────────────────────────────────────────────────────────────

def generate_reference(prefix: str = 'GMCR') -> str:
    """
    Generate a unique merchant reference for a Stripe checkout.

    Format: GMCR-<prefix>-<uuid4[:12]>
    Example: GMCR-ACT-a1b2c3d4e5f6
    """
    unique = uuid.uuid4().hex[:12]
    return f'GMCR-{prefix}-{unique}'


def create_checkout_session(
    *,
    amount,
    customer_name: str,
    customer_email: str,
    reference: str,
    success_url: str,
    cancel_url: str,
    metadata: dict | None = None,
    description: str = '',
):
    """
    Create a hosted Stripe Checkout session (redirect flow).

    Parameters
    ----------
    amount : float
        The charge amount in the configured currency unit (e.g. 39.99 CAD).
    customer_name : str
        Full name of the payer.
    customer_email : str
        Payer's email address.
    reference : str
        Unique merchant reference (use generate_reference()).
    success_url : str
        Where Stripe sends the customer after a successful payment.
        May contain the ``{CHECKOUT_SESSION_ID}`` placeholder.
    cancel_url : str
        Where Stripe sends the customer if they cancel the checkout.
    metadata : dict, optional
        Arbitrary key/value pairs stored with the checkout session
        (e.g. payment_type, user_id, shift_id).
    description : str, optional
        Line-item description shown on the checkout page.

    Returns
    -------
    stripe.checkout.Session
        The created session; ``session.url`` is where the customer must be
        redirected to complete payment.
    """
    _configure()

    currency         = (settings.STRIPE_CURRENCY or 'cad').lower()
    unit_amount      = _to_minor_units(amount)

    session_metadata = {'reference': reference}
    if metadata:
        session_metadata.update({str(k): str(v) for k, v in metadata.items()})

    logger.info(
        'Creating Stripe checkout session: ref=%s amount=%s %s',
        reference, amount, currency.upper(),
    )

    session = stripe.checkout.Session.create(
        mode='payment',
        customer_email=customer_email,
        client_reference_id=reference,
        line_items=[{
            'quantity': 1,
            'price_data': {
                'currency':     currency,
                'unit_amount':  unit_amount,
                'product_data': {
                    'name': description or 'GetMeCare payment',
                },
            },
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=session_metadata,
    )

    logger.info('Stripe checkout session created: id=%s', session.id)
    return session


def verify_payment(session_id: str) -> dict:
    """
    Verify the status of a checkout session (server-side).

    Parameters
    ----------
    session_id : str
        The ``cs_...`` id from the ``session_id`` query parameter that Stripe
        appends to the success_url.

    Returns
    -------
    dict
        - status    : "success" | "pending" | "failed"
        - reference : merchant reference (client_reference_id)
        - session_id: Stripe checkout session id
        - metadata  : session metadata dict
        - amount    : amount charged, in currency units
        - currency  : uppercase currency code
    """
    _configure()
    logger.info('Verifying Stripe payment: session_id=%s', session_id)

    session = stripe.checkout.Session.retrieve(
        session_id, expand=['payment_intent'],
    )

    meta       = session.get('metadata') or {}
    pay_status = session.get('payment_status')   # paid | unpaid | no_payment_required
    ses_status = session.get('status')           # complete | open | expired

    if ses_status == 'complete' and pay_status in ('paid', 'no_payment_required'):
        status = 'success'
    elif ses_status == 'open':
        status = 'pending'
    else:
        status = 'failed'

    return {
        'status':     status,
        'reference':  session.get('client_reference_id') or meta.get('reference', ''),
        'session_id': session.get('id', ''),
        'metadata':   meta,
        'amount':     (session.get('amount_total') or 0) / 100,
        'currency':   (session.get('currency') or '').upper(),
    }


def construct_webhook_event(payload: bytes, signature_header: str):
    """
    Validate a webhook and build the event it represents.

    Uses Stripe's ``Stripe-Signature`` HMAC scheme with the configured
    webhook signing secret (STRIPE_WEBHOOK_SECRET).

    Parameters
    ----------
    payload : bytes
        Raw request body (request.body in Django).
    signature_header : str
        Value of the ``Stripe-Signature`` HTTP header.

    Returns
    -------
    stripe.Event

    Raises
    ------
    ValueError, stripe.error.SignatureVerificationError
        If the signature is missing, the secret is unset, or the signature
        does not match the payload.
    """
    _configure()

    secret = settings.STRIPE_WEBHOOK_SECRET or ''
    if not secret:
        raise ValueError('STRIPE_WEBHOOK_SECRET is not configured.')
    if not signature_header:
        raise ValueError('Missing Stripe-Signature header.')

    return stripe.Webhook.construct_event(payload, signature_header, secret)

