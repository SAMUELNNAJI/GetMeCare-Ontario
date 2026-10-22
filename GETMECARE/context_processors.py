"""
Project-level context processors.

These run on every request so that dashboard base templates
(base_caregiver.html, base_employer.html) always have the sidebar
context variables they need — regardless of which view is active.
"""


def _get_total_unread(user):
    """
    Return the total number of unread items in the user's message inbox:
      - Unread DirectMessages sent by others
      - Unread (pending + not yet seen) BookingProposals received by this employer
    """
    try:
        from django.db.models import Q
        from Chatbot.models import DirectConversation, DirectMessage
        from Account.models import BookingProposal

        # Count unread direct messages across all conversations in a single query
        unread_msgs = DirectMessage.objects.filter(
            conversation__in=DirectConversation.objects.filter(
                Q(participant_1=user) | Q(participant_2=user)
            ),
            is_read=False
        ).exclude(sender=user).count()

        # Count unread proposals (employer only — proposals are sent TO the employer)
        unread_proposals = 0
        if getattr(user, 'is_employer', False):
            unread_proposals = BookingProposal.objects.filter(
                employer=user,
                status=BookingProposal.STATUS_PENDING,
                is_read=False,
            ).count()

        return unread_msgs + unread_proposals
    except Exception:
        return 0


def _get_support_unread_count(user):
    try:
        from Chatbot.models import SupportMessage
        return SupportMessage.objects.filter(
            chat__user=user,
            is_read=False,
        ).exclude(sender=user).count()
    except Exception:
        return 0


def sidebar_context(request):
    """
    Inject sidebar data for the current authenticated user.
    Safe to call on every request — returns {} for anonymous users
    and for users that don't match either role.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}

    ctx = {}

    if request.user.is_caregiver:
        try:
            from CareGiverAcc.views import _sidebar_context
            ctx = _sidebar_context(request.user)
        except Exception:
            pass

        if ctx.get('profile'):
            try:
                from Account.models import CaregiverProfile
                from Account.forms import REQUIRED_DOC_TYPES
                profile = ctx['profile']
                if profile.status != CaregiverProfile.STATUS_ACTIVE:
                    # Check permanent DB dismissal first — if set, never show again
                    if not profile.activation_modal_dismissed:
                        user_doc_types = set(
                            request.user.documents.filter(
                                doc_type__in=REQUIRED_DOC_TYPES
                            ).values_list('doc_type', flat=True).distinct()
                        )
                        all_docs_uploaded = len(user_doc_types) == len(REQUIRED_DOC_TYPES)
                        profile_complete = bool(
                            profile.care_type
                            and profile.hourly_rate is not None
                            and profile.city
                            and profile.skills
                        )
                        if not all_docs_uploaded or not profile_complete:
                            ctx['show_activation_modal'] = True
            except Exception:
                pass

    elif request.user.is_employer:
        try:
            from EmployerApp.views import _employer_ctx
            ctx = _employer_ctx(request.user)
        except Exception:
            pass

    # ── WhatsApp popup gate ──────────────────────────────
    # Auto-show the "Add WhatsApp" popup on the dashboard for
    # old users (caregivers or employers) who have not saved a usable WhatsApp number yet.
    if request.user.is_authenticated and not request.session.get('dismissed_whatsapp_modal'):
        try:
            from GETMECARE.whatsapp import whatsapp_digits
            ctx['show_whatsapp_modal'] = not bool(whatsapp_digits(request.user.phone))
        except Exception:
            ctx['show_whatsapp_modal'] = False
    else:
        ctx['show_whatsapp_modal'] = False

    # Inject unread count for both roles
    ctx['total_unread'] = _get_total_unread(request.user)
    ctx['support_unread_count'] = _get_support_unread_count(request.user)

    # Add upcoming shifts count for caregivers
    if request.user.is_caregiver:
        try:
            from Account.models import Shift
            from django.utils import timezone
            today = timezone.now().date()
            upcoming_shifts_count = Shift.objects.filter(
                caregiver=request.user,
                status=Shift.STATUS_SCHEDULED,
                start_date__gte=today,
            ).count()
            ctx['upcoming_shifts_count'] = upcoming_shifts_count
        except Exception:
            ctx['upcoming_shifts_count'] = 0

    # Notifications system for topbar bell
    try:
        from Account.views import ensure_user_notifications
        ensure_user_notifications(request.user)
        ctx['user_notifications'] = list(request.user.notifications.all()[:15])
        ctx['unread_notifications_count'] = request.user.notifications.filter(is_read=False).count()
    except Exception:
        ctx['user_notifications'] = []
        ctx['unread_notifications_count'] = 0

    return ctx




def admin_whatsapp_number(request):
    """
    Inject the admin WhatsApp number into every template context.
    """
    from django.conf import settings
    # Use the admin WhatsApp number from settings; fall back to a placeholder
    return {
        'admin_whatsapp_number': getattr(settings, 'ADMIN_WHATSAPP_NUMBER', '+12494812647'),
    }
