from flask.views import MethodView
from flask_smorest import Blueprint, abort
from flask_jwt_extended import jwt_required
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from db import db
from models import TagModel, StoreModel, ItemModel
from schemas import TagSchema, TagAndItemSchema
from resources.permissions import can_manage_store, can_work_store
from activity_log import log_activity

blp = Blueprint("Tags", "tags", description="Operations on tags")


@blp.route("/store/<int:store_id>/tag")
class TagsInStore(MethodView):
    @jwt_required()
    @blp.response(200, TagSchema(many=True))
    def get(self, store_id):
        store = StoreModel.query.get_or_404(store_id)
        return store.tags.all()

    @jwt_required()
    @blp.arguments(TagSchema)
    @blp.response(201, TagSchema)
    def post(self, tag_data, store_id):
        store = StoreModel.query.get_or_404(store_id)
        if not can_work_store(store):
            abort(403, message="You do not have permission to add tags to this store.")

        # store_id comes from the URL; ignore any value in the body so a caller
        # cannot create a tag against a store they just passed the check for.
        tag_data.pop("store_id", None)
        tag = TagModel(**tag_data, store_id=store_id)

        try:
            db.session.add(tag)
            db.session.flush()
            log_activity("create_tag", details=f"tag '{tag.name}' in store id={store_id}")
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, message="This store already has a tag with that name.")
        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred while inserting the tag.")

        return tag


@blp.route("/item/<int:item_id>/tag/<int:tag_id>")
class LinkTagsToItem(MethodView):
    @jwt_required()
    @blp.response(201, TagAndItemSchema)
    def post(self, item_id, tag_id):
        item = ItemModel.query.get_or_404(item_id)
        tag = TagModel.query.get_or_404(tag_id)

        if not can_work_store(item.store):
            abort(403, message="You do not have permission to tag this item.")

        # A tag belongs to one store; linking it to another store's item would
        # leak that store's taxonomy and let tags cross tenant boundaries.
        if tag.store_id != item.store_id:
            abort(400, message="Tag and item must belong to the same store.")

        if tag in item.tags:
            abort(409, message="This item already has that tag.")

        item.tags.append(tag)

        try:
            db.session.add(item)
            log_activity("link_tag", details=f"linked tag '{tag.name}' to item '{item.name}'")
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred while linking the tag.")

        return {"message": "Item added to tag", "item": item, "tag": tag}

    @jwt_required()
    @blp.response(200, TagAndItemSchema)
    def delete(self, item_id, tag_id):
        """Unlink a tag from an item (previously there was no way to undo a link)."""
        item = ItemModel.query.get_or_404(item_id)
        tag = TagModel.query.get_or_404(tag_id)

        if not can_work_store(item.store):
            abort(403, message="You do not have permission to untag this item.")

        if tag not in item.tags:
            abort(404, message="This item does not have that tag.")

        item.tags.remove(tag)

        try:
            db.session.add(item)
            log_activity("unlink_tag", details=f"unlinked tag '{tag.name}' from item '{item.name}'")
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            abort(500, message="An error occurred while unlinking the tag.")

        return {"message": "Tag removed from item", "item": item, "tag": tag}


@blp.route("/tag/<int:tag_id>")
class Tag(MethodView):
    @jwt_required()
    @blp.response(200, TagSchema)
    def get(self, tag_id):
        tag = TagModel.query.get_or_404(tag_id)
        return tag

    @jwt_required()
    @blp.response(
        202,
        description="Deletes a tag if no item is tagged with it.",
        example={"message": "Tag deleted."}
    )
    @blp.alt_response(403, description="Caller does not manage the tag's store.")
    @blp.alt_response(404, description="Tag not found.")
    @blp.alt_response(
        400,
        description="Returned if the tag is assigned to one or more items. In this case, the tag is not deleted."
    )
    def delete(self, tag_id):
        tag = TagModel.query.get_or_404(tag_id)

        if not can_manage_store(tag.store):
            abort(403, message="Only the store owner or an admin can delete a tag.")

        if tag.items:
            abort(
                400,
                message="Could not delete tag. Make sure tag is not associated with any items, then try again."
            )

        log_activity("delete_tag", details=f"tag '{tag.name}' (id={tag.id})")
        db.session.delete(tag)
        db.session.commit()
        return {"message": "Tag deleted."}
