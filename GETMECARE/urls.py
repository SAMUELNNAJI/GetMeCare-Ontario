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
class CorrectDomainPasswordResetView(auth_views.PasswordResetView):
    template_name             = 'registration/password_reset_form.html'
    email_template_name       = 'registration/password_reset_email.html'
    html_email_template_name  = 'registration/password_reset_email.html'
    subject_template_name     = 'registration/password_reset_subject.txt'

    def get_extra_email_context(self):
        ctx = super().get_extra_email_context() or {}
        # Override domain and protocol from the live request — always correct.
        ctx['domain']   = self.request.get_host()
        ctx['protocol'] = 'https' if self.request.is_secure() else 'http'
        return ctx

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
        }
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
        auth_views.PasswordResetConfirmView.as_view(
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
