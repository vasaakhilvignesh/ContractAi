"""
ContractIQ — User Model

Represents a ContractIQ platform user.
Authentication implementation is Phase 6 scope.
This model establishes the relational anchor for per-user contract isolation.

Evidence lineage: User → Contracts (ownership)
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    # ----------------------------------------------------------------
    # Primary Key
    # ----------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for the user",
    )

    # ----------------------------------------------------------------
    # Identity
    # ----------------------------------------------------------------
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="User email address — primary login identifier",
    )
    full_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Display name",
    )
    hashed_password: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Cryptographically salted and hashed password",
    )
    organization: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="User's organization or company name",
    )

    # ----------------------------------------------------------------
    # Access Control (stub — Phase 6 implementation)
    # ----------------------------------------------------------------
    role: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="viewer",
        comment="User role: admin | procurement_lead | legal | viewer",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Soft-delete flag — inactive users cannot log in",
    )

    # ----------------------------------------------------------------
    # Timestamps
    # ----------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        comment="Record creation timestamp",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="Record last-updated timestamp",
    )

    # ----------------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------------
    contracts: Mapped[list["Contract"]] = relationship(  # noqa: F821
        "Contract",
        back_populates="uploaded_by_user",
        cascade="all, delete-orphan",
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(  # noqa: F821
        "AuditEvent",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role!r}>"
