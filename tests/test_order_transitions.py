"""The /order/<id>/transition endpoint: permission + state-machine
enforcement wired to real accounts, not just order_lifecycle.py in isolation."""


def _placed_order(client, auth):
    owner, _, _ = auth("keeper", role="shopkeeper")
    store = client.post("/store", json={"name": "Shop"}, headers=owner).get_json()
    item = client.post(
        "/item", json={"name": "Widget", "price": 10.0, "store_id": store["id"]}, headers=owner
    ).get_json()
    buyer, _, _ = auth("buyer", role="customer")
    order = client.post(
        f"/item/{item['id']}/order", json={"quantity": 1}, headers=buyer
    ).get_json()
    return owner, buyer, order


class TestFullLifecycle:
    def test_shop_walks_an_order_to_completion(self, client, auth):
        owner, _, order = _placed_order(client, auth)
        oid = order["id"]

        for target in ("accepted", "packed", "out_for_delivery", "completed"):
            response = client.post(
                f"/order/{oid}/transition", json={"status": target}, headers=owner
            )
            assert response.status_code == 200, response.get_json()
            assert response.get_json()["status"] == target

    def test_allowed_next_reflects_current_state(self, client, auth):
        _, _, order = _placed_order(client, auth)
        assert set(order["allowed_next"].keys()) == {"accepted", "cancelled"}


class TestPermissions:
    def test_customer_cannot_accept_their_own_order(self, client, auth):
        _, buyer, order = _placed_order(client, auth)
        response = client.post(
            f"/order/{order['id']}/transition", json={"status": "accepted"}, headers=buyer
        )
        assert response.status_code == 400
        assert "Only the shop" in response.get_json()["message"]

    def test_customer_can_cancel_while_pending(self, client, auth):
        _, buyer, order = _placed_order(client, auth)
        response = client.post(
            f"/order/{order['id']}/transition", json={"status": "cancelled"}, headers=buyer
        )
        assert response.status_code == 200

    def test_customer_cannot_cancel_once_shop_has_accepted(self, client, auth):
        owner, buyer, order = _placed_order(client, auth)
        client.post(f"/order/{order['id']}/transition", json={"status": "accepted"}, headers=owner)

        response = client.post(
            f"/order/{order['id']}/transition", json={"status": "cancelled"}, headers=buyer
        )
        assert response.status_code == 400

    def test_stranger_cannot_touch_the_order(self, client, auth):
        _, _, order = _placed_order(client, auth)
        stranger, _, _ = auth("stranger", role="customer")
        response = client.post(
            f"/order/{order['id']}/transition", json={"status": "cancelled"}, headers=stranger
        )
        assert response.status_code == 403

    def test_admin_can_act_as_the_shop(self, client, auth):
        _, _, order = _placed_order(client, auth)
        admin, _, _ = auth("boss", admin=True, role="shopkeeper")
        response = client.post(
            f"/order/{order['id']}/transition", json={"status": "accepted"}, headers=admin
        )
        assert response.status_code == 200


class TestIllegalMoves:
    def test_cannot_skip_from_pending_to_packed(self, client, auth):
        owner, _, order = _placed_order(client, auth)
        response = client.post(
            f"/order/{order['id']}/transition", json={"status": "packed"}, headers=owner
        )
        assert response.status_code == 400

    def test_cannot_move_a_cancelled_order(self, client, auth):
        owner, buyer, order = _placed_order(client, auth)
        client.post(f"/order/{order['id']}/transition", json={"status": "cancelled"}, headers=buyer)

        response = client.post(
            f"/order/{order['id']}/transition", json={"status": "accepted"}, headers=owner
        )
        assert response.status_code == 400
        assert "already cancelled" in response.get_json()["message"].lower()

    def test_unrecognised_status_is_rejected_by_the_schema(self, client, auth):
        owner, _, order = _placed_order(client, auth)
        response = client.post(
            f"/order/{order['id']}/transition", json={"status": "teleported"}, headers=owner
        )
        assert response.status_code == 422


class TestOldEndpointsAreGone:
    """/fulfill and /cancel were replaced by /transition — five states need
    one authoritative table, not scattered near-duplicate route handlers."""

    def test_fulfill_endpoint_no_longer_exists(self, client, auth):
        owner, _, order = _placed_order(client, auth)
        response = client.post(f"/order/{order['id']}/fulfill", headers=owner)
        assert response.status_code in (404, 405)

    def test_old_cancel_endpoint_no_longer_exists(self, client, auth):
        _, buyer, order = _placed_order(client, auth)
        response = client.post(f"/order/{order['id']}/cancel", headers=buyer)
        assert response.status_code in (404, 405)
