import uuid
from datetime import datetime, time, timezone

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lunchbox.db import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String, default="schoolcafe")
    school_id: Mapped[str] = mapped_column(String)
    school_name: Mapped[str] = mapped_column(String)
    grade: Mapped[str] = mapped_column(String)
    meal_configs: Mapped[list] = mapped_column(JSON)
    included_categories: Mapped[list | None] = mapped_column(JSON, nullable=True)
    excluded_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    feed_token: Mapped[uuid.UUID] = mapped_column(
        unique=True, index=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(String)
    alert_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    show_as_busy: Mapped[bool] = mapped_column(Boolean, default=False)
    event_type: Mapped[str] = mapped_column(String, default="all_day")
    event_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    event_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )

    user = relationship("User", back_populates="subscriptions")
    menu_items = relationship(
        "MenuItem", back_populates="subscription", cascade="all, delete-orphan"
    )
    sync_logs = relationship(
        "SyncLog", back_populates="subscription", cascade="all, delete-orphan"
    )
