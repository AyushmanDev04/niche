"""Stock enforcement at the API level (single-request correctness, not the
true concurrency race — see tests/test_concurrency.py for that)."""


def _tracked_item(client, auth, stock=5, price=10.0):
    owner, _, _ = auth("keeper", role="shopkeeper")
    store = client.post("/store", json={"name": "Shop"}, headers=owner).get_json()
    item = client.post(
        "/item",
        json={"name": "Widget", "price": price, "store_id": store["id"], "stock_quantity": stock},
        headers=owner,
    ).get_json()
    return owner, store, item


class TestStockEnforcement:
    def test_ordering_within_stock_succeeds_and_decrements(self, client, auth):
        owner, _, item = _tracked_item(client, auth, stock=5)
        buyer, _, _ = auth("buyer", role="customer")

        response = client.post(
            f"/item/{item['id']}/order", json={"quantity": 3}, headers=buyer
        )
        assert response.status_code == 201

        fetched = client.get(f"/item/{item['id']}", headers=owner).get_json()
        assert fetched["stock_quantity"] == 2

    def test_ordering_more_than_available_is_rejected(self, client, auth):
        _, _, item = _tracked_item(client, auth, stock=2)
        buyer, _, _ = auth("buyer", role="customer")

        response = client.post(
            f"/item/{item['id']}/order", json={"quantity": 3}, headers=buyer
        )
        assert response.status_code == 409
        assert "2 left" in response.get_json()["message"]

    def test_stock_is_not_touched_by_a_rejected_order(self, client, auth):
        owner, _, item = _tracked_item(client, auth, stock=2)
        buyer, _, _ = auth("buyer", role="customer")
        client.post(f"/item/{item['id']}/order", json={"quantity": 5}, headers=buyer)

        fetched = client.get(f"/item/{item['id']}", headers=owner).get_json()
        assert fetched["stock_quantity"] == 2

    def test_exactly_the_last_unit_can_be_ordered(self, client, auth):
        _, _, item = _tracked_item(client, auth, stock=1)
        buyer, _, _ = auth("buyer", role="customer")
        assert client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        ).status_code == 201

    def test_out_of_stock_item_cannot_be_ordered_at_all(self, client, auth):
        owner, _, item = _tracked_item(client, auth, stock=1)
        buyer, _, _ = auth("buyer", role="customer")
        client.post(f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer)

        response = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        )
        assert response.status_code == 409
        assert "out of stock" in response.get_json()["message"].lower()

    def test_untracked_item_has_no_stock_limit(self, client, auth):
        """stock_quantity=None means unlimited — the behaviour every item had
        before stock tracking existed, preserved for items that opt out."""
        owner, _, _ = auth("keeper", role="shopkeeper")
        store = client.post("/store", json={"name": "Shop"}, headers=owner).get_json()
        item = client.post(
            "/item",
            json={"name": "Widget", "price": 5.0, "store_id": store["id"]},
            headers=owner,
        ).get_json()
        assert item["stock_quantity"] is None

        buyer, _, _ = auth("buyer", role="customer")
        response = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1000}, headers=buyer
        )
        assert response.status_code == 201


class TestStockRestoredOnCancellation:
    def test_cancelling_a_pending_order_gives_stock_back(self, client, auth):
        owner, _, item = _tracked_item(client, auth, stock=5)
        buyer, _, _ = auth("buyer", role="customer")

        order = client.post(
            f"/item/{item['id']}/order", json={"quantity": 3}, headers=buyer
        ).get_json()
        assert client.get(f"/item/{item['id']}", headers=owner).get_json()["stock_quantity"] == 2

        client.post(
            f"/order/{order['id']}/transition", json={"status": "cancelled"}, headers=buyer
        )
        assert client.get(f"/item/{item['id']}", headers=owner).get_json()["stock_quantity"] == 5

    def test_cancelling_after_shop_accepted_also_restores_stock(self, client, auth):
        owner, _, item = _tracked_item(client, auth, stock=5)
        buyer, _, _ = auth("buyer", role="customer")
        order = client.post(
            f"/item/{item['id']}/order", json={"quantity": 3}, headers=buyer
        ).get_json()

        client.post(f"/order/{order['id']}/transition", json={"status": "accepted"}, headers=owner)
        client.post(f"/order/{order['id']}/transition", json={"status": "cancelled"}, headers=owner)

        assert client.get(f"/item/{item['id']}", headers=owner).get_json()["stock_quantity"] == 5

    def test_item_sold_out_can_be_ordered_again_after_a_cancellation(self, client, auth):
        _, _, item = _tracked_item(client, auth, stock=1)
        buyer, _, _ = auth("buyer", role="customer")
        order = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        ).get_json()
        assert client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        ).status_code == 409

        client.post(
            f"/order/{order['id']}/transition", json={"status": "cancelled"}, headers=buyer
        )
        assert client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        ).status_code == 201


class TestStockEditing:
    """The shopkeeper's edit dialog is the only way stock gets set after
    creation, so the PUT path needs to round-trip both a number and a null."""

    def test_stock_can_be_changed_by_the_shop(self, client, auth):
        owner, _, item = _tracked_item(client, auth, stock=5)

        response = client.put(
            f"/item/{item['id']}",
            json={"name": item["name"], "price": item["price"], "stock_quantity": 12},
            headers=owner,
        )
        assert response.status_code == 200
        assert response.get_json()["stock_quantity"] == 12

    def test_explicit_null_stops_tracking_stock(self, client, auth):
        owner, _, item = _tracked_item(client, auth, stock=3)

        response = client.put(
            f"/item/{item['id']}",
            json={"name": item["name"], "price": item["price"], "stock_quantity": None},
            headers=owner,
        )
        assert response.status_code == 200
        assert response.get_json()["stock_quantity"] is None

        buyer, _, _ = auth("buyer", role="customer")
        assert client.post(
            f"/item/{item['id']}/order", json={"quantity": 50}, headers=buyer
        ).status_code == 201

    def test_omitting_stock_leaves_it_untouched(self, client, auth):
        owner, _, item = _tracked_item(client, auth, stock=7)

        client.put(
            f"/item/{item['id']}",
            json={"name": "Renamed", "price": item["price"]},
            headers=owner,
        )
        assert client.get(f"/item/{item['id']}", headers=owner).get_json()["stock_quantity"] == 7

    def test_negative_stock_is_rejected(self, client, auth):
        owner, _, item = _tracked_item(client, auth, stock=4)

        response = client.put(
            f"/item/{item['id']}",
            json={"name": item["name"], "price": item["price"], "stock_quantity": -1},
            headers=owner,
        )
        assert response.status_code == 422
        assert client.get(f"/item/{item['id']}", headers=owner).get_json()["stock_quantity"] == 4

    def test_a_customer_cannot_change_stock(self, client, auth):
        owner, _, item = _tracked_item(client, auth, stock=4)
        buyer, _, _ = auth("buyer", role="customer")

        response = client.put(
            f"/item/{item['id']}",
            json={"name": item["name"], "price": item["price"], "stock_quantity": 999},
            headers=buyer,
        )
        assert response.status_code == 403
        assert client.get(f"/item/{item['id']}", headers=owner).get_json()["stock_quantity"] == 4
