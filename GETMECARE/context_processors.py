"""
Project-level context processors.

These run on every request so that dashboard base templates
(base_caregiver.html, base_employer.html) always have the sidebar
context variables they need — regardless of which view is active.
"""


def sidebar_context(request):
    """
    Inject sidebar data for the current authenticated user.
    Safe to call on every request — returns {} for anonymous users
    and for users that don't match either role.
    """
    if not request.user.is_authenticated:
        return {}

    role = getattr(request.user, 'role', None)

    if role == 'caregiver':
        try:
            from CareGiverAcc.views import _sidebar_context
            return _sidebar_context(request.user)
        except Exception:
            return {}

    if role == 'employer':
        try:
            from EmployerApp.views import _employer_ctx
            return _employer_ctx(request.user)
        except Exception:
            return {}

    return {}
