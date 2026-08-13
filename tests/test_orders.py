"""Order records: pricing, references, and delivery details."""


def _shop(client, auth, price=10.0):
    owner, _, _ = auth("keeper", role="shopkeeper")
    store = client.post("/store", json={"name": "Shop"}, headers=owner).get_json()
    item = client.post(
        "/item",
        json={"name": "Widget", "price": price, "store_id": store["id"]},
        headers=owner,
    ).get_json()
    return owner, store, item


class TestOrderPricing:
    def test_price_is_frozen_at_purchase_time(self, client, auth):
        """The bug this guards: totals were derived from items.price, so a
        later price change rewrote the value of orders already placed."""
        owner, _, item = _shop(client, auth, price=10.0)
        buyer, _, _ = auth("buyer", role="customer")

        order = client.post(
            f"/item/{item['id']}/order", json={"quantity": 3}, headers=buyer
        ).get_json()
        assert order["unit_price"] == 10.0
        assert order["total"] == 30.0

        assert client.put(
            f"/item/{item['id']}", json={"price": 20.0}, headers=owner
        ).status_code == 200

        orders = client.get("/orders", headers=buyer).get_json()
        assert orders[0]["unit_price"] == 10.0, "historical price changed"
        assert orders[0]["total"] == 30.0, "historical total changed"

    def test_total_is_unit_price_times_quantity(self, client, auth):
        _, _, item = _shop(client, auth, price=12.5)
        buyer, _, _ = auth("buyer", role="customer")
        order = client.post(
            f"/item/{item['id']}/order", json={"quantity": 4}, headers=buyer
        ).get_json()
        assert order["total"] == 50.0

    def test_fractional_prices_do_not_drift(self, client, auth):
        """0.1 has no exact binary float representation; Numeric avoids the
        accumulating error a float total would show."""
        _, _, item = _shop(client, auth, price=0.10)
        buyer, _, _ = auth("buyer", role="customer")
        order = client.post(
            f"/item/{item['id']}/order", json={"quantity": 3}, headers=buyer
        ).get_json()
        assert order["total"] == 0.30

    def test_item_price_is_stored_as_exact_decimal(self, client, auth):
        """items.price was Float while orders.unit_price was already
        Numeric(10, 2), so the value a price was snapshotted *from* was the
        one place money still went through binary floating point."""
        from decimal import Decimal

        from db import db
        from models import ItemModel

        _, _, item = _shop(client, auth, price=19.99)

        with client.application.app_context():
            stored = db.session.get(ItemModel, item["id"]).price

        assert isinstance(stored, Decimal)
        assert stored == Decimal("19.99")

    def test_item_price_survives_a_round_trip_unrounded(self, client, auth):
        owner, _, item = _shop(client, auth, price=0.10)
        assert client.get(f"/item/{item['id']}", headers=owner).get_json()["price"] == 0.10


class TestOrderReference:
    def test_order_has_a_quotable_reference(self, client, auth):
        _, _, item = _shop(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
        order = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        ).get_json()
        assert order["reference"].startswith("ORD-")

    def test_reference_is_opaque_not_derived_from_the_id(self, client, auth):
        """Regression guard: references used to be f"ORD-{id:05d}", directly
        exposing the row's sequential primary key and how many orders exist
        platform-wide. They're now a random token — see references.py."""
        _, _, item = _shop(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
        order = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        ).get_json()
        assert order["reference"] != f"ORD-{order['id']:05d}"
        suffix = order["reference"].removeprefix("ORD-")
        assert len(suffix) == 8
        assert all(c in "0123456789ABCDEF" for c in suffix)

    def test_two_orders_get_different_references(self, client, auth):
        _, _, item = _shop(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
        first = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        ).get_json()
        second = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        ).get_json()
        assert first["reference"] != second["reference"]

    def test_reference_is_stable_across_reads(self, client, auth):
        _, _, item = _shop(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
        created = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        ).get_json()
        listed = client.get("/orders", headers=buyer).get_json()[0]
        assert listed["reference"] == created["reference"]


class TestDeliveryDetails:
    def test_address_and_phone_are_recorded(self, client, auth):
        _, _, item = _shop(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
        order = client.post(
            f"/item/{item['id']}/order",
            json={
                "quantity": 1,
                "delivery_address": "12 Nehru Road, Kanpur 208001",
                "contact_phone": "9876543210",
            },
            headers=buyer,
        ).get_json()
        assert order["delivery_address"] == "12 Nehru Road, Kanpur 208001"
        assert order["contact_phone"] == "9876543210"

    def test_shopkeeper_sees_delivery_details_on_incoming_orders(self, client, auth):
        """The shop cannot fulfil an order without them."""
        owner, store, item = _shop(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
        client.post(
            f"/item/{item['id']}/order",
            json={"quantity": 2, "delivery_address": "5 MG Road", "contact_phone": "9000000000"},
            headers=buyer,
        )

        incoming = client.get(f"/store/{store['id']}/order", headers=owner).get_json()
        assert incoming[0]["delivery_address"] == "5 MG Road"
        assert incoming[0]["contact_phone"] == "9000000000"
        assert incoming[0]["total"] == 20.0

    def test_over_long_address_is_rejected(self, client, auth):
        _, _, item = _shop(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
        response = client.post(
            f"/item/{item['id']}/order",
            json={"quantity": 1, "delivery_address": "x" * 301},
            headers=buyer,
        )
        assert response.status_code == 422

    def test_order_without_address_still_works(self, client, auth):
        """Kept optional so existing API clients do not break."""
        _, _, item = _shop(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
        response = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        )
        assert response.status_code == 201
        assert response.get_json()["delivery_address"] is None
