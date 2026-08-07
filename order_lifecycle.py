"""The order state machine.

Centralising the transition table here — instead of scattering `if status ==
"pending"` checks across five route handlers — makes the lifecycle auditable
in one place and means the frontend, the API, and any future admin tool all
answer "what can happen next?" the same way.
"""


class OrderStatus:
    PENDING = "pending"
    ACCEPTED = "accepted"
    PACKED = "packed"
    OUT_FOR_DELIVERY = "out_for_delivery"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

    ALL = (PENDING, ACCEPTED, PACKED, OUT_FOR_DELIVERY, COMPLETED, CANCELLED)
    TERMINAL = (COMPLETED, CANCELLED)

    LABELS = {
        PENDING: "Pending",
        ACCEPTED: "Accepted",
        PACKED: "Packed",
        OUT_FOR_DELIVERY: "Out for delivery",
        COMPLETED: "Completed",
        CANCELLED: "Cancelled",
    }


class TransitionError(ValueError):
    """Raised for any attempted move the state machine does not allow."""


_TRANSITIONS = {
    OrderStatus.PENDING: {
        OrderStatus.ACCEPTED: "shop",
        OrderStatus.CANCELLED: "either",
    },
    OrderStatus.ACCEPTED: {
        OrderStatus.PACKED: "shop",
        OrderStatus.CANCELLED: "shop",
    },
    OrderStatus.PACKED: {
        OrderStatus.OUT_FOR_DELIVERY: "shop",
        OrderStatus.CANCELLED: "shop",
    },
    OrderStatus.OUT_FOR_DELIVERY: {
        OrderStatus.COMPLETED: "shop",
        OrderStatus.CANCELLED: "shop",
    },
    OrderStatus.COMPLETED: {},
    OrderStatus.CANCELLED: {},
}


def allowed_next(current_status):
    """{target_status: actor} for every legal move from `current_status`."""
    return dict(_TRANSITIONS.get(current_status, {}))


def assert_transition(current_status, target_status, actor):
    """Raise TransitionError unless this exact move, by this actor, is legal.

    `actor` is "shop" or "customer" — the caller has already resolved which
    one the requester is (see resources/order.py).
    """
    if target_status not in OrderStatus.ALL:
        raise TransitionError(f"'{target_status}' is not a valid order status.")

    options = _TRANSITIONS.get(current_status, {})
    if target_status not in options:
        if current_status in OrderStatus.TERMINAL:
            raise TransitionError(
                f"This order is already {OrderStatus.LABELS[current_status].lower()} "
                "and cannot be changed further."
            )
        raise TransitionError(
            f"Cannot move an order from '{current_status}' to '{target_status}'."
        )

    required = options[target_status]
    if required != "either" and required != actor:
        who = "the shop" if required == "shop" else "the customer"
        raise TransitionError(f"Only {who} can make this change.")
