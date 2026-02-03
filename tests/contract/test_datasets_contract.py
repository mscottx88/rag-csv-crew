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

    def test_list_datasets_success(self, client: TestClient) -> None:
        """Test GET /datasets returns paginated list of datasets (T048).

        Validates per openapi.yaml:
        - 200 status code
        - DatasetList schema with datasets array, total_count, page, page_size
        - Pagination parameters work correctly

        Success Criteria (T048):
        - Returns list of user's datasets
        - Pagination metadata included
        - Only returns datasets for current user
        """
        # Login first
        login_response: Any = client.post("/auth/login", json={"username": "listuser"})
        assert login_response.status_code == 200
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Upload a couple of test datasets first
        for i in range(2):
            csv_content: bytes = f"id,value\n1,Test{i}\n".encode()
            files: dict[str, tuple[str, BytesIO, str]] = {
                "file": (f"test{i}.csv", BytesIO(csv_content), "text/csv")
            }
            response: Any = client.post("/datasets", files=files, headers=headers)
            assert response.status_code == 201

        # Now test GET /datasets
        response: Any = client.get("/datasets", headers=headers)

        # Verify 200 OK
        assert response.status_code == 200

        # Verify DatasetList schema
        data: dict[str, Any] = response.json()
        assert "datasets" in data
        assert "total_count" in data
        assert "page" in data
        assert "page_size" in data

        # Verify datasets array contains Dataset objects
        assert isinstance(data["datasets"], list)
        assert data["total_count"] >= 2  # At least the 2 we uploaded

        # Verify each dataset has required fields
        if len(data["datasets"]) > 0:
            dataset: dict[str, Any] = data["datasets"][0]
            assert "id" in dataset
            assert "filename" in dataset
            assert "uploaded_at" in dataset
            assert "row_count" in dataset

    def test_list_datasets_pagination(self, client: TestClient) -> None:
        """Test GET /datasets with pagination parameters (T048).

        Validates:
        - page and page_size query parameters work
        - Pagination metadata correct
        """
        login_response: Any = client.post("/auth/login", json={"username": "pageuser"})
        assert login_response.status_code == 200
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Test with pagination parameters
        response: Any = client.get("/datasets?page=1&page_size=10", headers=headers)

        assert response.status_code == 200
        data: dict[str, Any] = response.json()
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_list_datasets_unauthorized(self, client: TestClient) -> None:
        """Test GET /datasets without auth returns 401 (T048).

        Success Criteria:
        - Request without token returns 401
        """
        response: Any = client.get("/datasets")
        assert response.status_code == 401

    def test_get_dataset_by_id_success(self, client: TestClient) -> None:
        """Test GET /datasets/{dataset_id} returns single dataset (T049).

        Validates per openapi.yaml:
        - 200 status code
        - Dataset schema with all fields
        - Returns correct dataset by ID

        Success Criteria (T049):
        - Returns full dataset metadata
        - Includes schema information
        """
        # Login and upload a dataset
        login_response: Any = client.post("/auth/login", json={"username": "getuser"})
        assert login_response.status_code == 200
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        csv_content: bytes = b"id,name\n1,Test\n2,Test2\n"
        files: dict[str, tuple[str, BytesIO, str]] = {
            "file": ("gettest.csv", BytesIO(csv_content), "text/csv")
        }
        upload_response: Any = client.post("/datasets", files=files, headers=headers)
        assert upload_response.status_code == 201
        dataset_id: str = upload_response.json()["id"]

        # Now test GET /datasets/{id}
        response: Any = client.get(f"/datasets/{dataset_id}", headers=headers)

        # Verify 200 OK
        assert response.status_code == 200

        # Verify Dataset schema
        data: dict[str, Any] = response.json()
        assert data["id"] == dataset_id
        assert data["filename"] == "gettest"
        assert data["row_count"] == 2
        assert data["column_count"] == 2
        assert "schema_json" in data
        assert isinstance(data["schema_json"], list)

    def test_get_dataset_not_found(self, client: TestClient) -> None:
        """Test GET /datasets/{dataset_id} with invalid ID returns 404 (T049).

        Success Criteria:
        - Invalid UUID returns 404
        - Error message included
        """
        login_response: Any = client.post("/auth/login", json={"username": "getuser2"})
        assert login_response.status_code == 200
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Try to get non-existent dataset
        fake_id: str = "00000000-0000-0000-0000-000000000000"
        response: Any = client.get(f"/datasets/{fake_id}", headers=headers)

        assert response.status_code == 404
        data: dict[str, Any] = response.json()
        assert "detail" in data or "error" in data

    def test_get_dataset_unauthorized(self, client: TestClient) -> None:
        """Test GET /datasets/{dataset_id} without auth returns 401 (T049).

        Success Criteria:
        - Request without token returns 401
        """
        fake_id: str = "00000000-0000-0000-0000-000000000000"
        response: Any = client.get(f"/datasets/{fake_id}")
        assert response.status_code == 401

    def test_delete_dataset_success(self, client: TestClient) -> None:
        """Test DELETE /datasets/{dataset_id} removes dataset (T050).

        Validates per openapi.yaml:
        - 204 status code (No Content)
        - Dataset and associated data deleted
        - Subsequent GET returns 404

        Success Criteria (T050):
        - Successful deletion returns 204
        - Dataset no longer accessible
        - Associated table dropped
        """
        # Login and upload a dataset
        login_response: Any = client.post("/auth/login", json={"username": "deluser"})
        assert login_response.status_code == 200
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        csv_content: bytes = b"id,name\n1,Delete Me\n"
        files: dict[str, tuple[str, BytesIO, str]] = {
            "file": ("delete_me.csv", BytesIO(csv_content), "text/csv")
        }
        upload_response: Any = client.post("/datasets", files=files, headers=headers)
        assert upload_response.status_code == 201
        dataset_id: str = upload_response.json()["id"]

        # Delete the dataset
        response: Any = client.delete(f"/datasets/{dataset_id}", headers=headers)

        # Verify 204 No Content
        assert response.status_code == 204

        # Verify dataset no longer exists
        get_response: Any = client.get(f"/datasets/{dataset_id}", headers=headers)
        assert get_response.status_code == 404

    def test_delete_dataset_not_found(self, client: TestClient) -> None:
        """Test DELETE /datasets/{dataset_id} with invalid ID returns 404 (T050).

        Success Criteria:
        - Invalid UUID returns 404
        """
        login_response: Any = client.post("/auth/login", json={"username": "deluser2"})
        assert login_response.status_code == 200
        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        fake_id: str = "00000000-0000-0000-0000-000000000000"
        response: Any = client.delete(f"/datasets/{fake_id}", headers=headers)

        assert response.status_code == 404
        data: dict[str, Any] = response.json()
        assert "detail" in data or "error" in data

    def test_delete_dataset_unauthorized(self, client: TestClient) -> None:
        """Test DELETE /datasets/{dataset_id} without auth returns 401 (T050).

        Success Criteria:
        - Request without token returns 401
        """
        fake_id: str = "00000000-0000-0000-0000-000000000000"
        response: Any = client.delete(f"/datasets/{fake_id}")
        assert response.status_code == 401
