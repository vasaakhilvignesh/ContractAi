"""
ContractIQ — Authentication & Authorization Schemas

Phase 13A scope:
  - Strongly typed Pydantic schemas for registration, login, tokens, and current user.
  - Never expose hashed passwords or sensitive security credentials.
"""

import re
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class UserRegisterRequest(BaseModel):
    """Schema for new user registration."""

    email: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="User email address (must be valid format and unique)",
        examples=["analyst@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Plaintext password (minimum 8 characters)",
        examples=["SecurePass123!"],
    )
    full_name: Optional[str] = Field(
        default=None,
        max_length=255,
        description="User's display or legal name",
        examples=["Alex Analyst"],
    )
    organization: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Organization or firm name",
        examples=["Acme Corp"],
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        v_stripped = v.strip().lower()
        if not EMAIL_REGEX.match(v_stripped):
            raise ValueError("Invalid email format")
        return v_stripped


class UserLoginRequest(BaseModel):
    """Schema for user authentication / login."""

    email: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Registered user email address",
        examples=["analyst@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Account password",
        examples=["SecurePass123!"],
    )

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        v_stripped = v.strip().lower()
        if not EMAIL_REGEX.match(v_stripped):
            raise ValueError("Invalid email format")
        return v_stripped


class TokenResponse(BaseModel):
    """Schema for JWT access token response."""

    access_token: str = Field(
        ...,
        description="Cryptographically signed JWT bearer token",
    )
    token_type: str = Field(
        default="bearer",
        description="Token type (bearer)",
    )
    expires_in: int = Field(
        ...,
        description="Token lifespan in seconds",
        examples=[86400],
    )


class UserResponse(BaseModel):
    """Schema for public user profile (never exposes credentials or password hashes)."""

    id: uuid.UUID = Field(..., description="Unique user identifier")
    email: str = Field(..., description="User email address")
    full_name: Optional[str] = Field(default=None, description="Display name")
    organization: Optional[str] = Field(default=None, description="Organization name")
    role: str = Field(..., description="User role (admin, procurement_lead, legal, viewer)")
    is_active: bool = Field(..., description="Active account status flag")
    created_at: datetime = Field(..., description="Account creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class TokenPayload(BaseModel):
    """Validated JWT claims payload."""

    sub: str = Field(..., description="Subject claim containing user UUID string")
    email: str = Field(..., description="User email claim")
    role: str = Field(default="viewer", description="User role claim")
    exp: int = Field(..., description="Expiration timestamp (UNIX epoch)")
    iat: int = Field(..., description="Issued at timestamp (UNIX epoch)")
