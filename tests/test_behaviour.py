"""Regression tests for the correctness bugs fixed here."""


def _store_with_item(client, headers, store_name, item_name, **item_fields):
    store = client.post("/store", json={"name": store_name}, headers=headers).get_json()
    payload = {"name": item_name, "price": 9.99, "store_id": store["id"]}
    payload.update(item_fields)
    item = client.post("/item", json=payload, headers=headers).get_json()
    return store, item


class TestPerStoreUniqueness:
    def test_two_stores_can_sell_the_same_item_name(self, client, auth):
        """items.name was globally unique, so this used to fail."""
        headers, _, _ = auth("owner", role="shopkeeper")
        _, first = _store_with_item(client, headers, "Store A", "Coffee")
        assert first.get("id")

        store_b = client.post("/store", json={"name": "Store B"}, headers=headers).get_json()
        response = client.post(
            "/item",
            json={"name": "Coffee", "price": 3.5, "store_id": store_b["id"]},
            headers=headers,
        )
        assert response.status_code == 201

    def test_same_name_twice_in_one_store_is_rejected(self, client, auth):
        headers, _, _ = auth("owner", role="shopkeeper")
        store, _ = _store_with_item(client, headers, "Store A", "Coffee")
        response = client.post(
            "/item",
            json={"name": "Coffee", "price": 3.5, "store_id": store["id"]},
            headers=headers,
        )
        assert response.status_code == 409

    def test_two_stores_can_share_a_tag_name(self, client, auth):
        headers, _, _ = auth("owner", role="shopkeeper")
        a = client.post("/store", json={"name": "A"}, headers=headers).get_json()
        b = client.post("/store", json={"name": "B"}, headers=headers).get_json()
        client.post(f"/store/{a['id']}/tag", json={"name": "sale"}, headers=headers)
        response = client.post(
            f"/store/{b['id']}/tag", json={"name": "sale"}, headers=headers
        )
        assert response.status_code == 201


class TestHiddenItems:
    def test_hidden_item_is_absent_from_public_listing(self, client, auth):
        owner, _, _ = auth("owner", role="shopkeeper")
        _, item = _store_with_item(client, owner, "Shop", "Secret")
        assert client.post(f"/item/{item['id']}/hide", headers=owner).status_code == 200

        shopper, _, _ = auth("shopper")
        listed = client.get("/item", headers=shopper).get_json()
        assert [i for i in listed if i["id"] == item["id"]] == []

        # ...and cannot be fetched directly either.
        assert client.get(f"/item/{item['id']}", headers=shopper).status_code == 404

    def test_staff_still_see_hidden_items(self, client, auth):
        owner, _, _ = auth("owner", role="shopkeeper")
        _, item = _store_with_item(client, owner, "Shop", "Secret")
        client.post(f"/item/{item['id']}/hide", headers=owner)

        listed = client.get("/item", headers=owner).get_json()
        assert [i for i in listed if i["id"] == item["id"]]

    def test_hidden_item_cannot_be_ordered(self, client, auth):
        owner, _, _ = auth("owner", role="shopkeeper")
        _, item = _store_with_item(client, owner, "Shop", "Secret")
        client.post(f"/item/{item['id']}/hide", headers=owner)

        shopper, _, _ = auth("shopper")
        response = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=shopper
        )
        assert response.status_code == 404


class TestValidation:
    def test_rating_outside_one_to_five_is_rejected(self, client, auth):
        owner, _, _ = auth("owner", role="shopkeeper")
        _, item = _store_with_item(client, owner, "Shop", "Widget")
        shopper, _, _ = auth("shopper")
        for bad in (0, 6, 9999, -3):
            response = client.post(
                f"/item/{item['id']}/review",
                json={"rating": bad, "comment": "x"},
                headers=shopper,
            )
            assert response.status_code == 422, f"rating {bad} was accepted"

    def test_negative_order_quantity_is_rejected(self, client, auth):
        owner, _, _ = auth("owner", role="shopkeeper")
        _, item = _store_with_item(client, owner, "Shop", "Widget")
        shopper, _, _ = auth("shopper")
        response = client.post(
            f"/item/{item['id']}/order", json={"quantity": -5}, headers=shopper
        )
        assert response.status_code == 422

    def test_one_review_per_user_per_item(self, client, auth):
        owner, _, _ = auth("owner", role="shopkeeper")
        _, item = _store_with_item(client, owner, "Shop", "Widget")
        shopper, _, _ = auth("shopper")

        first = client.post(
            f"/item/{item['id']}/review", json={"rating": 5}, headers=shopper
        )
        assert first.status_code == 201

        second = client.post(
            f"/item/{item['id']}/review", json={"rating": 1}, headers=shopper
        )
        assert second.status_code == 409


class TestItemUpdate:
    def test_image_url_edit_is_actually_applied(self, client, auth):
        """PUT accepted image_url, returned 200, and silently ignored it."""
        owner, _, _ = auth("owner", role="shopkeeper")
        _, item = _store_with_item(client, owner, "Shop", "Widget")

        new_url = "https://example.com/new.png"
        response = client.put(
            f"/item/{item['id']}", json={"image_url": new_url}, headers=owner
        )
        assert response.status_code == 200
        assert response.get_json()["image_url"] == new_url

        fetched = client.get(f"/item/{item['id']}", headers=owner).get_json()
        assert fetched["image_url"] == new_url


class TestCascadingDeletes:
    def test_deleting_a_user_with_orders_and_reviews_succeeds(self, client, auth):
        """reviews.user_id / orders.user_id are NOT NULL with no cascade, so
        this raised a foreign key violation on any database that enforces
        them (i.e. Postgres, but not SQLite by default)."""
        admin, _, _ = auth("admin", admin=True)
        owner, _, _ = auth("owner", role="shopkeeper")
        _, item = _store_with_item(client, owner, "Shop", "Widget")

        shopper, shopper_id, shopper_tokens = auth("shopper")
        assert client.post(
            f"/item/{item['id']}/order", json={"quantity": 2}, headers=shopper
        ).status_code == 201
        assert client.post(
            f"/item/{item['id']}/review", json={"rating": 4}, headers=shopper
        ).status_code == 201

        # A fresh token is required to delete a user.
        response = client.delete(f"/user/{shopper_id}", headers=admin)
        assert response.status_code == 200, response.get_json()

    def test_deleting_an_ordered_item_succeeds(self, client, auth):
        owner, _, _ = auth("owner", role="shopkeeper")
        _, item = _store_with_item(client, owner, "Shop", "Widget")
        shopper, _, _ = auth("shopper")
        client.post(f"/item/{item['id']}/order", json={"quantity": 1}, headers=shopper)

        assert client.delete(f"/item/{item['id']}", headers=owner).status_code == 200

    def test_activity_log_survives_user_deletion(self, client, auth):
        admin, _, _ = auth("admin", admin=True)
        _, victim_id, _ = auth("victim")

        client.delete(f"/user/{victim_id}", headers=admin)

        feed = client.get("/activity", headers=admin).get_json()
        # The username snapshot is the whole point of storing it.
        assert any(entry.get("username") == "victim" for entry in feed)


class TestTokenRefresh:
    def test_refresh_returns_a_working_access_token(self, client, auth):
        _, _, tokens = auth("someone")
        refresh_headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}

        response = client.post("/refresh", headers=refresh_headers)
        assert response.status_code == 200

        new_access = response.get_json()["access_token"]
        assert client.get(
            "/store", headers={"Authorization": f"Bearer {new_access}"}
        ).status_code == 200

    def test_refresh_token_is_single_use(self, client, auth):
        _, _, tokens = auth("someone")
        refresh_headers = {"Authorization": f"Bearer {tokens['refresh_token']}"}

        assert client.post("/refresh", headers=refresh_headers).status_code == 200
        assert client.post("/refresh", headers=refresh_headers).status_code == 401


class TestReviewSerialisation:
    def test_review_exposes_item_id(self, client, auth):
        """item_id was load_only, so the frontend had to infer it."""
        owner, _, _ = auth("owner", role="shopkeeper")
        _, item = _store_with_item(client, owner, "Shop", "Widget")
        shopper, _, _ = auth("shopper")
        client.post(f"/item/{item['id']}/review", json={"rating": 5}, headers=shopper)

        reviews = client.get(f"/item/{item['id']}/review").get_json()
        assert reviews[0]["item_id"] == item["id"]
