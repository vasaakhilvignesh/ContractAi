"""
ContractIQ — Authentication REST API Router

Phase 13B & 13D scope:
  - POST /auth/register: Registers new user, returns UserResponse (HTTP 201).
  - POST /auth/login: Authenticates user, returns JWT TokenResponse (HTTP 200).
  - GET  /auth/me: Retrieves currently authenticated user profile (HTTP 200).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)
from app.services.auth_service import (
    InactiveUserError,
    InvalidCredentialsError,
    UserAlreadyExistsError,
    authenticate_user,
    create_access_token,
    register_user,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
    description="Registers a new user with unique email and secure password hashing.",
)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
) -> UserResponse:
    """Register a new user account."""
    try:
        user = register_user(
            db=db,
            email=request.email,
            password=request.password,
            full_name=request.full_name,
            organization=request.organization,
        )
        return UserResponse.model_validate(user)
    except UserAlreadyExistsError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate and obtain JWT access token",
    description="Validates user email and password, returning a signed JWT bearer token.",
)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """Login and generate access token."""
    try:
        user = authenticate_user(
            db=db,
            email=request.email,
            password=request.password,
        )
        token, expires_in = create_access_token(
            user_id=user.id,
            email=user.email,
            role=user.role,
        )
        return TokenResponse(
            access_token=token,
            token_type="bearer",
            expires_in=expires_in,
        )
    except InvalidCredentialsError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e
    except InactiveUserError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        ) from e


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Retrieves profile of the authenticated user via Bearer token.",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get authenticated user's profile."""
    return UserResponse.model_validate(current_user)
