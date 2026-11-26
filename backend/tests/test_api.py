"""Automated tests for the ShopEase API.  Run:  cd backend && python -m pytest -q"""
import importlib
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

CUSTOMER = {"name": "Asha Rao", "email": "asha@example.com", "phone": "98765 43210", "address": "12 MG Road, Bengaluru 560001"}


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DB_ENGINE", "sqlite")
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("ADMIN_TOKEN", "test-admin")
    import db
    import app as app_module
    importlib.reload(db)
    importlib.reload(app_module)
    return app_module.create_app().test_client()


def order(client, items, customer=CUSTOMER):
    return client.post("/api/orders", json={"customer": customer, "items": items})


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.get_json()["status"] == "ok"
    assert r.get_json()["database"] == "ok"


def test_products_and_filters(client):
    products = client.get("/api/products").get_json()
    assert len(products) == 12
    assert client.get("/api/categories").get_json() == ["Electronics", "Fashion", "Home"]
    assert len(client.get("/api/products?category=Fashion").get_json()) == 4
    assert [p["name"] for p in client.get("/api/products?q=watch").get_json()] == ["Smart Watch"]
    assert client.get("/api/products/1").get_json()["name"] == "Wireless Earbuds"
    assert client.get("/api/products/999").status_code == 404


def test_place_order_uses_database_prices_and_reduces_stock(client):
    before = client.get("/api/products/1").get_json()["stock"]
    r = order(client, [{"product_id": 1, "qty": 2, "price": 1}, {"product_id": 10, "qty": 1}])
    assert r.status_code == 201
    body = r.get_json()
    assert body["total"] == 2 * 2499 + 599          # the fake price 1 is ignored
    assert client.get("/api/products/1").get_json()["stock"] == before - 2
    found = client.get(f"/api/orders/{body['id']}?email=ASHA@example.com").get_json()
    assert found["status"] == "PLACED"
    assert len(found["items"]) == 2


def test_order_needs_matching_email(client):
    oid = order(client, [{"product_id": 2, "qty": 1}]).get_json()["id"]
    assert client.get(f"/api/orders/{oid}?email=someone@else.com").status_code == 404


def test_out_of_stock_and_bad_input(client):
    assert order(client, [{"product_id": 11, "qty": 1}]).status_code == 409      # Table Lamp has 0 in stock
    assert order(client, [{"product_id": 5, "qty": 4}]).status_code == 409       # only 3 power banks
    assert order(client, [{"product_id": 999, "qty": 1}]).status_code == 400
    assert order(client, [{"product_id": 1, "qty": 0}]).status_code == 400
    assert order(client, []).status_code == 400
    bad = dict(CUSTOMER, email="not-an-email", phone="123")
    r = order(client, [{"product_id": 1, "qty": 1}], bad)
    assert r.status_code == 400 and "email" in r.get_json()["error"] and "phone" in r.get_json()["error"]


def test_admin_needs_token_and_cancel_restocks(client):
    oid = order(client, [{"product_id": 3, "qty": 2}]).get_json()["id"]
    stock_after_order = client.get("/api/products/3").get_json()["stock"]
    assert client.get("/api/admin/orders").status_code == 401
    assert client.get("/api/admin/orders", headers={"X-Admin-Token": "wrong"}).status_code == 401
    h = {"X-Admin-Token": "test-admin"}
    assert client.get("/api/admin/orders", headers=h).get_json()[0]["id"] == oid
    assert client.patch(f"/api/admin/orders/{oid}", json={"status": "SHIPPED"}, headers=h).get_json()["status"] == "SHIPPED"
    assert client.patch(f"/api/admin/orders/{oid}", json={"status": "LOST"}, headers=h).status_code == 400
    client.patch(f"/api/admin/orders/{oid}", json={"status": "CANCELLED"}, headers=h)
    assert client.get("/api/products/3").get_json()["stock"] == stock_after_order + 2


def test_metrics(client):
    order(client, [{"product_id": 4, "qty": 1}])
    text = client.get("/metrics").get_data(as_text=True)
    assert "shopease_orders_total" in text
    assert 'route="/api/orders"' in text
    assert "shopease_products_low_stock" in text
