import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TenantScopedMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Customer(TenantScopedMixin, Base):
    __tablename__ = "customers"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    segment: Mapped[str] = mapped_column(String(64), nullable=False, default="standard")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")


class Product(TenantScopedMixin, Base):
    __tablename__ = "products"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(128), nullable=False, default="general")


class Subscription(TenantScopedMixin, Base):
    __tablename__ = "subscriptions"

    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), index=True)
    product_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("products.id"), index=True)
    plan: Mapped[str] = mapped_column(String(64), nullable=False, default="standard")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    started_at: Mapped[date] = mapped_column(Date, nullable=False)
    ended_at: Mapped[date | None] = mapped_column(Date, nullable=True)


class Transaction(TenantScopedMixin, Base):
    __tablename__ = "transactions"

    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    occurred_on: Mapped[date] = mapped_column(Date, nullable=False)


class SupportTicket(TenantScopedMixin, Base):
    __tablename__ = "support_tickets"

    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, default="normal")
    opened_on: Mapped[date] = mapped_column(Date, nullable=False)


class Contract(TenantScopedMixin, Base):
    __tablename__ = "contracts"

    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), index=True)
    renewal_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)


class Invoice(TenantScopedMixin, Base):
    __tablename__ = "invoices"

    customer_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("customers.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")


class Employee(TenantScopedMixin, Base):
    __tablename__ = "employees"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(128), nullable=False, default="general")


class Document(TenantScopedMixin, Base):
    __tablename__ = "documents"

    customer_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("customers.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False, default="upload")
    content: Mapped[str] = mapped_column(Text, nullable=False)


class DocumentChunk(TenantScopedMixin, Base):
    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("documents.id"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # List[float] produced by app.services.embeddings; see that module for
    # exactly what kind of vector this is and its known limitations.
    embedding: Mapped[list[float]] = mapped_column(JSON, nullable=False)
