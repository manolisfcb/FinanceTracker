def test_create_app_registers_expected_blueprints(app):
    blueprint_names = set(app.blueprints.keys())
    assert {"main", "auth", "portfolio", "stocks", "personal_finance"} <= blueprint_names


def test_home_page_is_public(client):
    resp = client.get("/")
    assert resp.status_code == 200
