"""Load testing script for RAG CSV Crew system.

Success Criterion: SC-006 - System supports 10 concurrent users with <20%
performance degradation.

This script simulates 10 concurrent users performing typical operations:
- Login
- Upload CSV
- Submit queries
- View results
- Review history

Performance baseline is established with single user, then compared against
10 concurrent users to measure degradation.
"""

import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, Future
from pathlib import Path
from typing import Any

import requests

# Add backend to path
backend_dir: Path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_dir))


class LoadTestUser:
    """Simulates a single user's interactions with the system."""

    def __init__(self, user_id: int, base_url: str) -> None:
        """Initialize load test user.

        Args:
            user_id: Unique identifier for this user
            base_url: Base URL of the API (e.g., http://localhost:8000)
        """
        self.user_id: int = user_id
        self.base_url: str = base_url
        self.username: str = f"load_test_user_{user_id:02d}"
        self.token: str | None = None
        self.headers: dict[str, str] = {}
        self.session: requests.Session = requests.Session()
        self.metrics: dict[str, list[float]] = {
            "login": [],
            "upload": [],
            "query": [],
            "history": [],
        }

    def login(self) -> None:
        """Authenticate and obtain JWT token."""
        start_time: float = time.time()

        response: requests.Response = self.session.post(
            f"{self.base_url}/auth/login",
            json={"username": self.username},
            timeout=10,
        )
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        self.token = data["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

        elapsed: float = time.time() - start_time
        self.metrics["login"].append(elapsed)

    def upload_csv(self, csv_content: str, filename: str) -> str:
        """Upload a CSV file.

        Args:
            csv_content: CSV file content as string
            filename: Name of the CSV file

        Returns:
            Dataset ID of the uploaded file
        """
        start_time: float = time.time()

        # Create in-memory file for upload
        files: dict[str, tuple[str, str, str]] = {
            "file": (filename, csv_content, "text/csv")
        }

        response: requests.Response = self.session.post(
            f"{self.base_url}/datasets",
            files=files,
            headers=self.headers,
            timeout=30,
        )
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        dataset_id: str = data["id"]

        elapsed: float = time.time() - start_time
        self.metrics["upload"].append(elapsed)

        return dataset_id

    def submit_query(self, query_text: str, dataset_id: str) -> dict[str, Any]:
        """Submit a natural language query.

        Args:
            query_text: Natural language question
            dataset_id: ID of dataset to query

        Returns:
            Query response with ID and status
        """
        start_time: float = time.time()

        response: requests.Response = self.session.post(
            f"{self.base_url}/queries",
            json={"query_text": query_text, "dataset_ids": [dataset_id]},
            headers=self.headers,
            timeout=10,
        )
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        query_id: str = data["id"]

        # Poll for completion (with timeout)
        max_wait: int = 45
        poll_interval: float = 2.0
        waited: float = 0.0

        while waited < max_wait:
            time.sleep(poll_interval)
            waited += poll_interval

            poll_response: requests.Response = self.session.get(
                f"{self.base_url}/queries/{query_id}",
                headers=self.headers,
                timeout=10,
            )
            poll_response.raise_for_status()

            status_data: dict[str, Any] = poll_response.json()
            if status_data["status"] in ["completed", "failed", "cancelled"]:
                break

        elapsed: float = time.time() - start_time
        self.metrics["query"].append(elapsed)

        return status_data

    def get_query_history(self) -> list[dict[str, Any]]:
        """Retrieve query history.

        Returns:
            List of past queries
        """
        start_time: float = time.time()

        response: requests.Response = self.session.get(
            f"{self.base_url}/queries",
            headers=self.headers,
            timeout=10,
        )
        response.raise_for_status()

        data: dict[str, Any] = response.json()
        history: list[dict[str, Any]] = data.get("queries", [])

        elapsed: float = time.time() - start_time
        self.metrics["history"].append(elapsed)

        return history

    def run_scenario(self, csv_content: str, filename: str, query: str) -> None:
        """Execute a complete user scenario.

        Args:
            csv_content: CSV file content
            filename: CSV filename
            query: Natural language query to ask
        """
        try:
            # Step 1: Login
            self.login()
            print(f"  [User {self.user_id:02d}] Logged in as {self.username}")

            # Step 2: Upload CSV
            dataset_id: str = self.upload_csv(csv_content, filename)
            print(
                f"  [User {self.user_id:02d}] Uploaded {filename} (ID: {dataset_id[:8]}...)"
            )

            # Step 3: Submit query
            result: dict[str, Any] = self.submit_query(query, dataset_id)
            print(
                f"  [User {self.user_id:02d}] Query completed with status: {result['status']}"
            )

            # Step 4: Get history
            history: list[dict[str, Any]] = self.get_query_history()
            print(
                f"  [User {self.user_id:02d}] Retrieved history ({len(history)} queries)"
            )

        except Exception as e:
            print(f"  [User {self.user_id:02d}] ERROR: {e}")


# Sample CSV data for load testing
SAMPLE_CSV: str = """date,product,revenue,quantity
2024-01-15,Widget A,1500.00,50
2024-01-20,Widget B,2300.00,75
2024-01-22,Widget A,1200.00,40
2024-01-25,Widget C,3500.00,100
2024-01-28,Widget B,1800.00,60
"""

SAMPLE_QUERY: str = "What is the total revenue?"


def run_single_user_baseline(base_url: str) -> dict[str, float]:
    """Establish performance baseline with single user.

    Args:
        base_url: API base URL

    Returns:
        Average response times for each operation
    """
    print("\n=== BASELINE TEST (1 User) ===\n")

    user: LoadTestUser = LoadTestUser(user_id=0, base_url=base_url)

    # Run scenario 3 times to get average
    for i in range(3):
        print(f"Baseline run {i + 1}/3...")
        user.run_scenario(
            csv_content=SAMPLE_CSV,
            filename=f"baseline_test_{i}.csv",
            query=SAMPLE_QUERY,
        )
        time.sleep(2)  # Brief pause between runs

    # Calculate averages
    baseline: dict[str, float] = {
        "login": sum(user.metrics["login"]) / len(user.metrics["login"]),
        "upload": sum(user.metrics["upload"]) / len(user.metrics["upload"]),
        "query": sum(user.metrics["query"]) / len(user.metrics["query"]),
        "history": sum(user.metrics["history"]) / len(user.metrics["history"]),
    }

    print("\n--- Baseline Results ---")
    for operation, avg_time in baseline.items():
        print(f"{operation.capitalize()}: {avg_time:.2f}s")

    return baseline


def run_concurrent_users(base_url: str, num_users: int) -> dict[str, list[float]]:
    """Run load test with multiple concurrent users.

    Args:
        base_url: API base URL
        num_users: Number of concurrent users to simulate

    Returns:
        All response times for each operation
    """
    print(f"\n=== LOAD TEST ({num_users} Concurrent Users) ===\n")

    users: list[LoadTestUser] = [
        LoadTestUser(user_id=i, base_url=base_url) for i in range(1, num_users + 1)
    ]

    # Run all users concurrently
    with ThreadPoolExecutor(max_workers=num_users) as executor:
        futures: list[Future[None]] = []
        for user in users:
            future: Future[None] = executor.submit(
                user.run_scenario,
                csv_content=SAMPLE_CSV,
                filename=f"load_test_user_{user.user_id}.csv",
                query=SAMPLE_QUERY,
            )
            futures.append(future)

        # Wait for all to complete
        for future in futures:
            future.result()

    # Aggregate all metrics
    aggregated: dict[str, list[float]] = {
        "login": [],
        "upload": [],
        "query": [],
        "history": [],
    }

    for user in users:
        for operation in aggregated:
            aggregated[operation].extend(user.metrics[operation])

    return aggregated


def calculate_degradation(
    baseline: dict[str, float], load_test: dict[str, list[float]]
) -> dict[str, dict[str, float]]:
    """Calculate performance degradation percentage.

    Args:
        baseline: Single user average response times
        load_test: Concurrent users response times

    Returns:
        Performance metrics with degradation percentages
    """
    results: dict[str, dict[str, float]] = {}

    for operation in baseline:
        avg_time: float = sum(load_test[operation]) / len(load_test[operation])
        degradation: float = ((avg_time - baseline[operation]) / baseline[operation]) * 100

        results[operation] = {
            "baseline_avg": baseline[operation],
            "load_avg": avg_time,
            "degradation_pct": degradation,
        }

    return results


def main() -> None:
    """Execute load test and validate SC-006."""
    print("=== RAG CSV Crew Load Test ===")
    print("Success Criterion: SC-006 - <20% degradation with 10 concurrent users\n")

    # Configuration
    base_url: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    num_concurrent_users: int = 10

    print(f"API URL: {base_url}")
    print(f"Concurrent Users: {num_concurrent_users}\n")

    # Check if API is accessible
    try:
        response: requests.Response = requests.get(
            f"{base_url}/health", timeout=5
        )
        response.raise_for_status()
        print("✓ API is accessible\n")
    except requests.RequestException as e:
        print(f"✗ API is not accessible: {e}")
        print("\nPlease ensure:")
        print("1. Backend server is running (cd backend && uvicorn src.main:app)")
        print("2. Database is running (docker-compose up -d)")
        sys.exit(1)

    # Step 1: Establish baseline
    baseline: dict[str, float] = run_single_user_baseline(base_url)

    # Step 2: Run load test
    load_test_metrics: dict[str, list[float]] = run_concurrent_users(
        base_url, num_concurrent_users
    )

    # Step 3: Calculate degradation
    results: dict[str, dict[str, float]] = calculate_degradation(
        baseline, load_test_metrics
    )

    # Step 4: Report results
    print("\n=== PERFORMANCE DEGRADATION ANALYSIS ===\n")

    max_degradation: float = 0.0
    failed_operations: list[str] = []

    for operation, metrics in results.items():
        print(f"{operation.upper()}:")
        print(f"  Baseline (1 user):  {metrics['baseline_avg']:.2f}s")
        print(f"  Load ({num_concurrent_users} users):    {metrics['load_avg']:.2f}s")
        print(f"  Degradation:        {metrics['degradation_pct']:.1f}%")

        if metrics["degradation_pct"] > max_degradation:
            max_degradation = metrics["degradation_pct"]

        if metrics["degradation_pct"] > 20.0:
            failed_operations.append(operation)
            print("  Status:             ✗ FAIL (>20% degradation)")
        else:
            print("  Status:             ✓ PASS (<20% degradation)")

        print()

    # Final verdict
    print("=== FINAL VERDICT ===\n")
    print(f"Maximum Degradation: {max_degradation:.1f}%")
    print(f"SC-006 Threshold: 20.0%")

    if not failed_operations:
        print("\n✓ SUCCESS: All operations meet SC-006 requirements (<20% degradation)")
        print(f"   System supports {num_concurrent_users} concurrent users with acceptable performance")
    else:
        print(f"\n✗ FAILURE: {len(failed_operations)} operation(s) exceed 20% degradation:")
        for operation in failed_operations:
            print(f"   - {operation}: {results[operation]['degradation_pct']:.1f}%")
        print("\nRecommendations:")
        print("- Review database connection pool size")
        print("- Optimize slow queries with EXPLAIN ANALYZE")
        print("- Consider caching frequently accessed data")
        print("- Profile CrewAI agent execution time")


if __name__ == "__main__":
    main()
