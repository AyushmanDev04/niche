"""Regression tests for the vulnerabilities and authorization gaps fixed here.

Each test names the specific behaviour that was previously wrong.
"""

import pytest


class TestStaticExposure:
    def test_dotenv_is_not_served(self, client):
        """static_folder="." used to serve /.env, /data.db and /app.py."""
        for path in ("/.env", "/data.db", "/app.py", "/requirements.txt", "/.flaskenv"):
            assert client.get(path).status_code == 404, f"{path} is reachable"

    def test_frontend_still_served(self, client):
        assert client.get("/").status_code == 200
        assert client.get("/app.js").status_code == 200


class TestSecretConfig:
    def test_refuses_to_boot_without_jwt_secret(self, monkeypatch):
        """There used to be a hardcoded fallback secret."""
        import app as app_module

        monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="JWT_SECRET_KEY"):
            app_module.create_app()


class TestMakeAdminBackdoor:
    def test_endpoint_is_gone(self, client):
        response = client.post("/make-admin/someone")
        assert response.status_code in (404, 405)


class TestTagAuthorization:
    """Every tag endpoint was previously unauthenticated beyond a valid JWT."""

    def _store_owned_by_other(self, client, auth):
        owner_headers, _, _ = auth("owner", role="shopkeeper")
        store = client.post(
            "/store", json={"name": "Owned"}, headers=owner_headers
        ).get_json()
        return store, owner_headers

    def test_outsider_cannot_create_tag(self, client, auth):
        store, _ = self._store_owned_by_other(client, auth)
        outsider, _, _ = auth("outsider", role="shopkeeper")
        response = client.post(
            f"/store/{store['id']}/tag", json={"name": "sale"}, headers=outsider
        )
        assert response.status_code == 403

    def test_outsider_cannot_delete_tag(self, client, auth):
        store, owner = self._store_owned_by_other(client, auth)
        tag = client.post(
            f"/store/{store['id']}/tag", json={"name": "sale"}, headers=owner
        ).get_json()
        outsider, _, _ = auth("outsider", role="shopkeeper")
        assert client.delete(f"/tag/{tag['id']}", headers=outsider).status_code == 403

    def test_tag_cannot_cross_store_boundary(self, client, auth):
        owner, _, _ = auth("owner", role="shopkeeper")
        store_a = client.post("/store", json={"name": "A"}, headers=owner).get_json()
        store_b = client.post("/store", json={"name": "B"}, headers=owner).get_json()
        tag_a = client.post(
            f"/store/{store_a['id']}/tag", json={"name": "sale"}, headers=owner
        ).get_json()
        item_b = client.post(
            "/item",
            json={"name": "Widget", "price": 1.0, "store_id": store_b["id"]},
            headers=owner,
        ).get_json()

        response = client.post(
            f"/item/{item_b['id']}/tag/{tag_a['id']}", headers=owner
        )
        assert response.status_code == 400


class TestLogoutPersistence:
    def test_token_is_rejected_after_logout(self, client, auth):
        headers, _, _ = auth("someone")
        assert client.get("/store", headers=headers).status_code == 200

        assert client.post("/logout", headers=headers).status_code == 200

        assert client.get("/store", headers=headers).status_code == 401


class TestAnonymousBrowsing:
    """The catalogue is public. GET /item and GET /store returned 401 to
    signed-out visitors, so the shop could not be seen before registering —
    while GET /item/<id>/review was already public."""

    def test_item_list_is_public(self, client, auth):
        owner, _, _ = auth("keeper", role="shopkeeper")
        store = client.post("/store", json={"name": "Shop"}, headers=owner).get_json()
        client.post(
            "/item",
            json={"name": "Widget", "price": 9.99, "store_id": store["id"]},
            headers=owner,
        )

        response = client.get("/item")
        assert response.status_code == 200
        assert [item["name"] for item in response.get_json()] == ["Widget"]

    def test_store_list_and_detail_are_public(self, client, auth):
        owner, _, _ = auth("keeper", role="shopkeeper")
        store = client.post("/store", json={"name": "Shop"}, headers=owner).get_json()

        assert client.get("/store").status_code == 200
        assert client.get(f"/store/{store['id']}").status_code == 200

    def test_item_detail_is_public(self, client, auth):
        owner, _, _ = auth("keeper", role="shopkeeper")
        store = client.post("/store", json={"name": "Shop"}, headers=owner).get_json()
        item = client.post(
            "/item",
            json={"name": "Widget", "price": 9.99, "store_id": store["id"]},
            headers=owner,
        ).get_json()

        assert client.get(f"/item/{item['id']}").status_code == 200

    def test_hidden_items_stay_hidden_from_anonymous_visitors(self, client, auth):
        """Opening the catalogue up must not open up what staff hid."""
        owner, _, _ = auth("keeper", role="shopkeeper")
        store = client.post("/store", json={"name": "Shop"}, headers=owner).get_json()
        item = client.post(
            "/item",
            json={"name": "Secret", "price": 9.99, "store_id": store["id"]},
            headers=owner,
        ).get_json()
        assert client.post(f"/item/{item['id']}/hide", headers=owner).status_code == 200

        assert client.get(f"/item/{item['id']}").status_code == 404
        assert client.get("/item").get_json() == []

    def test_writing_still_requires_a_token(self, client, auth):
        """Only the reads became public."""
        owner, _, _ = auth("keeper", role="shopkeeper")
        store = client.post("/store", json={"name": "Shop"}, headers=owner).get_json()

        assert client.post("/store", json={"name": "Anon"}).status_code == 401
        assert client.post(
            "/item", json={"name": "Anon", "price": 1.0, "store_id": store["id"]}
        ).status_code == 401


class TestActivityFeedLimit:
    def test_negative_limit_does_not_reach_the_query(self, client, auth):
        """?limit=-1 was passed straight to .limit(), which PostgreSQL rejects
        outright. Clamped to 0, it is an empty page rather than an error."""
        admin, _, _ = auth("admin", admin=True)

        response = client.get("/activity?limit=-1", headers=admin)
        assert response.status_code == 200
        assert response.get_json() == []

    def test_limit_is_capped_and_honoured(self, client, auth):
        admin, _, _ = auth("admin", admin=True)
        for index in range(3):
            auth(f"extra{index}")

        assert len(client.get("/activity?limit=2", headers=admin).get_json()) == 2
        assert client.get("/activity?limit=99999", headers=admin).status_code == 200


class TestPrivilegeSeparation:
    def test_non_admin_cannot_list_users(self, client, auth):
        headers, _, _ = auth("normal")
        assert client.get("/users", headers=headers).status_code == 403

    def test_user_cannot_read_another_users_record(self, client, auth):
        _, victim_id, _ = auth("victim")
        attacker, _, _ = auth("attacker")
        assert client.get(f"/user/{victim_id}", headers=attacker).status_code == 403

    def test_user_can_read_own_record(self, client, auth):
        headers, user_id, _ = auth("self")
        assert client.get(f"/user/{user_id}", headers=headers).status_code == 200
