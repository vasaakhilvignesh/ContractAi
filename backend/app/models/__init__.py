"""
app/models/__init__.py

Imports all ORM model classes so that SQLAlchemy's MetaData (attached to Base)
is fully populated. This module MUST be imported by Alembic's env.py before
calling Base.metadata.create_all() or autogenerating migrations, otherwise
Alembic will not detect any tables.

Import order follows foreign-key dependency order to avoid forward reference issues
in documentation, though SQLAlchemy handles forward references via strings.
"""

# Level 0: No FK dependencies
from app.models.user import User

# Level 1: Depends on users
from app.models.contract import Contract

# Level 2: Depends on contracts
from app.models.document_chunk import DocumentChunk

# Level 3: Depends on contracts + document_chunks
from app.models.clause import Clause

# Level 4: Depends on contracts + clauses + document_chunks
from app.models.obligation import Obligation
from app.models.risk_signal import RiskSignal

# Level 5: Depends on users + contracts
from app.models.audit_event import AuditEvent

__all__ = [
    "User",
    "Contract",
    "DocumentChunk",
    "Clause",
    "Obligation",
    "RiskSignal",
    "AuditEvent",
]
