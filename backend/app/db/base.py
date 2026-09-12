"""
ContractIQ Backend — SQLAlchemy Declarative Base

All ORM models inherit from Base.
This module is imported by Alembic's env.py to detect all mapped tables.

Usage:
    from app.db.base import Base
    class MyModel(Base):
        ...
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Shared declarative base for all ContractIQ SQLAlchemy models.
    Alembic's env.py imports this base (and all model modules) so that
    autogenerate can detect schema changes.
    """
    pass
