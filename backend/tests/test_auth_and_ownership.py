"""
ContractIQ — Phase 13A–13E Authentication & Per-User Ownership Test Suite

Covers:
  - 13A: Password hashing (PBKDF2-HMAC-SHA256, constant-time compare, salting) & JWT tokens (sign, decode, expire, tamper)
  - 13B: Registration (POST /auth/register), duplicate email rejection (409 Conflict), login (POST /auth/login), invalid credentials rejection (401)
  - 13C: Current user profile (GET /auth/me), token validation (401 on missing/malformed/expired)
  - 13D: Contract ownership enforcement & per-user isolation (200 for owner/admin, 403 IDOR rejection for other users)
  - 13E: Non-tamperability and zero credential leakage in responses
"""

import uuid
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.auth import verify_contract_access
from app.db.session import SessionLocal
from app.models.contract import Contract
from app.models.user import User
from app.services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
    TokenError,
    TokenExpiredError,
)


# ====================================================================
# Unit Tests: 13A Password Hashing & JWT Tokens
# ====================================================================

def test_password_hashing_and_verification():
    """Verify passwords are salted and verified with constant-time comparison."""
    password = "SuperSecretPassword123!"
    hashed = hash_password(password)

    # Hash should start with algorithm identifier and iteration count
    assert hashed.startswith("pbkdf2_sha256$600000$")
    assert hashed != password

    # Two hashes of same password must differ (salting)
    hashed2 = hash_password(password)
    assert hashed != hashed2

    # Verification must succeed for correct password and fail for wrong password
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password(password, None) is False
    assert verify_password("", hashed) is False


def test_jwt_token_generation_and_decoding():
    """Verify signed JWT creation, claim decoding, and tampering rejection."""
    user_id = uuid.uuid4()
    email = "analyst@contractiq.internal"
    role = "legal"

    token, expires_in = create_access_token(user_id=user_id, email=email, role=role, expires_minutes=30)
    assert isinstance(token, str)
    assert expires_in == 30 * 60

    # Valid token decode
    claims = decode_access_token(token)
    assert claims["sub"] == str(user_id)
    assert claims["email"] == email
    assert claims["role"] == role
    assert claims["exp"] > claims["iat"]

    # Tampered signature should be rejected
    tampered_token = token[:-4] + "xxxx"
    with pytest.raises(TokenError):
        decode_access_token(tampered_token)

    # Malformed token should be rejected
    with pytest.raises(TokenError):
        decode_access_token("invalid.token")


def test_jwt_token_expiration():
    """Verify expired tokens are rejected deterministically."""
    user_id = uuid.uuid4()
    email = "expired@contractiq.internal"

    # Create token with -1 minute expiration
    token, _ = create_access_token(user_id=user_id, email=email, expires_minutes=-1)
    with pytest.raises(TokenExpiredError):
        decode_access_token(token)


# ====================================================================
# Integration Tests: 13B & 13C API Registration, Login, and Me
# ====================================================================

@pytest.mark.db
def test_auth_registration_and_login_flow(test_client: TestClient, database_url):
    """Test user registration, duplicate prevention, login, and profile fetching."""
    if not database_url:
        pytest.skip("DATABASE_URL not configured")

    unique_suffix = uuid.uuid4().hex[:8]
    email = f"user_{unique_suffix}@contractiq.io"
    password = "SecurePassword123!"

    # 1. Register new user
    reg_resp = test_client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
            "full_name": "Test User",
            "organization": "Acme Legal",
        },
    )
    assert reg_resp.status_code == 201
    user_data = reg_resp.json()
    assert user_data["email"] == email
    assert user_data["full_name"] == "Test User"
    assert user_data["organization"] == "Acme Legal"
    assert "hashed_password" not in user_data
    assert "password" not in user_data

    # 2. Duplicate registration must return 409 Conflict
    dup_resp = test_client.post(
        "/auth/register",
        json={
            "email": email,
            "password": password,
        },
    )
    assert dup_resp.status_code == 409
    assert "already exists" in dup_resp.json()["detail"].lower()

    # 3. Login with wrong password must return 401 Unauthorized
    bad_login = test_client.post(
        "/auth/login",
        json={"email": email, "password": "WrongPassword123!"},
    )
    assert bad_login.status_code == 401

    # 4. Login with correct password must return JWT token
    good_login = test_client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert good_login.status_code == 200
    token_data = good_login.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    access_token = token_data["access_token"]

    # 5. Access /auth/me without token -> 401
    unauth_me = test_client.get("/auth/me")
    assert unauth_me.status_code == 401

    # 6. Access /auth/me with Bearer token -> 200
    auth_me = test_client.get(
        "/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert auth_me.status_code == 200
    me_data = auth_me.json()
    assert me_data["email"] == email
    assert me_data["id"] == user_data["id"]


# ====================================================================
# Ownership Tests: 13C & 13D Contract Access & IDOR Prevention
# ====================================================================

@pytest.mark.db
def test_contract_ownership_and_idor_protection(database_url):
    """Test that contracts owned by User A cannot be accessed/modified by User B (403 Forbidden)."""
    if not database_url:
        pytest.skip("DATABASE_URL not configured")

    session = SessionLocal()
    try:
        # Create User A
        user_a = User(
            id=uuid.uuid4(),
            email=f"usera_{uuid.uuid4().hex[:6]}@test.com",
            full_name="User A",
            role="viewer",
            is_active=True,
        )
        # Create User B
        user_b = User(
            id=uuid.uuid4(),
            email=f"userb_{uuid.uuid4().hex[:6]}@test.com",
            full_name="User B",
            role="viewer",
            is_active=True,
        )
        # Create Admin User
        admin_user = User(
            id=uuid.uuid4(),
            email=f"admin_{uuid.uuid4().hex[:6]}@test.com",
            full_name="Admin User",
            role="admin",
            is_active=True,
        )
        session.add_all([user_a, user_b, admin_user])
        session.commit()

        # Create Contract belonging to User A
        contract_a = Contract(
            id=uuid.uuid4(),
            title="User A Confidential Contract",
            vendor="Acme Corp",
            status="active",
            uploaded_by=user_a.id,
        )
        session.add(contract_a)
        session.commit()

        # Test verify_contract_access logic directly
        # 1. Owner (User A) should have access
        verify_contract_access(contract_a, user_a)

        # 2. Admin should have access
        verify_contract_access(contract_a, admin_user)

        # 3. User B should be forbidden (HTTP 403 IDOR prevention)
        with pytest.raises(HTTPException) as exc_info:
            verify_contract_access(contract_a, user_b)
        assert exc_info.value.status_code == 403
        assert "access forbidden" in exc_info.value.detail.lower()

        # 4. Unauthenticated caller (current_user=None) passes access check for backwards-compatible public view
        verify_contract_access(contract_a, None)
    finally:
        session.close()


@pytest.mark.db
def test_contract_api_per_user_isolation(test_client: TestClient, database_url):
    """Test contract endpoints with authenticated users and verify cross-user isolation."""
    if not database_url:
        pytest.skip("DATABASE_URL not configured")

    # Register & login User 1
    u1_email = f"u1_{uuid.uuid4().hex[:6]}@test.com"
    test_client.post("/auth/register", json={"email": u1_email, "password": "Password123!"})
    login_1 = test_client.post("/auth/login", json={"email": u1_email, "password": "Password123!"})
    token_1 = login_1.json()["access_token"]

    # Register & login User 2
    u2_email = f"u2_{uuid.uuid4().hex[:6]}@test.com"
    test_client.post("/auth/register", json={"email": u2_email, "password": "Password123!"})
    login_2 = test_client.post("/auth/login", json={"email": u2_email, "password": "Password123!"})
    token_2 = login_2.json()["access_token"]

    # User 1 creates a contract
    create_resp = test_client.post(
        "/contracts",
        json={"title": "User 1 Master Agreement", "vendor": "Vendor Alpha"},
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert create_resp.status_code == 201
    contract_id = create_resp.json()["id"]

    # User 1 can fetch their contract
    get_owner_resp = test_client.get(
        f"/contracts/{contract_id}",
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert get_owner_resp.status_code == 200
    assert get_owner_resp.json()["title"] == "User 1 Master Agreement"

    # User 2 attempts to fetch User 1's contract -> 403 Forbidden
    get_other_resp = test_client.get(
        f"/contracts/{contract_id}",
        headers={"Authorization": f"Bearer {token_2}"},
    )
    assert get_other_resp.status_code == 403

    # User 2 attempts to update User 1's contract -> 403 Forbidden
    patch_other_resp = test_client.patch(
        f"/contracts/{contract_id}",
        json={"title": "Hacked Title"},
        headers={"Authorization": f"Bearer {token_2}"},
    )
    assert patch_other_resp.status_code == 403

    # User 2 attempts to delete User 1's contract -> 403 Forbidden
    delete_other_resp = test_client.delete(
        f"/contracts/{contract_id}",
        headers={"Authorization": f"Bearer {token_2}"},
    )
    assert delete_other_resp.status_code == 403

    # User 1 can delete their own contract -> 204 No Content
    delete_owner_resp = test_client.delete(
        f"/contracts/{contract_id}",
        headers={"Authorization": f"Bearer {token_1}"},
    )
    assert delete_owner_resp.status_code == 204
