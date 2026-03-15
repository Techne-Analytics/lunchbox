import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lunchbox.db import Base


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE")
    )
    school_id: Mapped[str] = mapped_column(String)
    menu_date: Mapped[date] = mapped_column(Date, index=True)
    meal_type: Mapped[str] = mapped_column(String)
    serving_line: Mapped[str] = mapped_column(String)
    grade: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    item_name: Mapped[str] = mapped_column(String)
    fetched_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    subscription = relationship("Subscription", back_populates="menu_items")
