from marshmallow import Schema, fields, validate

from models.user import Role
from order_lifecycle import OrderStatus

PHONE_REGEX = r"^[6-9]\d{9}$"
PINCODE_REGEX = r"^[1-9]\d{5}$"


class PlainItemSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=80))
    price = fields.Float(required=True, validate=validate.Range(min=0))
    image_url = fields.Str(
        allow_none=True,
        validate=validate.Regexp(
            r"^https?://",
            error="image_url must start with http:// or https://",
        ),
    )
    is_hidden = fields.Bool(dump_only=True)
    stock_quantity = fields.Int(allow_none=True, validate=validate.Range(min=0))
    average_rating = fields.Function(
        lambda item: round(float(item.average_rating or 0), 2), dump_only=True
    )
    review_count = fields.Int(dump_only=True)


class PlainStoreSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=80))
    owner_id = fields.Int(dump_only=True)
    average_rating = fields.Function(
        lambda store: round(float(store.average_rating or 0), 2), dump_only=True
    )
    review_count = fields.Int(dump_only=True)


class PlainTagSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str()


class PlainReviewSchema(Schema):
    id = fields.Int(dump_only=True)
    rating = fields.Int(required=True, validate=validate.Range(min=1, max=5))
    comment = fields.Str(allow_none=True, validate=validate.Length(max=500))
    created_at = fields.DateTime(dump_only=True)


class ReviewSchema(PlainReviewSchema):
    """Defined ahead of ItemSchema because items embed reviews in this shape.

    `user_id` is what makes that embedding useful: without it the console
    could not tell its own reviews apart from anyone else's, and had to
    re-fetch /item/<id>/review once per item on every page load.
    """

    item_id = fields.Int(dump_only=True)
    user_id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True, attribute="user.username")


class PlainWorkerSchema(Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True)


class ItemUpdateSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=80))
    price = fields.Float(validate=validate.Range(min=0))
    image_url = fields.Str(
        allow_none=True,
        validate=validate.Regexp(
            r"^https?://",
            error="image_url must start with http:// or https://",
        ),
    )
    stock_quantity = fields.Int(allow_none=True, validate=validate.Range(min=0))


class ItemSchema(PlainItemSchema):
    store_id = fields.Int(required=True, load_only=True)
    store = fields.Nested(PlainStoreSchema(), dump_only=True)
    tags = fields.List(fields.Nested(PlainTagSchema()), dump_only=True)
    reviews = fields.List(fields.Nested(ReviewSchema()), dump_only=True)


class StoreSchema(PlainStoreSchema):
    items = fields.List(fields.Nested(PlainItemSchema()), dump_only=True)
    tags = fields.List(fields.Nested(PlainTagSchema()), dump_only=True)
    workers = fields.List(fields.Nested(PlainWorkerSchema()), dump_only=True)


class TagSchema(PlainTagSchema):
    store_id = fields.Int(load_only=True)
    store = fields.Nested(PlainStoreSchema(), dump_only=True)
    items = fields.List(fields.Nested(PlainItemSchema()), dump_only=True)


class TagAndItemSchema(Schema):
    message = fields.Str()
    item = fields.Nested(ItemSchema)
    tag = fields.Nested(TagSchema)


class StoreReviewSchema(PlainReviewSchema):
    """A review as the shopkeeper sees it: which item, who wrote it, comment."""

    item_id = fields.Int(dump_only=True)
    item_name = fields.Str(dump_only=True, attribute="item.name")
    user_id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True, attribute="user.username")


class StoreReviewSummarySchema(Schema):
    """Everything a shopkeeper needs about their store's feedback."""

    store_id = fields.Int(dump_only=True)
    store_name = fields.Str(dump_only=True)
    average_rating = fields.Float(dump_only=True)
    review_count = fields.Int(dump_only=True)
    rating_breakdown = fields.Dict(
        keys=fields.Str(), values=fields.Int(), dump_only=True
    )
    per_item = fields.List(fields.Dict(), dump_only=True)
    reviews = fields.List(fields.Nested(StoreReviewSchema()), dump_only=True)


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    public_ref = fields.Str(dump_only=True)
    username = fields.Str(required=True, validate=validate.Length(min=3, max=80))
    password = fields.Str(required=True, load_only=True, validate=validate.Length(min=8))
    email = fields.Str()
    role = fields.Str(dump_only=True)


class UserRegisterSchema(UserSchema):
    """Registration picks a side of the marketplace and cannot be changed later."""

    role = fields.Str(
        load_default=Role.CUSTOMER,
        validate=validate.OneOf(Role.ALL),
    )


class LoginSchema(Schema):
    username = fields.Str(required=True)
    password = fields.Str(required=True, load_only=True)
    role = fields.Str(load_default=None, allow_none=True, validate=validate.OneOf(Role.ALL))


class UserAdminSchema(Schema):
    """Extended view used only in admin endpoints (list, single-user detail)."""
    id = fields.Int(dump_only=True)
    public_ref = fields.Str(dump_only=True)
    username = fields.Str(dump_only=True)
    email = fields.Str(dump_only=True)
    role = fields.Str(dump_only=True)
    is_admin = fields.Bool(dump_only=True)
    is_banned = fields.Bool(dump_only=True)
    google_id = fields.Str(dump_only=True)
    stores = fields.List(fields.Nested(PlainStoreSchema()), dump_only=True)


class GoogleLoginSchema(Schema):
    credential = fields.Str(required=True)
    role = fields.Str(load_default=Role.CUSTOMER, validate=validate.OneOf(Role.ALL))


class AddWorkerSchema(Schema):
    username = fields.Str(required=True)


class UserProfileSchema(Schema):
    """Read/write shape for GET and PUT /me/profile.

    Regex validation mirrors static/validation.js — belt and suspenders: the
    client rejects bad input before a round trip, the server rejects it
    regardless of what actually sent the request.
    """

    address_line1 = fields.Str(
        allow_none=True, load_default=None, validate=validate.Length(max=150)
    )
    address_line2 = fields.Str(
        allow_none=True, load_default=None, validate=validate.Length(max=150)
    )
    city = fields.Str(allow_none=True, load_default=None, validate=validate.Length(max=80))
    state = fields.Str(allow_none=True, load_default=None, validate=validate.Length(max=80))
    pincode = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Regexp(PINCODE_REGEX, error="Enter a valid 6-digit PIN code."),
    )
    phone = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Regexp(PHONE_REGEX, error="Enter a valid 10-digit mobile number."),
    )
    formatted_address = fields.Str(dump_only=True)
    is_complete = fields.Bool(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class ActivityLogSchema(Schema):
    id = fields.Int(dump_only=True)
    user_id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True)
    action = fields.Str(dump_only=True)
    details = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class PlaceOrderSchema(Schema):
    quantity = fields.Int(load_default=1, validate=validate.Range(min=1, max=1000))
    delivery_address = fields.Str(
        load_default=None, allow_none=True, validate=validate.Length(max=300)
    )
    contact_phone = fields.Str(
        load_default=None, allow_none=True, validate=validate.Length(max=20)
    )


class OrderTransitionSchema(Schema):
    status = fields.Str(required=True, validate=validate.OneOf(OrderStatus.ALL))


class OrderSchema(Schema):
    id = fields.Int(dump_only=True)
    reference = fields.Str(dump_only=True)
    user_id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True, attribute="user.username")
    item_id = fields.Int(dump_only=True)
    item = fields.Nested(PlainItemSchema(), dump_only=True)
    store_id = fields.Int(dump_only=True)
    store_name = fields.Str(dump_only=True, attribute="store.name")
    quantity = fields.Int(dump_only=True)
    unit_price = fields.Function(
        lambda order: None if order.unit_price is None else round(float(order.unit_price), 2),
        dump_only=True,
    )
    total = fields.Float(dump_only=True)
    status = fields.Str(dump_only=True)
    delivery_address = fields.Str(dump_only=True)
    contact_phone = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    allowed_next = fields.Method("get_allowed_next", dump_only=True)

    def get_allowed_next(self, order):
        from order_lifecycle import allowed_next

        return allowed_next(order.status)