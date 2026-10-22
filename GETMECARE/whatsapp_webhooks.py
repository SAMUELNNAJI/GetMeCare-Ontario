"""Webhook routes for WhatsApp Business Platform (Meta) callbacks.

Meta sends status updates (sent -> delivered -> read) and event webhooks to
this endpoint.  The admin-alert sender uses the Meta Graph API, not a generic
HTTP POST.
"""

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings

import logging
import hmac
import hashlib

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def whatsapp_webhook(request):
    """Receive Meta/WhatsApp Business Platform callbacks.

    Returns a 200 OK with a plain-text "ok" so Meta's validation succeeds.
    """
    # --- Verification challenge (required by Meta on webhook registration) ---
    # Meta sends a GET with a "hub.verify_token" and expects "hub.challenge".
    verify_token = getattr(settings, "ADMIN_WHATSAPP_WEBHOOK_VERIFY_TOKEN", "")
    if request.method == "GET":
        mode = request.GET.get("hub.mode", "")
        token = request.GET.get("hub.verify_token", "")
        challenge = request.GET.get("hub.challenge", "")
        if mode == "subscribe" and token == verify_token:
            return JsonResponse({"hub.challenge": challenge})
        return JsonResponse({"error": "invalid verify token"}, status=403)

    # --- Event callback (POST) ---
    # Meta sends JSON like:
    #   {"entry":[{"id":"<phone_number_id>","changes":[
    #       {"value":{"status":"delivered","timestamp":"..."},"field":"status"}]}]}
    try:
        data = request.body.decode("utf-8")
        logger.info("WhatsApp webhook received: %s", data[:500])
    except Exception:
        logger.exception("Failed to parse WhatsApp webhook body")
        return JsonResponse({"error": "bad request"}, status=400)

    # Basic signature check (optional but recommended). Settings should hold
    # ADMIN_WHATSAPP_WEBHOOK_SECRET (the "whsec_..." value from Meta).
    signature = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")
    if signature and getattr(settings, "ADMIN_WHATSAPP_WEBHOOK_SECRET", ""):
        expected = "sha256=" + hmac.new(
            getattr(settings, "ADMIN_WHATSAPP_WEBHOOK_SECRET", "").encode(),
            request.body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            logger.warning("WhatsApp webhook signature mismatch")
            return JsonResponse({"error": "forbidden"}, status=403)

    # Normalise the payload to a simple structure for logging.
    try:
        import json

        payload = json.loads(data)
    except Exception:
        payload = {"raw": data[:500]}

    entry = payload.get("entry", [])
    for entry_obj in entry:
        changes = entry_obj.get("changes", [])
        for change in changes:
            value = change.get("value", {})
            field = change.get("field", "")
            logger.info(
                "WhatsApp %s update: %s | from: %s | timestamp: %s",
                field,
                value.get("status"),
                value.get("from"),
                value.get("timestamp"),
            )

    return JsonResponse({"received": True})
