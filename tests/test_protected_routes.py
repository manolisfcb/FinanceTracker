import pytest

PROTECTED_ROUTES = [
    "/portfolio",
    "/dash",
    "/stocks",
    "/transactions",
    "/transactions_charts",
]


@pytest.mark.parametrize("path", PROTECTED_ROUTES)
def test_anonymous_access_redirects_to_login(client, path):
    resp = client.get(path)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


@pytest.mark.parametrize("path", ["/portfolio", "/dash", "/stocks", "/transactions", "/transactions_charts"])
def test_authenticated_access_succeeds(auth_client, path):
    resp = auth_client.get(path)
    assert resp.status_code == 200
