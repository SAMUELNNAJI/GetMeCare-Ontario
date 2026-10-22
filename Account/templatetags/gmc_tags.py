from django import template

register = template.Library()


@register.filter
def wa_link(phone):
    """Return a wa.me click-to-chat URL for a phone number (digits only)."""
    # Shared with GETMECARE.whatsapp so the filter, the caregiver
    # "Add WhatsApp" endpoint and the admin badge all agree on validity.
    from GETMECARE.whatsapp import whatsapp_link
    return whatsapp_link(phone)


@register.filter
def status_badge_color(status):
    """Return the CSS class for a dispute status badge."""
    status_map = {
        'open': 'bg-danger',
        'under_review': 'bg-warning text-dark',
        'resolved': 'bg-success',
        'dismissed': 'bg-secondary',
        'pending': 'bg-info',
        'completed': 'bg-success',
        'paid': 'bg-success',
        'partial': 'bg-warning text-dark',
        'failed': 'bg-danger',
    }
    return status_map.get(status, 'bg-secondary')

