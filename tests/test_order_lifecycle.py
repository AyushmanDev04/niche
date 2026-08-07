"""The state machine in isolation — no Flask, no database, pure transition logic."""

import pytest

from order_lifecycle import OrderStatus, TransitionError, assert_transition, allowed_next


class TestHappyPath:
    def test_full_lifecycle_shop_side(self):
        """A shop can walk an order through every stage in order."""
        path = [
            (OrderStatus.PENDING, OrderStatus.ACCEPTED),
            (OrderStatus.ACCEPTED, OrderStatus.PACKED),
            (OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY),
            (OrderStatus.OUT_FOR_DELIVERY, OrderStatus.COMPLETED),
        ]
        for current, target in path:
            assert_transition(current, target, actor="shop")  # must not raise

    def test_customer_can_cancel_while_pending(self):
        assert_transition(OrderStatus.PENDING, OrderStatus.CANCELLED, actor="customer")

    def test_shop_can_cancel_at_any_non_terminal_stage(self):
        for status in (OrderStatus.PENDING, OrderStatus.ACCEPTED, OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY):
            assert_transition(status, OrderStatus.CANCELLED, actor="shop")


class TestForbiddenMoves:
    def test_customer_cannot_accept_their_own_order(self):
        with pytest.raises(TransitionError, match="Only the shop"):
            assert_transition(OrderStatus.PENDING, OrderStatus.ACCEPTED, actor="customer")

    def test_customer_cannot_cancel_once_accepted(self):
        """Stock is reserved and prep may be underway; only the shop backs out now."""
        with pytest.raises(TransitionError, match="Only the shop"):
            assert_transition(OrderStatus.ACCEPTED, OrderStatus.CANCELLED, actor="customer")

    def test_cannot_skip_stages(self):
        with pytest.raises(TransitionError):
            assert_transition(OrderStatus.PENDING, OrderStatus.PACKED, actor="shop")
        with pytest.raises(TransitionError):
            assert_transition(OrderStatus.PENDING, OrderStatus.COMPLETED, actor="shop")

    def test_cannot_go_backwards(self):
        with pytest.raises(TransitionError):
            assert_transition(OrderStatus.PACKED, OrderStatus.ACCEPTED, actor="shop")

    @pytest.mark.parametrize("terminal", OrderStatus.TERMINAL)
    def test_nothing_leaves_a_terminal_state(self, terminal):
        for target in OrderStatus.ALL:
            with pytest.raises(TransitionError):
                assert_transition(terminal, target, actor="shop")

    def test_unknown_target_status_is_rejected(self):
        with pytest.raises(TransitionError, match="not a valid order status"):
            assert_transition(OrderStatus.PENDING, "teleported", actor="shop")


class TestAllowedNext:
    def test_lists_options_with_their_actor(self):
        assert allowed_next(OrderStatus.PENDING) == {
            OrderStatus.ACCEPTED: "shop",
            OrderStatus.CANCELLED: "either",
        }

    def test_terminal_states_have_no_options(self):
        assert allowed_next(OrderStatus.COMPLETED) == {}
        assert allowed_next(OrderStatus.CANCELLED) == {}
