"""Real concurrent checkouts racing for the same limited stock.

This is the actual proof for the `SELECT ... FOR UPDATE` claim — everything
in test_inventory.py exercises the *logic* with one request at a time, which
would pass even with no locking at all. This file is the one that would fail
if the lock were removed or replaced with a plain SELECT.

Skipped outside Postgres: SQLite has no real row-level locking (with_for_
update() is accepted but does nothing), so this test would be meaningless —
it could only prove Python's GIL serialised the threads, not that the
database did. Run it with:

    TEST_DATABASE_URL=postgresql://postgres:pw@localhost:55432/nichesuite \
        pytest tests/test_concurrency.py -q
"""

import os
import threading

import pytest

pytestmark = pytest.mark.skipif(
    not (os.environ.get("TEST_DATABASE_URL") or "").startswith("postgresql"),
    reason="row locking is meaningless on SQLite — run with TEST_DATABASE_URL set to Postgres",
)


def _setup_limited_stock_item(client, auth, stock):
    owner, _, _ = auth("keeper", role="shopkeeper")
    store = client.post("/store", json={"name": "Shop"}, headers=owner).get_json()
    item = client.post(
        "/item",
        json={"name": "LimitedWidget", "price": 10.0, "store_id": store["id"], "stock_quantity": stock},
        headers=owner,
    ).get_json()
    return owner, item


class TestOversellPrevention:
    def test_only_stock_quantity_orders_succeed_under_concurrent_load(self, client, auth):
        """20 customers simultaneously try to buy the last 5 units. Exactly 5
        succeed, the other 15 are told there's not enough stock, and the item
        never goes negative — the whole point of taking the lock."""
        stock = 5
        concurrency = 20
        _, item = _setup_limited_stock_item(client, auth, stock=stock)

        tokens = [auth(f"racer{i}", role="customer")[0] for i in range(concurrency)]

        results = [None] * concurrency

        def buy(index):
            response = client.post(
                f"/item/{item['id']}/order",
                json={"quantity": 1},
                headers=tokens[index],
            )
            results[index] = response.status_code

        threads = [threading.Thread(target=buy, args=(i,)) for i in range(concurrency)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        succeeded = results.count(201)
        rejected = results.count(409)

        assert succeeded == stock, f"expected exactly {stock} orders to succeed, got {succeeded} (results={results})"
        assert rejected == concurrency - stock
        assert None not in results, "a thread did not finish within the timeout"

        final = client.get(f"/item/{item['id']}", headers=tokens[0]).get_json()
        assert final["stock_quantity"] == 0, "stock must never go negative or under-decrement"

    def test_single_unit_race_exactly_one_winner(self, client, auth):
        """The sharpest version of the race: two customers, one unit."""
        _, item = _setup_limited_stock_item(client, auth, stock=1)
        token_a, _, _ = auth("racer_a", role="customer")
        token_b, _, _ = auth("racer_b", role="customer")

        results = {}

        def buy(name, token):
            results[name] = client.post(
                f"/item/{item['id']}/order", json={"quantity": 1}, headers=token
            ).status_code

        t1 = threading.Thread(target=buy, args=("a", token_a))
        t2 = threading.Thread(target=buy, args=("b", token_b))
        t1.start()
        t2.start()
        t1.join(timeout=15)
        t2.join(timeout=15)

        outcomes = sorted(results.values())
        assert outcomes == [201, 409], f"expected exactly one winner, got {results}"
