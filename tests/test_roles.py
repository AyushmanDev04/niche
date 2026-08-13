"""The customer/shopkeeper split.

Two rules define the marketplace:
  - customers buy and review, and cannot sell;
  - shopkeepers sell, and cannot review or buy.
"""


def _shop_with_item(client, auth, owner_name="keeper", item_name="Widget"):
    owner, _, _ = auth(owner_name, role="shopkeeper")
    store = client.post("/store", json={"name": "Shop"}, headers=owner).get_json()
    item = client.post(
        "/item",
        json={"name": item_name, "price": 10.0, "store_id": store["id"]},
        headers=owner,
    ).get_json()
    return owner, store, item


class TestCustomersCannotSell:
    def test_customer_cannot_create_a_store(self, client, auth):
        headers, _, _ = auth("buyer", role="customer")
        response = client.post("/store", json={"name": "Sneaky"}, headers=headers)
        assert response.status_code == 403
        assert "shopkeeper" in response.get_json()["message"].lower()

    def test_customer_cannot_create_an_item(self, client, auth):
        _, store, _ = _shop_with_item(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
        response = client.post(
            "/item",
            json={"name": "Contraband", "price": 1.0, "store_id": store["id"]},
            headers=buyer,
        )
        assert response.status_code == 403

    def test_customer_cannot_be_made_a_store_worker(self, client, auth):
        """Otherwise being hired would be a back door around the rule."""
        owner, store, _ = _shop_with_item(client, auth)
        auth("buyer", role="customer")
        response = client.post(
            f"/store/{store['id']}/worker", json={"username": "buyer"}, headers=owner
        )
        assert response.status_code == 400
        assert "customer" in response.get_json()["message"].lower()

    def test_shopkeeper_can_be_made_a_store_worker(self, client, auth):
        owner, store, _ = _shop_with_item(client, auth)
        auth("staff", role="shopkeeper")
        response = client.post(
            f"/store/{store['id']}/worker", json={"username": "staff"}, headers=owner
        )
        assert response.status_code == 200


class TestOnlyCustomersReview:
    def test_shopkeeper_cannot_review(self, client, auth):
        owner, _, item = _shop_with_item(client, auth)
        response = client.post(
            f"/item/{item['id']}/review", json={"rating": 5}, headers=owner
        )
        assert response.status_code == 403

    def test_shopkeeper_cannot_review_a_rival_store(self, client, auth):
        """Not just their own products — no selling account rates the market."""
        _, _, item = _shop_with_item(client, auth, owner_name="keeper")
        rival, _, _ = auth("rival", role="shopkeeper")
        response = client.post(
            f"/item/{item['id']}/review", json={"rating": 1}, headers=rival
        )
        assert response.status_code == 403

    def test_admin_cannot_review(self, client, auth):
        _, _, item = _shop_with_item(client, auth)
        admin, _, _ = auth("boss", admin=True, role="shopkeeper")
        response = client.post(
            f"/item/{item['id']}/review", json={"rating": 5}, headers=admin
        )
        assert response.status_code == 403

    def test_admin_with_customer_role_still_cannot_review(self, client, auth):
        """An admin carries an underlying role; being a "customer" admin must
        not become a way around the rule."""
        _, _, item = _shop_with_item(client, auth)
        admin, _, _ = auth("boss2", admin=True, role="customer")
        response = client.post(
            f"/item/{item['id']}/review", json={"rating": 5}, headers=admin
        )
        assert response.status_code == 403

    def test_customer_can_review(self, client, auth, delivered_buyer):
        owner, _, item = _shop_with_item(client, auth)
        buyer, _, _ = delivered_buyer(item, "buyer", owner)
        response = client.post(
            f"/item/{item['id']}/review",
            json={"rating": 4, "comment": "Solid."},
            headers=buyer,
        )
        assert response.status_code == 201

    def test_shopkeeper_cannot_order(self, client, auth):
        owner, _, item = _shop_with_item(client, auth)
        response = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=owner
        )
        assert response.status_code == 403


class TestReviewsRequireAPurchase:
    """A rating is only worth anything if the rater actually bought the thing.
    Any customer could review any item, bought or not."""

    def test_customer_who_never_ordered_cannot_review(self, client, auth):
        _, _, item = _shop_with_item(client, auth)
        stranger, _, _ = auth("stranger", role="customer")

        response = client.post(
            f"/item/{item['id']}/review", json={"rating": 5}, headers=stranger
        )
        assert response.status_code == 403
        assert "ordered" in response.get_json()["message"].lower()

    def test_a_pending_order_is_enough(self, client, auth):
        """Requiring a *delivered* order put reviewing behind the shop's own
        queue — only staff can advance an order past pending, so a shop that
        ignored its orders silenced every customer it had."""
        owner, _, item = _shop_with_item(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
        assert client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        ).status_code == 201

        response = client.post(
            f"/item/{item['id']}/review", json={"rating": 5}, headers=buyer
        )
        assert response.status_code == 201, response.get_json()

    def test_a_cancelled_order_is_not_enough(self, client, auth):
        owner, _, item = _shop_with_item(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
        order = client.post(
            f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
        ).get_json()
        assert client.post(
            f"/order/{order['id']}/transition",
            json={"status": "cancelled"},
            headers=buyer,
        ).status_code == 200

        response = client.post(
            f"/item/{item['id']}/review", json={"rating": 1}, headers=buyer
        )
        assert response.status_code == 403

    def test_buying_one_item_does_not_unlock_reviewing_another(
        self, client, auth, delivered_buyer
    ):
        owner, store, item = _shop_with_item(client, auth, item_name="Bought")
        other = client.post(
            "/item",
            json={"name": "Unbought", "price": 5.0, "store_id": store["id"]},
            headers=owner,
        ).get_json()

        buyer, _, _ = delivered_buyer(item, "buyer", owner)

        assert client.post(
            f"/item/{item['id']}/review", json={"rating": 5}, headers=buyer
        ).status_code == 201
        assert client.post(
            f"/item/{other['id']}/review", json={"rating": 1}, headers=buyer
        ).status_code == 403

    def test_a_delivered_order_unlocks_the_review(self, client, auth, delivered_buyer):
        owner, _, item = _shop_with_item(client, auth)
        buyer, _, _ = delivered_buyer(item, "buyer", owner)

        response = client.post(
            f"/item/{item['id']}/review",
            json={"rating": 4, "comment": "Arrived, works."},
            headers=buyer,
        )
        assert response.status_code == 201, response.get_json()


class TestRegistrationAndLogin:
    def test_role_defaults_to_customer(self, client):
        client.post("/register", json={"username": "nobody", "password": "pw123456"})
        body = client.post(
            "/login", json={"username": "nobody", "password": "pw123456"}
        ).get_json()
        assert body["role"] == "customer"

    def test_login_reports_role_and_username(self, client, auth):
        _, _, tokens = auth("keeper", role="shopkeeper")
        assert tokens["role"] == "shopkeeper"
        assert tokens["username"] == "keeper"
        assert tokens["is_admin"] is False

    def test_wrong_role_tab_is_rejected_with_a_clear_message(self, client, auth):
        auth("buyer", role="customer")
        response = client.post(
            "/login",
            json={"username": "buyer", "password": "pw123456", "role": "shopkeeper"},
        )
        assert response.status_code == 403
        assert "customer account" in response.get_json()["message"]

    def test_invalid_role_is_rejected(self, client):
        response = client.post(
            "/register",
            json={"username": "weird", "password": "pw123456", "role": "wizard"},
        )
        assert response.status_code == 422

    def test_me_reports_the_role(self, client, auth):
        headers, _, _ = auth("keeper", role="shopkeeper")
        assert client.get("/me", headers=headers).get_json()["role"] == "shopkeeper"

    def test_email_given_at_registration_is_saved(self, client):
        """UserRegisterSchema accepted an email and the endpoint dropped it,
        so every password account had a null email however the form was
        filled in."""
        assert client.post(
            "/register",
            json={
                "username": "mailed",
                "password": "pw123456",
                "email": "mailed@example.com",
            },
        ).status_code == 201

        tokens = client.post(
            "/login", json={"username": "mailed", "password": "pw123456"}
        ).get_json()
        me = client.get(
            "/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        ).get_json()
        assert me["email"] == "mailed@example.com"

    def test_registering_without_an_email_is_still_allowed(self, client):
        assert client.post(
            "/register", json={"username": "quiet", "password": "pw123456"}
        ).status_code == 201

    def test_blank_email_is_stored_as_null_not_empty_string(self, client):
        """An empty string would collide with every other blank account in the
        Google sign-in lookup, which matches on email."""
        client.post(
            "/register",
            json={"username": "blank", "password": "pw123456", "email": "   "},
        )
        tokens = client.post(
            "/login", json={"username": "blank", "password": "pw123456"}
        ).get_json()
        me = client.get(
            "/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        ).get_json()
        assert not me.get("email")


class TestAggregateRatings:
    def _review(self, client, delivered_buyer, owner, item, name, rating, comment=None):
        buyer, _, _ = delivered_buyer(item, name, owner)
        payload = {"rating": rating}
        if comment:
            payload["comment"] = comment
        assert client.post(
            f"/item/{item['id']}/review", json=payload, headers=buyer
        ).status_code == 201

    def test_average_is_a_float_not_an_integer(self, client, auth, delivered_buyer):
        owner, _, item = _shop_with_item(client, auth)
        for index, rating in enumerate((5, 4, 4)):
            self._review(client, delivered_buyer, owner, item, f"buyer{index}", rating)

        fetched = client.get(f"/item/{item['id']}", headers=owner).get_json()
        assert isinstance(fetched["average_rating"], float)
        assert fetched["average_rating"] == 4.33
        assert fetched["review_count"] == 3

    def test_unreviewed_item_reports_zero_not_null(self, client, auth):
        owner, _, item = _shop_with_item(client, auth)
        fetched = client.get(f"/item/{item['id']}", headers=owner).get_json()
        assert fetched["average_rating"] == 0.0
        assert fetched["review_count"] == 0

    def test_store_average_rolls_up_across_items(self, client, auth, delivered_buyer):
        owner, store, item = _shop_with_item(client, auth, item_name="First")
        second = client.post(
            "/item",
            json={"name": "Second", "price": 5.0, "store_id": store["id"]},
            headers=owner,
        ).get_json()

        self._review(client, delivered_buyer, owner, item, "buyer_one", 5)
        self._review(client, delivered_buyer, owner, second, "buyer_two", 2)

        fetched = client.get(f"/store/{store['id']}", headers=owner).get_json()
        assert fetched["average_rating"] == 3.5
        assert fetched["review_count"] == 2


class TestShopkeeperReviewView:
    def test_shopkeeper_sees_comments_average_and_breakdown(
        self, client, auth, delivered_buyer
    ):
        owner, store, item = _shop_with_item(client, auth)

        for index, (rating, comment) in enumerate(
            [(5, "Excellent"), (4, "Good"), (4, "Nice")]
        ):
            buyer, _, _ = delivered_buyer(item, f"buyer{index}", owner)
            client.post(
                f"/item/{item['id']}/review",
                json={"rating": rating, "comment": comment},
                headers=buyer,
            )

        summary = client.get(f"/store/{store['id']}/review", headers=owner).get_json()

        assert summary["average_rating"] == 4.33
        assert summary["review_count"] == 3
        assert summary["rating_breakdown"] == {"1": 0, "2": 0, "3": 0, "4": 2, "5": 1}

        comments = {review["comment"] for review in summary["reviews"]}
        assert comments == {"Excellent", "Good", "Nice"}

        assert all(review["username"] for review in summary["reviews"])
        assert all(review["item_name"] == "Widget" for review in summary["reviews"])

        assert summary["per_item"][0]["item_name"] == "Widget"
        assert summary["per_item"][0]["average_rating"] == 4.33

    def test_outsider_cannot_read_a_stores_reviews(self, client, auth):
        _, store, _ = _shop_with_item(client, auth)
        rival, _, _ = auth("rival", role="shopkeeper")
        assert client.get(
            f"/store/{store['id']}/review", headers=rival
        ).status_code == 403
