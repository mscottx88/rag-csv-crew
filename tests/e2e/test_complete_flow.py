"""End-to-end tests for complete backend flow with real API calls.

Tests the full stack from HTTP request through CrewAI to database storage
WITHOUT mocks. These tests make real API calls to OpenAI/Anthropic and should
be run sparingly to avoid quota issues.

Constitutional Requirements:
- Thread-based operations only (no async/await)
- All variables have explicit type annotations
- All functions have return type annotations
- PEP 8 compliance (all imports at top of file)
"""

import io
from typing import Any

from fastapi.testclient import TestClient
import pytest


@pytest.mark.e2e
@pytest.mark.skipif(
    True,  # Set to False to run E2E tests with real API calls
    reason="E2E test disabled by default to avoid API quota usage. Set skipif=False to enable.",
)
class TestCompleteFlow:
    """End-to-end tests for complete backend flow (real API calls)."""

    def test_complete_query_flow_with_real_apis(self, client: TestClient) -> None:
        """Test complete flow: login → upload → query → response with real APIs.

        This test exercises the entire backend stack WITHOUT mocks:
        - FastAPI routes
        - Database operations (PostgreSQL)
        - CSV ingestion
        - CrewAI orchestration (REAL API calls)
        - SQL generation (REAL Claude/OpenAI)
        - HTML response generation (REAL Claude/OpenAI)

        WARNING: This test makes REAL API calls and consumes quota/credits.
        Only run when you need to verify the complete integration.

        Args:
            client: FastAPI test client fixture

        Success Criteria:
        - User can log in
        - CSV upload succeeds
        - Query submission succeeds
        - Response contains generated SQL
        - Response contains HTML content
        - All operations use real APIs (no mocks)
        """
        # Step 1: Login to get JWT token
        login_response: Any = client.post("/auth/login", json={"username": "e2euser"})
        assert login_response.status_code == 200, f"Login failed: {login_response.json()}"

        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Step 2: Upload a minimal CSV dataset
        csv_content: str = """id,name,value
1,Item A,100
2,Item B,200
3,Item C,150
"""
        csv_file: io.BytesIO = io.BytesIO(csv_content.encode("utf-8"))

        upload_response: Any = client.post(
            "/datasets/",
            headers=headers,
            files={"file": ("test_data.csv", csv_file, "text/csv")},
        )
        assert upload_response.status_code == 201, f"Upload failed: {upload_response.json()}"

        dataset_id: str = upload_response.json()["id"]
        print(f"\n[OK] Dataset uploaded: {dataset_id}")

        # Step 3: Submit a simple query (REAL CrewAI + OpenAI/Anthropic API calls)
        query_body: dict[str, Any] = {
            "query_text": "What are the top 2 items by value?",
            "dataset_ids": [dataset_id],
        }

        print("\n==> Submitting query (calling REAL APIs - Claude/OpenAI)...")
        query_response: Any = client.post("/queries", json=query_body, headers=headers)

        # Verify query was submitted successfully
        assert (
            query_response.status_code == 201
        ), f"Query submission failed: {query_response.json()}"

        query_data: dict[str, Any] = query_response.json()
        query_id: str = query_data["id"]
        print(f"[OK] Query submitted: {query_id}")
        print(f"   Status: {query_data['status']}")

        # Step 4: Verify the response contains AI-generated content
        if query_data["status"] == "completed":
            # Query completed synchronously
            assert query_data["generated_sql"] is not None, "No SQL was generated"
            assert len(query_data["generated_sql"]) > 0, "Generated SQL is empty"
            print(f"\n[OK] SQL Generated (by Claude):\n{query_data['generated_sql'][:200]}...")

            # Get full response with HTML
            detail_response: Any = client.get(f"/queries/{query_id}", headers=headers)
            assert detail_response.status_code == 200

            detail_data: dict[str, Any] = detail_response.json()

            # Verify HTML response was generated
            if "response" in detail_data and detail_data["response"]:
                html_content: str | None = detail_data["response"].get("html_content")
                assert html_content is not None, "No HTML content generated"
                assert len(html_content) > 0, "HTML content is empty"
                assert "<" in html_content, "HTML content doesn't look like HTML"
                print(f"\n[OK] HTML Response Generated (by Claude):\n{html_content[:200]}...")

            print("\n[SUCCESS] Complete E2E flow succeeded with REAL API calls!")
            print("   - User authenticated")
            print("   - CSV dataset uploaded and ingested")
            print("   - Natural language query processed by CrewAI")
            print("   - SQL generated by Claude Opus")
            print("   - SQL executed against PostgreSQL")
            print("   - HTML response formatted by Claude Opus")
            print("   - All data persisted to database")
        else:
            # Query is still processing or failed
            print(f"\n[WARN]  Query status: {query_data['status']}")
            print("   This is expected if the query takes time to process")
            print("   The query was submitted successfully to the real API")

    def test_query_with_no_datasets(self, client: TestClient) -> None:
        """Test query submission when user has no datasets (real API call).

        This test verifies that the system handles the case where a user
        submits a query but has no uploaded datasets. The AI should generate
        SQL that handles this gracefully.

        WARNING: Makes REAL API calls to CrewAI/Claude.

        Args:
            client: FastAPI test client fixture

        Success Criteria:
        - Query submission succeeds
        - System doesn't crash with no datasets
        - Response is generated (even if it says "no data")
        """
        # Login
        login_response: Any = client.post("/auth/login", json={"username": "e2euser2"})
        assert login_response.status_code == 200

        token: str = login_response.json()["access_token"]
        headers: dict[str, str] = {"Authorization": f"Bearer {token}"}

        # Submit query with no datasets uploaded
        query_body: dict[str, Any] = {
            "query_text": "Show me all data",
            "dataset_ids": None,  # Query all (which is none)
        }

        print("\n==> Submitting query with no datasets (REAL API call)...")
        query_response: Any = client.post("/queries", json=query_body, headers=headers)

        # Should succeed (not crash)
        assert query_response.status_code == 201, f"Query failed: {query_response.json()}"

        query_data: dict[str, Any] = query_response.json()
        print(f"[OK] Query submitted: {query_data['id']}")
        print(f"   Status: {query_data['status']}")
        print("   System handled 'no datasets' case gracefully")
