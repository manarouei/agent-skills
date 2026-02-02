import re
import uuid
import enum
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from auth.utils import hashed_password_generator

from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    ForeignKey,
    JSON,
    Text,
    Index,
    Numeric,
)
from sqlalchemy import Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.sql import func
from fastapi_storages import FileSystemStorage
from fastapi_storages.integrations.sqlalchemy import FileType

from config import settings
from .config import Base


class AdminUser(Base):
    __tablename__ = "adminusers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    def __str__(self) -> str:  # pragma: no cover
        return self.username


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[Optional[str]] = mapped_column(String, unique=True, index=True, nullable=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    hashed_password: Mapped[str] = mapped_column(String, default=lambda: hashed_password_generator())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_staff: Mapped[bool] = mapped_column(Boolean, default=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    workflows: Mapped[List["Workflow"]] = relationship(
        "Workflow",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    credentials: Mapped[List["Credential"]] = relationship(
        "Credential",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    orders: Mapped[List["Order"]] = relationship(
        "Order",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    subscriptions: Mapped[List["Subscription"]] = relationship(
        "Subscription",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @validates("email")
    def validate_email(self, _key: str, value: Optional[str]) -> Optional[str]:
        """Convert empty string to NULL for unique constraint compatibility"""
        if value == '' or value is None:
            return None
        return value

    @validates("username")
    def validate_phone(self, _key: str, value: str) -> str:
        if value and not re.match(r"09\d{9}", value):
            raise ValueError("Invalid phone number format")
        return value

    @property
    def active_subscription(self) -> Optional["Subscription"]:
        for user_subscription in self.subscriptions:
            if user_subscription.is_valid:
                return user_subscription
        return None


class PhoneCode(Base):
    __tablename__ = "phone_codes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    phone_number: Mapped[str] = mapped_column(String(11), unique=True)
    tmp_code: Mapped[str] = mapped_column(String(6))
    tmp_code_expire: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tmp_code_sent_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    tmp_code_sent_counter: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    def check_code(self, code: str) -> bool:
        now = datetime.now(timezone.utc)
        return self.tmp_code == code and self.tmp_code_expire > now


class WhiteListPhones(Base):
    __tablename__ = "whitelist_phones"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    phone_number: Mapped[str] = mapped_column(String(11), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    nodes: Mapped[Dict[str, Any] | List[Dict[str, Any]] | None] = mapped_column(JSON)
    connections: Mapped[Dict[str, Any] | List[Dict[str, Any]] | None] = mapped_column(JSON)
    settings: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    pin_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    trigger_count: Mapped[int] = mapped_column(default=0)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))

    user: Mapped["User"] = relationship("User", back_populates="workflows")

    executions: Mapped[List["Execution"]] = relationship(
        "Execution", back_populates="workflow", cascade="all, delete-orphan"
    )
    webhooks: Mapped[List["Webhook"]] = relationship(
        "Webhook", back_populates="workflow", cascade="all, delete-orphan"
    )


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    type: Mapped[str] = mapped_column(String(128), nullable=False)
    data: Mapped[str] = mapped_column(String, nullable=False)  # Encrypted credentials
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    is_managed: Mapped[bool] = mapped_column(Boolean, default=False)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"))

    user: Mapped["User"] = relationship("User", back_populates="credentials")


class Execution(Base):
    __tablename__ = "executions"

    STATUS_CHOICES = ["pending", "running", "success", "error"]

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    finished: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32))
    mode: Mapped[str] = mapped_column(String(32))
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    workflow_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflows.id", ondelete="CASCADE"))

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="executions")
    executionData: Mapped[Optional["ExecutionData"]] = relationship(
        "ExecutionData",
        uselist=False,
        back_populates="execution",
        cascade="all, delete-orphan",
    )

    @validates("status")
    def validate_status(self, _key, value: str) -> str:
        if value not in self.STATUS_CHOICES:
            raise ValueError(f"Invalid status: {value}")
        return value


class ExecutionData(Base):
    __tablename__ = "execution_data"

    data: Mapped[str] = mapped_column(Text, nullable=False)
    workflow_data: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)

    execution_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("executions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    execution: Mapped["Execution"] = relationship(
        "Execution",
        back_populates="executionData",
    )


class Webhook(Base):
    __tablename__ = "webhook"

    webhook_id: Mapped[str] = mapped_column(String, primary_key=True)
    method: Mapped[str] = mapped_column(Text, primary_key=True)
    node: Mapped[str] = mapped_column(String, nullable=False)
    workflow_id: Mapped[str] = mapped_column(
        String, ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="webhooks")

    __table_args__ = (
        Index(
            "ix_webhook_webhook_id_method",
            "webhook_id",
            "method",
        ),
    )


class DynamicNode(Base):
    __tablename__ = "dynamic_nodes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(100), unique=True)
    version: Mapped[int] = mapped_column()
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    properties: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[Optional[str]] = mapped_column(String(50))
    icon: Mapped[Optional[str]] = mapped_column(FileType(FileSystemStorage(settings.MEDIA_ROOT / "dynamic_nodes")))
    is_start: Mapped[bool] = mapped_column(Boolean, default=False)
    is_end: Mapped[bool] = mapped_column(Boolean, default=False)
    is_webhook: Mapped[bool] = mapped_column(Boolean, default=False)
    is_schedule: Mapped[bool] = mapped_column(Boolean, server_default="false")


class CredentialType(Base):
    __tablename__ = "credential_types"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    properties: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)  # Store JSON properties configuration
    is_oauth2: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class Option(Base):
    __tablename__ = "options"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(String(255), nullable=False)


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255))
    nodes_limit: Mapped[int] = mapped_column(nullable=False)
    price: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)  # in toman
    duration_days: Mapped[int] = mapped_column(nullable=False)  # in days
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())


class OrderStatusEnum(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    failed = "failed"
    canceled = "canceled"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    plan_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    amount: Mapped[int] = mapped_column(Numeric(12, 0), nullable=False)
    tax: Mapped[int] = mapped_column(default=0)
    status: Mapped[OrderStatusEnum] = mapped_column(Enum(OrderStatusEnum), default=OrderStatusEnum.pending)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    user: Mapped[Optional["User"]] = relationship("User", back_populates="orders")
    transaction: Mapped[Optional["Transaction"]] = relationship("Transaction", back_populates="order", uselist=False)

    @property
    def price(self) -> Optional[int]:
        return (self.plan_snapshot or {}).get("price")

    @property
    def nodes_limit(self) -> int:
        return (self.plan_snapshot or {}).get("nodes_limit", 0)

    @property
    def total_price(self) -> int:
        return int(self.amount) + int(self.tax)


class TransactionStatusEnum(str, enum.Enum):
    pending = "pending"
    success = "success"
    failed = "failed"


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    authority: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # از زرین‌پال
    ref_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # کد رهگیری در صورت موفقیت
    status: Mapped[TransactionStatusEnum] = mapped_column(Enum(TransactionStatusEnum), default=TransactionStatusEnum.pending)
    gateway: Mapped[str] = mapped_column(String(50), default="ZarinPal")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())

    order: Mapped["Order"] = relationship("Order", back_populates="transaction")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    nodes_used: Mapped[int] = mapped_column(default=0)
    nodes_limit: Mapped[int] = mapped_column(default=0)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    
    # Dynamic node access fields
    plan_type: Mapped[str] = mapped_column(String(50), default="custom", nullable=False)
    node_overrides: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, default=dict, nullable=True)

    user: Mapped[Optional["User"]] = relationship("User", back_populates="subscriptions")

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.end_date

    @property
    def is_valid(self) -> bool:
        return self.is_active and not self.is_expired

    @property
    def remaining_nodes(self) -> int:
        return self.nodes_limit - self.nodes_used
