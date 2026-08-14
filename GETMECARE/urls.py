"""
URL configuration for GETMECARE project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import render
from django.views.generic import TemplateView
from django.contrib.auth import views as auth_views
from GETMECARE.sitemaps import StaticViewSitemap, CaregiverSitemap, JobSitemap


# ── Custom password-reset view — injects the real domain from the request
# so the reset link never points to example.com regardless of the sites table.
#
# Root cause: Django's PasswordResetForm.save() calls get_context() which
# reads domain from django.contrib.sites (defaults to "example.com").
# Fix: subclass PasswordResetForm and override save() to pass domain/protocol
# from the request, then inject a pre-built {{ reset_url }} into the template
# context so the email template never needs {% url %} at render time.

from django import forms as _dj_forms
from django.contrib.auth.forms import PasswordResetForm as _BaseResetForm
from django.contrib.auth.tokens import default_token_generator as _token_gen
from django.utils.http import urlsafe_base64_encode as _b64enc
from django.utils.encoding import force_bytes as _fbytes
from django.core.mail import EmailMultiAlternatives as _EmailAlt
from django.template import loader as _loader


class _FixedDomainPasswordResetForm(_BaseResetForm):
    """
    Identical to Django's PasswordResetForm except it receives `domain` and
    `protocol` as explicit kwargs (from the request) so the reset link is
    always absolute and points to the real server, not example.com.
    """

    def save(
        self,
        domain_override=None,
        subject_template_name='registration/password_reset_subject.txt',
        email_template_name='registration/password_reset_email.html',
        use_https=False,
        token_generator=_token_gen,
        from_email=None,
        request=None,
        html_email_template_name=None,
        extra_email_context=None,
    ):
        from django.contrib.auth import get_user_model
        UserModel = get_user_model()
        email_field_name = UserModel.get_email_field_name()

        # Pull the real domain & protocol from extra_email_context if provided,
        # fall back to domain_override, then finally to the request host.
        protocol = 'http'
        domain   = domain_override or 'getmecare-ontario.com'
        if extra_email_context:
            protocol = extra_email_context.get('protocol', protocol)
            domain   = extra_email_context.get('domain', domain)
        elif request:
            protocol = 'https' if use_https else 'http'
            domain   = request.get_host()

        for user in self.get_users(self.cleaned_data['email']):
            uid   = _b64enc(_fbytes(user.pk))
            token = token_generator.make_token(user)

            # Build the fully-qualified reset URL right here.
            confirm_path = (
                f'/password-reset/confirm/{uid}/{token}/'
            )
            reset_url = f'{protocol}://{domain}{confirm_path}'

            ctx = {
                'email':     getattr(user, email_field_name),
                'domain':    domain,
                'site_name': 'GetMeCare Ontario',
                'uid':       uid,
                'user':      user,
                'token':     token,
                'protocol':  protocol,
                'reset_url': reset_url,   # ← the pre-built absolute URL
            }
            if extra_email_context:
                ctx.update(extra_email_context)

            subject = _loader.render_to_string(subject_template_name, ctx)
            subject = ''.join(subject.splitlines())   # no newlines in subject
            body    = _loader.render_to_string(email_template_name, ctx)

            email_message = _EmailAlt(subject, body, from_email, [getattr(user, email_field_name)])
            if html_email_template_name:
                html = _loader.render_to_string(html_email_template_name, ctx)
                email_message.attach_alternative(html, 'text/html')
            email_message.send()


class CorrectDomainPasswordResetView(auth_views.PasswordResetView):
    template_name             = 'registration/password_reset_form.html'
    email_template_name       = 'registration/password_reset_email.html'
    html_email_template_name  = 'registration/password_reset_email.html'
    subject_template_name     = 'registration/password_reset_subject.txt'
    form_class                = _FixedDomainPasswordResetForm

    def get_extra_email_context(self):
        ctx = super().get_extra_email_context() or {}
        ctx['domain']   = self.request.get_host()
        ctx['protocol'] = 'https' if self.request.is_secure() else 'http'
        return ctx


class _PasswordChangedConfirmView(auth_views.PasswordResetConfirmView):
    """
    Extends Django's PasswordResetConfirmView to send a confirmation email
    after the user successfully sets a new password via the reset link.
    """
    template_name        = 'registration/password_reset_confirm.html'
    success_url          = 'password_reset_complete'
    token_generator      = _token_gen

    def form_valid(self, form):
        response = super().form_valid(form)
        user = form.user
        try:
            from GETMECARE.email_utils import send_password_changed_email
            send_password_changed_email(user)
        except Exception:
            logger.exception('Password-changed email failed for user %s', user.pk)
        return response

# ── Custom error handler views ────────────────────────────────
def custom_bad_request(request, exception=None):
    return render(request, '400.html', status=400)


def custom_permission_denied(request, exception=None):
    return render(request, '403.html', status=403)


def custom_page_not_found(request, exception=None):
    return render(request, '404.html', status=404)


def custom_server_error(request):
    return render(request, '500.html', status=500)


handler400 = 'GETMECARE.urls.custom_bad_request'
handler403 = 'GETMECARE.urls.custom_permission_denied'
handler404 = 'GETMECARE.urls.custom_page_not_found'
handler500 = 'GETMECARE.urls.custom_server_error'


urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('sitemap.xml', sitemap, {
        'sitemaps': {
            'static': StaticViewSitemap,
            'caregivers': CaregiverSitemap,
            'jobs': JobSitemap,
        },
    }, name='django.contrib.sitemaps.views.sitemap'),
    # ── Password reset (ZeptoMail) ────────────────────────────
    path(
        'password-reset/',
        CorrectDomainPasswordResetView.as_view(),
        name='password_reset',
    ),
    path(
        'password-reset/done/',
        auth_views.PasswordResetDoneView.as_view(
            template_name='registration/password_reset_done.html',
        ),
        name='password_reset_done',
    ),
    path(
        'password-reset/confirm/<uidb64>/<token>/',
        _PasswordChangedConfirmView.as_view(
            template_name='registration/password_reset_confirm.html',
        ),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        auth_views.PasswordResetCompleteView.as_view(
            template_name='registration/password_reset_complete.html',
        ),
        name='password_reset_complete',
    ),
    path('', include('Caregiver.urls')),
    path('', include('Account.urls')),
    path('', include('AdminApp.urls')),
    path('', include('EmployerApp.urls')),
    path('', include('CareGiverAcc.urls')),
    path('chatbot/', include('Chatbot.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# ── Error-page preview URLs (development only) ────────────────
if settings.DEBUG:
    urlpatterns += [
        path('test-400/', custom_bad_request, name='test-400'),
        path('test-403/', custom_permission_denied, name='test-403'),
        path('test-404/', custom_page_not_found, name='test-404'),
        path('test-500/', custom_server_error, name='test-500'),
    ]
