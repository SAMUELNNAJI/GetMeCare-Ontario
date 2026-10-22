"""Small provider-agnostic adapter for operational WhatsApp alerts."""
import logging
import re

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# A phone number is considered WhatsApp-usable when it has at least this
# many digits. Kept in ONE place so the ``wa_link`` template filter, the
# caregiver "Add WhatsApp" endpoint and the admin badge can never disagree.
MIN_WHATSAPP_DIGITS = 7


def whatsapp_digits(phone) -> str:
    """
    Return the digits-only form of ``phone``, or ``''`` when it is not a
    usable number (empty, or fewer than MIN_WHATSAPP_DIGITS digits).
    """
    if not phone:
        return ''
    digits = re.sub(r'\D', '', str(phone))
    if len(digits) < MIN_WHATSAPP_DIGITS:
        return ''
    return digits


def whatsapp_link(phone) -> str:
    """Return a wa.me click-to-chat URL for ``phone``, or ``''`` if invalid."""
    digits = whatsapp_digits(phone)
    return f'https://wa.me/{digits}' if digits else ''


def _meta_graph_send(to: str, body: str, event: str, payload: dict) -> bool:
    """Send a WhatsApp message via the Meta Graph API.

    This is the real delivery path for WhatsApp Business Platform — Meta
    accepts a POST to the ``/c/{phone_number_id}/messages`` endpoint and
    returns a message ID on success.  Requires
    ``ADMIN_WHATSAPP_ACCESS_TOKEN`` and ``ADMIN_WHATSAPP_NUMBER_ID`` in
    ``settings`` (described below).
    """
    api_url = (
        f"https://graph.facebook.com/v18.0/c/"
        f"{getattr(settings, 'ADMIN_WHATSAPP_NUMBER_ID', '')}/messages"
    )
    access_token = getattr(settings, "ADMIN_WHATSAPP_ACCESS_TOKEN", "")
    if not access_token:
        logger.warning(
            "ADMIN_WHATSAPP_ACCESS_TOKEN not set; cannot send via Meta Graph API"
        )
        return False

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to,
        "text": {"body": body},
    }

    try:
        response = requests.post(
            api_url,
            headers=headers,
            json=data,
            timeout=10,
        )
        response.raise_for_status()
        result = response.json()
        logger.info(
            "Meta Graph API send OK | to=%s | message_id=%s",
            to,
            result.get("messages", [{}])[0].get("id"),
        )
        return True
    except Exception:
        logger.exception(
            "Meta Graph API send failed | to=%s | url=%s", to, api_url
        )
        return False


def notify_admin(message: str, *, event: str, payload: dict) -> bool:
    """Send an operational alert to Admin via Gmail / Email (and optional WhatsApp gateway).

    Controlled by ``ADMIN_NOTIFICATION_CHANNEL``:
      - 'email' (default): Sends directly to Admin Gmail (ADMIN_EMAIL).
      - 'both': Dispatches to Admin Gmail and the WhatsApp webhook.
      - 'whatsapp': Dispatches to the WhatsApp webhook.
    """
    channel = getattr(settings, 'ADMIN_NOTIFICATION_CHANNEL', 'email').lower()
    email_delivered = False
    whatsapp_delivered = False

    # 1. Primary path: Delivery to Admin Gmail
    if channel in ('email', 'both'):
        try:
            from GETMECARE.email_utils import send_admin_general_alert_email, send_admin_new_care_request_email
            if event == 'care_request_created' and payload:
                email_delivered = send_admin_new_care_request_email(payload)
            else:
                email_delivered = send_admin_general_alert_email(
                    subject=event.replace('_', ' ').title(),
                    message=message,
                    event=event,
                    payload=payload,
                )
            if email_delivered:
                logger.info("Admin alert delivered to Gmail | event=%s", event)
        except Exception:
            logger.exception("Failed to deliver admin alert to Gmail | event=%s", event)

    # 2. WhatsApp gateway (if configured or enabled)
    webhook_url = getattr(settings, "ADMIN_WHATSAPP_WEBHOOK_URL", "")
    if (channel in ('whatsapp', 'both') or not email_delivered) and webhook_url:
        try:
            response = requests.post(
                webhook_url,
                json={
                    "to": getattr(settings, "ADMIN_WHATSAPP_NUMBER", ""),
                    "body": message,
                    "event": event,
                    "payload": payload,
                },
                timeout=8,
            )
            response.raise_for_status()
            logger.info(
                "WhatsApp alert pushed to webhook | url=%s | event=%s",
                webhook_url,
                event,
            )
            whatsapp_delivered = True
        except Exception:
            logger.exception(
                "WhatsApp webhook push failed | url=%s | event=%s",
                webhook_url,
                event,
            )

    if email_delivered or whatsapp_delivered:
        return True

    logger.info("Admin alert logged (console fallback): event=%s\n%s", event, message)
    return False
