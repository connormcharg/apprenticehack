"""Demo-friendly: never let browsers cache HTML pages (stale screens mid-demo)."""


class NoStoreHtmlMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.get('Content-Type', '').startswith('text/html'):
            response['Cache-Control'] = 'no-store, max-age=0'
        return response
