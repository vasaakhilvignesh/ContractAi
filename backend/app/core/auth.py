"""
ContractIQ — Core Authentication & Authorization Dependencies

Phase 13C scope:
  - Extract and validate JWT bearer tokens from HTTP Authorization headers.
  - Enforce active user requirements.
  - Enforce contract ownership to protect against IDOR (Insecure Direct Object References).
"""

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.contract import Contract
from app.models.user import User
from app.services.auth_service import (
    TokenError,
    TokenExpiredError,
    decode_access_token,
)

security_bearer = HTTPBearer(auto_error=False)


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> Optional[User]:
    """
    Extracts and validates the current user if an Authorization Bearer header is provided.
    Returns None if no header is present.
    Raises HTTPException(401) if token is provided but invalid/expired.
    """
    if not credentials or not credentials.credentials:
        return None

    token = credentials.credentials
    try:
        payload = decode_access_token(token)
    except TokenExpiredError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except TokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user_id_str = payload.get("sub")
    try:
        user_id = uuid.UUID(user_id_str)
    except (ValueError, TypeError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user identification in token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e

    user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Requires a valid JWT Bearer token and returns the active authenticated User.
    Raises HTTPException(401) if missing or invalid.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_current_user_optional(credentials=credentials, db=db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def verify_contract_access(
    contract: Contract,
    current_user: Optional[User],
) -> None:
    """
    Verifies that the given user has permission to access the contract.
    If current_user is authenticated:
      - If contract.uploaded_by is set, contract.uploaded_by must match current_user.id (or admin).
    If unauthorized, raises HTTPException(403).
    """
    if current_user is None:
        return

    # Admin role can access all contracts
    if current_user.role == "admin":
        return

    if contract.uploaded_by is not None and contract.uploaded_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you do not have permission to access this contract",
        )
