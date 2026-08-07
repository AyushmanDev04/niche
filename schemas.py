from marshmallow import Schema, fields, validate

from models.user import Role


class PlainItemSchema(Schema):
    # Int, not Str: every other schema dumps ids as numbers, and the mismatch
    # meant the frontend's `review.item_id === item.id` comparison was always
    # false, so item ratings never rendered.
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
    # Mean of every rating on this item, as a float (0.0 when unreviewed).
    average_rating = fields.Function(
        lambda item: round(float(item.average_rating or 0), 2), dump_only=True
    )
    review_count = fields.Int(dump_only=True)


class PlainStoreSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=80))
    owner_id = fields.Int(dump_only=True)
    # Rolled up across every item in the store.
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
    # store_id is deliberately absent: moving an item between stores needs a
    # permission check against *both* stores, so it is not part of a plain edit.


class ItemSchema(PlainItemSchema):
    store_id = fields.Int(required=True, load_only=True)
    store = fields.Nested(PlainStoreSchema(), dump_only=True)
    tags = fields.List(fields.Nested(PlainTagSchema()), dump_only=True)
    reviews = fields.List(fields.Nested(PlainReviewSchema()), dump_only=True)


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
    # How many reviews sit at each star value, 1..5.
    rating_breakdown = fields.Dict(
        keys=fields.Str(), values=fields.Int(), dump_only=True
    )
    per_item = fields.List(fields.Dict(), dump_only=True)
    reviews = fields.List(fields.Nested(StoreReviewSchema()), dump_only=True)


class ReviewSchema(PlainReviewSchema):
    # item_id is dumped as well as loaded: the frontend groups reviews by item,
    # and while this was load_only it had to reconstruct the association from
    # array positions.
    item_id = fields.Int(dump_only=True)
    user_id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True, attribute="user.username")


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
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
    # Optional: when the login form's role tab is submitted, the server checks
    # the account actually is that role and fails clearly if not.
    role = fields.Str(load_default=None, allow_none=True, validate=validate.OneOf(Role.ALL))


class UserAdminSchema(Schema):
    """Extended view used only in admin endpoints (list, single-user detail)."""
    id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True)
    email = fields.Str(dump_only=True)
    role = fields.Str(dump_only=True)
    is_admin = fields.Bool(dump_only=True)
    is_banned = fields.Bool(dump_only=True)
    google_id = fields.Str(dump_only=True)
    stores = fields.List(fields.Nested(PlainStoreSchema()), dump_only=True)


class GoogleLoginSchema(Schema):
    credential = fields.Str(required=True)
    # Only applied when the Google account is signing up for the first time;
    # an existing account keeps whichever role it already has.
    role = fields.Str(load_default=Role.CUSTOMER, validate=validate.OneOf(Role.ALL))


class AddWorkerSchema(Schema):
    username = fields.Str(required=True)


class ActivityLogSchema(Schema):
    id = fields.Int(dump_only=True)
    user_id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True)
    action = fields.Str(dump_only=True)
    details = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class PlaceOrderSchema(Schema):
    # Without the range check, negative quantities were accepted.
    quantity = fields.Int(load_default=1, validate=validate.Range(min=1, max=1000))
    # A local shop cannot deliver without these. Optional at the API level so
    # existing integrations keep working, but the checkout form requires them.
    delivery_address = fields.Str(
        load_default=None, allow_none=True, validate=validate.Length(max=300)
    )
    contact_phone = fields.Str(
        load_default=None, allow_none=True, validate=validate.Length(max=20)
    )


class OrderSchema(Schema):
    id = fields.Int(dump_only=True)
    # Quotable order number for receipts and support ("ORD-00042").
    reference = fields.Str(dump_only=True)
    user_id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True, attribute="user.username")
    item_id = fields.Int(dump_only=True)
    item = fields.Nested(PlainItemSchema(), dump_only=True)
    store_id = fields.Int(dump_only=True)
    store_name = fields.Str(dump_only=True, attribute="store.name")
    quantity = fields.Int(dump_only=True)
    # Price paid per unit, frozen at checkout — not the item's current price.
    unit_price = fields.Function(
        lambda order: None if order.unit_price is None else round(float(order.unit_price), 2),
        dump_only=True,
    )
    total = fields.Float(dump_only=True)
    status = fields.Str(dump_only=True)
    delivery_address = fields.Str(dump_only=True)
    contact_phone = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)