"""
ContractIQ — Health Endpoint Schemas

Pydantic models for the /health endpoint response.
The health response distinguishes API status from database status,
so a database issue does not mask a healthy API process.
"""

from pydantic import BaseModel


class DatabaseHealthSchema(BaseModel):
    """Database-specific health information."""

    connected: bool
    pg_version: str | None = None
    pgvector_version: str | None = None
    error: str | None = None

    model_config = {"from_attributes": True}


class HealthResponseSchema(BaseModel):
    """
    Response schema for GET /health.

    Fields:
      - status: Overall API status ("ok" | "degraded")
        "ok"      → API is running and DB connection is healthy.
        "degraded" → API is running but DB connection failed or is not configured.
      - version: Application version string.
      - database: Detailed database health sub-object.
    """

    status: str
    version: str
    database: DatabaseHealthSchema
