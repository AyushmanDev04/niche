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

    def test_customer_can_review(self, client, auth):
        _, _, item = _shop_with_item(client, auth)
        buyer, _, _ = auth("buyer", role="customer")
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


class TestAggregateRatings:
    def _review(self, client, auth, item, name, rating, comment=None):
        buyer, _, _ = auth(name, role="customer")
        payload = {"rating": rating}
        if comment:
            payload["comment"] = comment
        assert client.post(
            f"/item/{item['id']}/review", json=payload, headers=buyer
        ).status_code == 201

    def test_average_is_a_float_not_an_integer(self, client, auth):
        owner, _, item = _shop_with_item(client, auth)
        # 5, 4, 4 -> 4.333... which must not be truncated to 4.
        for index, rating in enumerate((5, 4, 4)):
            self._review(client, auth, item, f"buyer{index}", rating)

        fetched = client.get(f"/item/{item['id']}", headers=owner).get_json()
        assert isinstance(fetched["average_rating"], float)
        assert fetched["average_rating"] == 4.33
        assert fetched["review_count"] == 3

    def test_unreviewed_item_reports_zero_not_null(self, client, auth):
        owner, _, item = _shop_with_item(client, auth)
        fetched = client.get(f"/item/{item['id']}", headers=owner).get_json()
        assert fetched["average_rating"] == 0.0
        assert fetched["review_count"] == 0

    def test_store_average_rolls_up_across_items(self, client, auth):
        owner, store, item = _shop_with_item(client, auth, item_name="First")
        second = client.post(
            "/item",
            json={"name": "Second", "price": 5.0, "store_id": store["id"]},
            headers=owner,
        ).get_json()

        self._review(client, auth, item, "buyer_one", 5)
        self._review(client, auth, second, "buyer_two", 2)

        fetched = client.get(f"/store/{store['id']}", headers=owner).get_json()
        assert fetched["average_rating"] == 3.5
        assert fetched["review_count"] == 2


class TestShopkeeperReviewView:
    def test_shopkeeper_sees_comments_average_and_breakdown(self, client, auth):
        owner, store, item = _shop_with_item(client, auth)

        for index, (rating, comment) in enumerate(
            [(5, "Excellent"), (4, "Good"), (4, "Nice")]
        ):
            buyer, _, _ = auth(f"buyer{index}", role="customer")
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

        # Each review names its author and item for the shopkeeper.
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
