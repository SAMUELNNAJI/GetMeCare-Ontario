from django.http import HttpResponsePermanentRedirect


class CanonicalHostMiddleware:
    """Redirect non-canonical hosts to the primary host (getmecare-ontario.com).

    Addresses URL canonicalization audit findings. Only redirects when the
    request host is a known alias (www, or any non-primary host) and never
    touches local/test hosts so development and tests keep working.
    """

    PRIMARY_HOST = 'getmecare-ontario.com'
    SAFE_HOSTS = {'localhost', '127.0.0.1', 'testserver', 'getmecare-ontario.com'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(':')[0].lower()
        if host not in self.SAFE_HOSTS:
            # redirect any unknown/alias host to the primary host
            url = request.build_absolute_uri()
            # replace host portion
            try:
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(url)
                parsed = parsed._replace(netloc=self.PRIMARY_HOST)
                return HttpResponsePermanentRedirect(urlunparse(parsed))
            except Exception:
                pass
        # www -> non-www
        if host == 'www.getmecare-ontario.com':
            url = request.build_absolute_uri().replace(
                'www.getmecare-ontario.com', self.PRIMARY_HOST, 1
            )
            return HttpResponsePermanentRedirect(url)
        return self.get_response(request)
