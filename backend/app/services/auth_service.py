"""
ContractIQ — Authentication Service

Phase 13A scope:
  - Cryptographically secure password hashing (PBKDF2-HMAC-SHA256 with 600,000 rounds).
  - Cryptographically signed JWT access tokens (HMAC-SHA256).
  - User registration with duplicate email detection.
  - User credential verification.
  - No plain-text passwords stored or logged.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.user import User


class AuthServiceError(Exception):
    """Base exception for authentication service errors."""


class UserAlreadyExistsError(AuthServiceError):
    """Raised when attempting to register an email that already exists."""


class InvalidCredentialsError(AuthServiceError):
    """Raised when authentication credentials are invalid or user not found."""


class InactiveUserError(AuthServiceError):
    """Raised when user account is inactive."""


class TokenError(AuthServiceError):
    """Raised when a JWT token is malformed, invalid, or expired."""


class TokenExpiredError(TokenError):
    """Raised when a JWT token has expired."""


# ----------------------------------------------------------------------
# Password Hashing Utilities (Standard Library PBKDF2-HMAC-SHA256)
# Format: pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
# ----------------------------------------------------------------------

PBKDF2_ITERATIONS = 600_000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    """
    Hash a plaintext password with a random 16-byte salt using PBKDF2-HMAC-SHA256.
    Uses 600,000 iterations for robust security resistance against brute-force attacks.
    """
    salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(dk).decode("ascii")
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, hashed_password: Optional[str]) -> bool:
    """
    Verify a plaintext password against a stored PBKDF2 hash using constant-time comparison.
    """
    if not hashed_password:
        return False
    try:
        parts = hashed_password.split("$")
        if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
            return False
        iterations = int(parts[1])
        salt = base64.b64decode(parts[2].encode("ascii"))
        expected_hash = base64.b64decode(parts[3].encode("ascii"))
        actual_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual_hash, expected_hash)
    except Exception:
        return False


# ----------------------------------------------------------------------
# JWT Token Utilities (Standard Library HS256)
# Format: <header_b64>.<payload_b64>.<signature_b64>
# ----------------------------------------------------------------------

def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data_str: str) -> bytes:
    padding = "=" * (4 - (len(data_str) % 4) if len(data_str) % 4 != 0 else 0)
    return base64.urlsafe_b64decode((data_str + padding).encode("ascii"))


def create_access_token(
    user_id: uuid.UUID,
    email: str,
    role: str = "viewer",
    expires_minutes: Optional[int] = None,
) -> Tuple[str, int]:
    """
    Generate a signed JWT HS256 access token.
    Returns: (token_string, expires_in_seconds)
    """
    exp_minutes = expires_minutes if expires_minutes is not None else settings.jwt_access_token_expire_minutes
    expires_in_seconds = int(exp_minutes * 60)
    now = int(time.time())
    exp = now + expires_in_seconds

    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "iat": now,
        "exp": exp,
    }

    header_bytes = json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")

    unsigned_token = f"{_b64url_encode(header_bytes)}.{_b64url_encode(payload_bytes)}"
    secret_bytes = settings.jwt_secret_key.encode("utf-8")
    signature = hmac.new(secret_bytes, unsigned_token.encode("ascii"), hashlib.sha256).digest()
    token = f"{unsigned_token}.{_b64url_encode(signature)}"

    return token, expires_in_seconds


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Validate and decode a JWT HS256 access token.
    Checks signature, structure, and expiration.
    """
    if not token or not isinstance(token, str):
        raise TokenError("Token is missing or empty")

    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("Malformed token structure")

    header_b64, payload_b64, signature_b64 = parts
    unsigned_token = f"{header_b64}.{payload_b64}"
    secret_bytes = settings.jwt_secret_key.encode("utf-8")
    expected_sig = hmac.new(secret_bytes, unsigned_token.encode("ascii"), hashlib.sha256).digest()

    try:
        actual_sig = _b64url_decode(signature_b64)
    except Exception as e:
        raise TokenError("Invalid token signature encoding") from e

    if not hmac.compare_digest(actual_sig, expected_sig):
        raise TokenError("Invalid token signature")

    try:
        header_raw = _b64url_decode(header_b64).decode("utf-8")
        header = json.loads(header_raw)
        if header.get("alg") != "HS256":
            raise TokenError(f"Unsupported algorithm: {header.get('alg')}")

        payload_raw = _b64url_decode(payload_b64).decode("utf-8")
        payload = json.loads(payload_raw)
    except TokenError:
        raise
    except Exception as e:
        raise TokenError("Failed to parse token claims") from e

    now = int(time.time())
    exp = payload.get("exp")
    if exp is None or not isinstance(exp, (int, float)):
        raise TokenError("Token missing expiration claim")

    if now > exp:
        raise TokenExpiredError("Token has expired")

    if not payload.get("sub"):
        raise TokenError("Token missing subject claim")

    return payload


# ----------------------------------------------------------------------
# User Registration & Authentication Services
# ----------------------------------------------------------------------

def register_user(
    db: Session,
    email: str,
    password: str,
    full_name: Optional[str] = None,
    organization: Optional[str] = None,
    role: str = "viewer",
) -> User:
    """
    Register a new user account.
    Checks for email uniqueness, hashes password, and persists user record.
    """
    normalized_email = email.strip().lower()

    # Check for duplicate email
    existing = db.execute(
        select(User).where(User.email == normalized_email)
    ).scalar_one_or_none()

    if existing is not None:
        raise UserAlreadyExistsError(f"User with email '{normalized_email}' already exists")

    hashed_pw = hash_password(password)

    user = User(
        email=normalized_email,
        hashed_password=hashed_pw,
        full_name=full_name.strip() if full_name else None,
        organization=organization.strip() if organization else None,
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(
    db: Session,
    email: str,
    password: str,
) -> User:
    """
    Authenticate user by email and password.
    Returns User if valid, otherwise raises InvalidCredentialsError or InactiveUserError.
    """
    normalized_email = email.strip().lower()
    user = db.execute(
        select(User).where(User.email == normalized_email)
    ).scalar_one_or_none()

    if user is None:
        raise InvalidCredentialsError("Invalid email or password")

    if not verify_password(password, user.hashed_password):
        raise InvalidCredentialsError("Invalid email or password")

    if not user.is_active:
        raise InactiveUserError("User account is inactive")

    return user
