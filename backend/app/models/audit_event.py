"""
ContractIQ — AuditEvent Model

Provides a tamper-evident, append-only audit log of all significant
actions performed on the ContractIQ platform.

Design principles:
  - Records are append-only. Existing records must NEVER be updated or deleted.
  - actor: Can be a user ID or the string "system" for automated pipeline events.
  - entity_type / entity_id: What object was acted upon (e.g., "contract", <uuid>).
  - event_type: A stable string code for the action (see examples in comment).
  - details: JSON-encoded supplementary information about the event.

Event type examples:
  - contract.uploaded
  - contract.processing.started
  - contract.processing.completed
  - contract.processing.failed
  - clause.extracted
  - obligation.extracted
  - risk_signal.generated
  - risk_signal.acknowledged
  - user.login (Phase 6)
  - user.created (Phase 6)

Evidence lineage:
  AuditEvent → Contract (optional)
  AuditEvent → User (optional — "system" events have no user FK)
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AuditEvent(Base):
    __tablename__ = "audit_events"

    # ----------------------------------------------------------------
    # Primary Key
    # ----------------------------------------------------------------
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for this audit event",
    )

    # ----------------------------------------------------------------
    # Actor
    # ----------------------------------------------------------------
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="User who performed this action. NULL for system-initiated events.",
    )
    actor: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="system",
        comment=(
            "Human-readable actor identifier. "
            "Either user email/name or 'system' for automated events."
        ),
    )

    # ----------------------------------------------------------------
    # Event Classification
    # ----------------------------------------------------------------
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment=(
            "Stable dot-notation event code. "
            "Example: contract.uploaded, risk_signal.acknowledged, user.login"
        ),
    )

    # ----------------------------------------------------------------
    # Target Entity
    # ----------------------------------------------------------------
    entity_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Type of entity acted upon: contract | clause | obligation | risk_signal | user",
    )
    entity_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="UUID (as string) of the entity acted upon",
    )

    # ----------------------------------------------------------------
    # Contract Reference (direct FK for efficient contract audit log queries)
    # ----------------------------------------------------------------
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Contract associated with this event, if applicable",
    )

    # ----------------------------------------------------------------
    # Event Details
    # ----------------------------------------------------------------
    details: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment=(
            "JSON-encoded supplementary data about the event. "
            "Must not contain passwords or full credentials."
        ),
    )
    ip_address: Mapped[str | None] = mapped_column(
        String(45),  # Supports both IPv4 and IPv6
        nullable=True,
        comment="Client IP address at the time of the event (Phase 6+)",
    )

    # ----------------------------------------------------------------
    # Timestamp (immutable after insert — no updated_at)
    # ----------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        comment="Event timestamp — immutable after insert",
    )

    # ----------------------------------------------------------------
    # Relationships
    # ----------------------------------------------------------------
    user: Mapped["User | None"] = relationship(  # noqa: F821
        "User",
        back_populates="audit_events",
    )
    contract: Mapped["Contract | None"] = relationship(  # noqa: F821
        "Contract",
        back_populates="audit_events",
    )

    def __repr__(self) -> str:
        return (
            f"<AuditEvent id={self.id} event_type={self.event_type!r} "
            f"actor={self.actor!r} at={self.created_at}>"
        )
