import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from tests.factories import (
    create_menu_item,
    create_subscription,
    create_sync_log,
    create_user,
)


class TestUniqueConstraints:
    def test_duplicate_google_id_raises(self, db):
        create_user(db, google_id="dupe-gid")
        db.flush()
        with pytest.raises(IntegrityError):
            create_user(db, google_id="dupe-gid")

    def test_duplicate_feed_token_raises(self, db):
        user = create_user(db)
        token = uuid.uuid4()
        create_subscription(db, user, feed_token=token)
        db.flush()
        with pytest.raises(IntegrityError):
            create_subscription(db, user, feed_token=token, display_name="Other")


class TestForeignKeyConstraints:
    def test_subscription_with_bad_user_id_raises(self, db):
        from lunchbox.models import Subscription

        sub = Subscription(
            user_id=uuid.uuid4(),
            school_id="x",
            school_name="X",
            grade="05",
            meal_configs=[],
            display_name="X",
        )
        db.add(sub)
        with pytest.raises(IntegrityError):
            db.flush()


class TestCascadeDeletes:
    def test_delete_subscription_cascades_menu_items(self, db):
        user = create_user(db)
        sub = create_subscription(db, user)
        create_menu_item(db, sub)
        create_sync_log(db, sub)
        db.commit()

        from lunchbox.models import MenuItem, SyncLog

        db.delete(sub)
        db.commit()

        assert (
            db.query(MenuItem).filter(MenuItem.subscription_id == sub.id).count() == 0
        )
        assert db.query(SyncLog).filter(SyncLog.subscription_id == sub.id).count() == 0

    def test_delete_user_cascades_subscriptions(self, db):
        from lunchbox.models import Subscription

        user = create_user(db)
        create_subscription(db, user)
        db.commit()

        db.delete(user)
        db.commit()

        assert (
            db.query(Subscription).filter(Subscription.user_id == user.id).count() == 0
        )


class TestAutoGeneration:
    def test_feed_token_auto_generated(self, db):
        user = create_user(db)
        sub = create_subscription(db, user)
        assert sub.feed_token is not None
        assert isinstance(sub.feed_token, uuid.UUID)

    def test_timestamps_auto_populated(self, db):
        user = create_user(db)
        sub = create_subscription(db, user)
        assert sub.created_at is not None
        assert sub.updated_at is not None
