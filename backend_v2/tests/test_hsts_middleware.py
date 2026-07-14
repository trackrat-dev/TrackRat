"""Tests for the HSTS response-header middleware (main.hsts_header_middleware).

The domain is on the browser HSTS preload list, so every HTTPS response must
carry `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload`.
The header must NOT be emitted over plaintext (RFC 6797), which the middleware
decides from X-Forwarded-Proto (set by the GCE external load balancer) falling
back to the request scheme.
"""

EXPECTED_HSTS = "max-age=31536000; includeSubDomains; preload"


def test_hsts_present_when_forwarded_proto_https(client):
    """Behind the LB (X-Forwarded-Proto: https), HSTS is set with preload."""
    response = client.get("/health", headers={"X-Forwarded-Proto": "https"})
    assert response.status_code == 200
    assert response.headers.get("Strict-Transport-Security") == EXPECTED_HSTS


def test_hsts_absent_over_plain_http(client):
    """No X-Forwarded-Proto and an http scheme (TestClient default) => no HSTS.

    Sending HSTS over plaintext is a spec violation and lets an active MITM
    poison the max-age, so its absence here is the behavior we want.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_absent_when_forwarded_proto_http(client):
    """An explicit X-Forwarded-Proto: http (e.g. the :80 redirect path) => no HSTS."""
    response = client.get("/health", headers={"X-Forwarded-Proto": "http"})
    assert response.status_code == 200
    assert "Strict-Transport-Security" not in response.headers


def test_hsts_applied_to_api_route(client):
    """The header is a global response header, not health-specific."""
    response = client.get(
        "/api/v2/predictions/supported-stations",
        headers={"X-Forwarded-Proto": "https"},
    )
    # Endpoint may 200 with data; regardless of body, the security header rides along.
    assert response.headers.get("Strict-Transport-Security") == EXPECTED_HSTS
