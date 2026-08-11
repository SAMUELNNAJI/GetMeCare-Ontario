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
        if getattr(user, 'role', None) == 'employer':
            unread_proposals = BookingProposal.objects.filter(
                employer=user,
                status=BookingProposal.STATUS_PENDING,
                is_read=False,
            ).count()

        return unread_msgs + unread_proposals
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

    role = getattr(request.user, 'role', None)

    ctx = {}

    if role == 'caregiver':
        try:
            from CareGiverAcc.views import _sidebar_context
            ctx = _sidebar_context(request.user)
        except Exception:
            pass

    elif role == 'employer':
        try:
            from EmployerApp.views import _employer_ctx
            ctx = _employer_ctx(request.user)
        except Exception:
            pass

    # Inject unread count for both roles
    ctx['total_unread'] = _get_total_unread(request.user)

    # Add upcoming shifts count for caregivers
    if role == 'caregiver':
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

    return ctx
