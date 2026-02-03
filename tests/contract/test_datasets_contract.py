"""Contract tests for CSV upload endpoint (T047-T049).

Tests POST /datasets endpoint for CSV file upload per openapi.yaml.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
"""

from io import BytesIO
from typing import Any

from fastapi.testclient import TestClient
import pytest


@pytest.mark.contract
class TestDatasetsContract:
    """Contract tests for CSV upload endpoint (T047-T049)."""

    def test_upload_csv_success(self, client: TestClient) -> None:
        """Test POST /datasets with valid CSV returns 201 with dataset info (T047).

        Validates per openapi.yaml:
        - 201 status code
        - Response schema: Dataset with all fields
        - File uploaded and ingested
        - Metadata stored

        Success Criteria (T047):
        - Valid CSV returns 201
        - Dataset ID returned
        - Row count matches CSV
        """
        # Login first to get auth token
        login_response: Any = client.post("/auth/login", json={"username": "csvuser"})
        assert login_response.status_code == 200
        token: str = login_response.json()["access_token"]

        # Upload CSV file
        csv_content: bytes = b"id,name,price\n1,Product A,19.99\n2,Product B,29.99\n3,Product C,39.99\n"
        files: dict[str, tuple[str, BytesIO, str]] = {
            "file": ("products.csv", BytesIO(csv_content), "text/csv")
        }
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        response: Any = client.post("/datasets", files=files, headers=headers)

        # Verify 201 Created
        assert response.status_code == 201

        # Verify Dataset schema per openapi.yaml
        data: dict[str, Any] = response.json()
        assert "id" in data  # UUID
        assert "filename" in data
        assert "original_filename" in data
        assert "table_name" in data
        assert "uploaded_at" in data
        assert "row_count" in data
        assert "column_count" in data
        assert "file_size_bytes" in data
        assert "schema_json" in data

        # Verify data values
        assert data["filename"] == "products"
        assert data["original_filename"] == "products.csv"
        assert data["table_name"] == "products_data"
        assert data["row_count"] == 3
        assert data["column_count"] == 3

    def test_upload_csv_invalid_format(self, client: TestClient) -> None:
        """Test POST /datasets with invalid CSV returns 400 (T048).

        Validates per openapi.yaml:
        - 400 status code for invalid CSV format
        - Error response includes detail field

        Success Criteria (T048):
        - Malformed CSV returns 400
        - Error message describes issue
        """
        # Login first
        login_response: Any = client.post("/auth/login", json={"username": "csvuser2"})
        assert login_response.status_code == 200
        token: str = login_response.json()["access_token"]

        # Upload invalid CSV (binary data, not CSV)
        invalid_content: bytes = b"\x00\x01\x02\x03\x04\x05"
        files: dict[str, tuple[str, BytesIO, str]] = {
            "file": ("invalid.csv", BytesIO(invalid_content), "text/csv")
        }
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        response: Any = client.post("/datasets", files=files, headers=headers)

        # Verify 400 Bad Request
        assert response.status_code == 400

        # Verify error response
        data: dict[str, Any] = response.json()
        assert "detail" in data or "error" in data

    def test_upload_csv_filename_conflict(self, client: TestClient) -> None:
        """Test POST /datasets with duplicate filename returns 409 (T049).

        Validates per openapi.yaml:
        - 409 status code for filename conflict
        - FilenameConflictResponse schema with suggested_filename

        Success Criteria (T049):
        - Duplicate filename returns 409
        - Suggested filename with timestamp provided
        """
        # Login first
        login_response: Any = client.post("/auth/login", json={"username": "csvuser3"})
        assert login_response.status_code == 200
        token: str = login_response.json()["access_token"]

        csv_content: bytes = b"id,name\n1,Item A\n2,Item B\n"
        files: dict[str, tuple[str, BytesIO, str]] = {
            "file": ("sales.csv", BytesIO(csv_content), "text/csv")
        }
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # First upload - should succeed
        response1: Any = client.post("/datasets", files=files, headers=headers)
        assert response1.status_code == 201

        # Second upload with same filename - should conflict
        files2: dict[str, tuple[str, BytesIO, str]] = {
            "file": ("sales.csv", BytesIO(csv_content), "text/csv")
        }
        response2: Any = client.post("/datasets", files=files2, headers=headers)

        # Verify 409 Conflict
        assert response2.status_code == 409

        # Verify FilenameConflictResponse per openapi.yaml
        data: dict[str, Any] = response2.json()
        assert "error" in data
        assert data["error"] == "filename_conflict"
        assert "suggested_filename" in data
        assert data["suggested_filename"].startswith("sales_")

    def test_upload_csv_unauthorized(self, client: TestClient) -> None:
        """Test POST /datasets without auth returns 401 (T050).

        Validates per openapi.yaml:
        - 401 status code when no bearer token provided
        - Security requirement enforced

        Success Criteria (T050):
        - Request without token returns 401
        """
        csv_content: bytes = b"id,name\n1,Test\n"
        files: dict[str, tuple[str, BytesIO, str]] = {
            "file": ("test.csv", BytesIO(csv_content), "text/csv")
        }

        response: Any = client.post("/datasets", files=files)

        # Verify 401 Unauthorized
        assert response.status_code == 401
