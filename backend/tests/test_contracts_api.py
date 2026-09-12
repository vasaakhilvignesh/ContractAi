"""
ContractIQ — Tests for Contract REST API Endpoints

Tests:
  1. POST /contracts — Create contract successfully with 201 Created.
  2. GET /contracts/{id} — Retrieve created contract by UUID.
  3. GET /contracts — List contracts with pagination and filtering.
  4. PATCH /contracts/{id} — Partially update contract fields.
  5. DELETE /contracts/{id} — Delete contract with 204 No Content.
  6. GET /contracts/{id} — Nonexistent UUID returns 404.
  7. PATCH /contracts/{id} — Nonexistent UUID returns 404.
  8. DELETE /contracts/{id} — Nonexistent UUID returns 404.
  9. GET /contracts/{invalid} — Invalid UUID format returns 422.
  10. POST /contracts — Validation failure (empty title / negative value) returns 422.
  11. GET /api/v1/contracts — Prefixed route behaves identically.
"""

import uuid
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def sample_contract_payload() -> dict:
    """Provides a valid contract creation payload."""
    return {
        "title": f"Test Master Services Agreement - {uuid.uuid4().hex[:8]}",
        "vendor": "Acme Global Solutions",
        "contract_type": "MSA",
        "status": "active",
        "effective_date": "2026-01-01",
        "expiry_date": "2027-01-01",
        "contract_value": 250000.50,
        "currency": "USD",
        "risk_level": "medium",
        "has_auto_renewal": True,
        "page_count": 24,
        "file_name": "acme_msa_2026.pdf",
    }


class TestContractCRUD:
    """End-to-end CRUD tests for Contract API endpoints."""

    @pytest.mark.db
    def test_create_contract_success(
        self, test_client: TestClient, sample_contract_payload: dict, database_url
    ):
        """POST /contracts must create a contract and return 201 Created."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured — skipping live DB test")

        response = test_client.post("/contracts", json=sample_contract_payload)
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

        data = response.json()
        assert "id" in data
        assert uuid.UUID(data["id"])
        assert data["title"] == sample_contract_payload["title"]
        assert data["vendor"] == sample_contract_payload["vendor"]
        assert data["contract_type"] == "MSA"
        assert data["status"] == "active"
        assert float(data["contract_value"]) == 250000.50
        assert data["currency"] == "USD"
        assert data["has_auto_renewal"] is True
        assert data["processing_status"] == "pending"
        assert "created_at" in data
        assert "updated_at" in data

        # Cleanup
        test_client.delete(f"/contracts/{data['id']}")

    @pytest.mark.db
    def test_get_contract_by_id(
        self, test_client: TestClient, sample_contract_payload: dict, database_url
    ):
        """GET /contracts/{id} must retrieve the exact contract."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured — skipping live DB test")

        create_res = test_client.post("/contracts", json=sample_contract_payload)
        contract_id = create_res.json()["id"]

        get_res = test_client.get(f"/contracts/{contract_id}")
        assert get_res.status_code == 200
        data = get_res.json()
        assert data["id"] == contract_id
        assert data["title"] == sample_contract_payload["title"]

        # Cleanup
        test_client.delete(f"/contracts/{contract_id}")

    @pytest.mark.db
    def test_list_contracts_with_pagination(
        self, test_client: TestClient, sample_contract_payload: dict, database_url
    ):
        """GET /contracts must return paginated list with total count."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured — skipping live DB test")

        # Create a contract to ensure at least one exists
        create_res = test_client.post("/contracts", json=sample_contract_payload)
        contract_id = create_res.json()["id"]

        response = test_client.get("/contracts?limit=10&offset=0")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert isinstance(data["items"], list)
        assert data["total"] >= 1
        assert data["limit"] == 10
        assert data["offset"] == 0

        # Filter by vendor substring
        vendor_filter_res = test_client.get(f"/contracts?vendor=Acme+Global")
        assert vendor_filter_res.status_code == 200
        filtered_items = vendor_filter_res.json()["items"]
        assert any(item["id"] == contract_id for item in filtered_items)

        # Cleanup
        test_client.delete(f"/contracts/{contract_id}")

    @pytest.mark.db
    def test_update_contract_partial(
        self, test_client: TestClient, sample_contract_payload: dict, database_url
    ):
        """PATCH /contracts/{id} must update only the specified fields."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured — skipping live DB test")

        create_res = test_client.post("/contracts", json=sample_contract_payload)
        contract_id = create_res.json()["id"]

        update_payload = {
            "title": "Updated Contract Title",
            "risk_level": "critical",
            "status": "pending_review",
        }
        patch_res = test_client.patch(f"/contracts/{contract_id}", json=update_payload)
        assert patch_res.status_code == 200
        updated_data = patch_res.json()
        assert updated_data["title"] == "Updated Contract Title"
        assert updated_data["risk_level"] == "critical"
        assert updated_data["status"] == "pending_review"
        # Unchanged fields remain preserved
        assert updated_data["vendor"] == sample_contract_payload["vendor"]
        assert updated_data["contract_type"] == sample_contract_payload["contract_type"]

        # Cleanup
        test_client.delete(f"/contracts/{contract_id}")

    @pytest.mark.db
    def test_delete_contract(
        self, test_client: TestClient, sample_contract_payload: dict, database_url
    ):
        """DELETE /contracts/{id} must delete record; subsequent GET returns 404."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured — skipping live DB test")

        create_res = test_client.post("/contracts", json=sample_contract_payload)
        contract_id = create_res.json()["id"]

        del_res = test_client.delete(f"/contracts/{contract_id}")
        assert del_res.status_code == 204

        # Verify deletion
        get_res = test_client.get(f"/contracts/{contract_id}")
        assert get_res.status_code == 404

    @pytest.mark.db
    def test_api_v1_prefixed_route(
        self, test_client: TestClient, sample_contract_payload: dict, database_url
    ):
        """/api/v1/contracts route alias must function identically."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured — skipping live DB test")

        create_res = test_client.post("/api/v1/contracts", json=sample_contract_payload)
        assert create_res.status_code == 201
        contract_id = create_res.json()["id"]

        get_res = test_client.get(f"/api/v1/contracts/{contract_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == contract_id

        # Cleanup
        test_client.delete(f"/api/v1/contracts/{contract_id}")


class TestContractErrorHandling:
    """Negative testing and validation error handling."""

    def test_get_nonexistent_contract_returns_404(
        self, test_client: TestClient, database_url
    ):
        """Requesting a non-existent UUID must return 404 Not Found."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured — skipping live DB test")

        random_id = uuid.uuid4()
        response = test_client.get(f"/contracts/{random_id}")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_patch_nonexistent_contract_returns_404(
        self, test_client: TestClient, database_url
    ):
        """Patching a non-existent UUID must return 404 Not Found."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured — skipping live DB test")

        random_id = uuid.uuid4()
        response = test_client.patch(
            f"/contracts/{random_id}", json={"title": "Doesn't exist"}
        )
        assert response.status_code == 404

    def test_delete_nonexistent_contract_returns_404(
        self, test_client: TestClient, database_url
    ):
        """Deleting a non-existent UUID must return 404 Not Found."""
        if not database_url:
            pytest.skip("DATABASE_URL not configured — skipping live DB test")

        random_id = uuid.uuid4()
        response = test_client.delete(f"/contracts/{random_id}")
        assert response.status_code == 404

    def test_invalid_uuid_returns_422(self, test_client: TestClient):
        """Malformed UUID string must be rejected by FastAPI with 422 Unprocessable Entity."""
        response = test_client.get("/contracts/not-a-valid-uuid")
        assert response.status_code == 422
        assert "detail" in response.json()

    def test_validation_rejects_empty_title(self, test_client: TestClient):
        """POST with empty title must be rejected with 422."""
        invalid_payload = {"title": ""}
        response = test_client.post("/contracts", json=invalid_payload)
        assert response.status_code == 422

    def test_validation_rejects_negative_value(self, test_client: TestClient):
        """POST with negative contract_value must be rejected with 422."""
        invalid_payload = {"title": "Valid Title", "contract_value": -500.00}
        response = test_client.post("/contracts", json=invalid_payload)
        assert response.status_code == 422
