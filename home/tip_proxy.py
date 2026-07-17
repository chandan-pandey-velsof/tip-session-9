"""TIP API proxy — SHIPPED BY THE PLATFORM. DO NOT MODIFY OR RECREATE THIS FILE.

The browser calls same-origin ``/tip-api/<path>``; this view forwards the request to the
TIP backend with the API key attached server-side, so the token never reaches the client.

It is deliberately generic and correct for every TIP endpoint:

* forwards ANY HTTP method,
* forwards the RAW request body and the ORIGINAL ``Content-Type`` header — so JSON,
  ``application/x-www-form-urlencoded``, and ``multipart/form-data`` (incl. file uploads
  like ``predictor/predict``) all pass through with their boundary intact,
* forwards the query string,
* streams the upstream response back VERBATIM (raw bytes, status, content-type) — it never
  re-JSON-encodes the body, so it cannot raise "Object of type bytes is not JSON
  serializable", and it works for ``/v1/*`` and non-versioned paths (e.g. ``/portfolio/*``)
  identically.

Because this file is shipped and never regenerated, every deployed page gets the exact same
correct proxy. Do not ask the model to write a proxy — call ``/tip-api/<endpoint>`` from the
page's JavaScript and this handles the rest.
"""
import requests
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

# Hop-by-hop / recomputed headers we must not forward as-is. Dropping accept-encoding
# means the upstream returns an uncompressed body, so streaming `.content` back with the
# upstream Content-Type is always consistent for the browser.
_DROP_HEADERS = {"host", "content-length", "connection", "accept-encoding"}


@csrf_exempt
def tip_api_proxy(request, path):
    base = (settings.TIP_API_URL or "").rstrip("/")
    url = f"{base}/{path.lstrip('/')}"

    headers = {k: v for k, v in request.headers.items() if k.lower() not in _DROP_HEADERS}
    headers["x-api-key"] = settings.TIP_API_TOKEN  # server-side key; NOT Authorization

    try:
        upstream = requests.request(
            method=request.method,
            url=url,
            params=request.GET.dict(),   # preserve query string (app_num, status, biblo_id, ...)
            data=request.body,           # raw bytes → JSON, form-data, multipart, uploads all work
            headers=headers,
            timeout=60,
        )
    except requests.RequestException:
        return HttpResponse(
            b'{"status": false, "message": "proxy_error"}',
            status=502, content_type="application/json",
        )

    # Return the upstream response UNCHANGED — raw bytes, status, and content-type.
    return HttpResponse(
        upstream.content,
        status=upstream.status_code,
        content_type=upstream.headers.get("Content-Type", "application/json"),
    )
