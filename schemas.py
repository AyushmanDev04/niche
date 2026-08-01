from marshmallow import Schema, fields


class PlainItemSchema(Schema):
    id = fields.Str(dump_only=True)
    name = fields.Str(required=True)
    price = fields.Float(required=True)
    image_url = fields.Str()
    is_hidden = fields.Bool(dump_only=True)


class PlainStoreSchema(Schema):
    id = fields.Str(dump_only=True)
    name = fields.Str(required=True)
    owner_id = fields.Int(dump_only=True)


class PlainTagSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str()


class PlainReviewSchema(Schema):
    id = fields.Int(dump_only=True)
    rating = fields.Int(required=True)
    comment = fields.Str()
    created_at = fields.DateTime(dump_only=True)


class PlainWorkerSchema(Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True)


class ItemUpdateSchema(Schema):
    name = fields.Str()
    price = fields.Float()
    image_url = fields.Str()
    store_id = fields.Int()


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


class ReviewSchema(PlainReviewSchema):
    item_id = fields.Int(load_only=True)
    user_id = fields.Int(dump_only=True)


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    username = fields.Str(required=True)
    password = fields.Str(required=True, load_only=True)
    email = fields.Str()


class UserAdminSchema(Schema):
    """Extended view used only in admin endpoints (list, single-user detail)."""
    id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True)
    email = fields.Str(dump_only=True)
    is_admin = fields.Bool(dump_only=True)
    is_banned = fields.Bool(dump_only=True)
    google_id = fields.Str(dump_only=True)
    stores = fields.List(fields.Nested(PlainStoreSchema()), dump_only=True)


class GoogleLoginSchema(Schema):
    credential = fields.Str(required=True)


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
    quantity = fields.Int(load_default=1)


class OrderSchema(Schema):
    id = fields.Int(dump_only=True)
    user_id = fields.Int(dump_only=True)
    username = fields.Str(dump_only=True, attribute="user.username")
    item_id = fields.Int(dump_only=True)
    item = fields.Nested(PlainItemSchema(), dump_only=True)
    store_id = fields.Int(dump_only=True)
    quantity = fields.Int(dump_only=True)
    status = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)