import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"


class Order(Base):
    __tablename__ = "orders"

    # UUID generated in Python, not by the DB, so the value is available
    # immediately after object creation — before the INSERT is committed.
    # This lets us publish the order_id to RabbitMQ in the same request handler
    # without an extra SELECT after commit.
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_id: Mapped[str] = mapped_column(String, nullable=False)
    product_id: Mapped[str] = mapped_column(String, nullable=False)
    quantity: Mapped[int]
    # Default applied by SQLAlchemy on the Python side; the DB schema also has
    # server_default="pending" (see migration) as a safety net for direct INSERT.
    status: Mapped[str] = mapped_column(String, default=OrderStatus.PENDING)
    # server_default lets the DB set the timestamp, avoiding clock skew
    # between application servers.
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
