"""Integration tests for job API endpoints."""
from fastapi.testclient import TestClient

from agentic_system.api.main import app


def test_health_check():
    """Test health check endpoint."""
    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint():
    """Test root endpoint."""
    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "service" in response.json()


def test_create_job_contract_only():
    """
    Test job creation API contract (without Celery worker).

    This tests that the endpoint accepts the correct input format
    and returns the expected response structure.
    """
    client = TestClient(app)

    # Test payload
    payload = {
        "agent_id": "simple_summarizer",
        "input": {
            "text": "This is a test text to summarize.",
            "max_words": 50,
        },
        "idempotency_key": "test-key-123",
    }

    response = client.post("/v1/jobs", json=payload)

    # Check response structure
    assert response.status_code == 200
    data = response.json()

    assert "job_id" in data
    assert "agent_id" in data
    assert "status" in data
    assert "trace_id" in data
    assert "created_at" in data
    assert "updated_at" in data

    assert data["agent_id"] == "simple_summarizer"
    assert data["status"] == "pending"

    # Save job_id for next test
    job_id = data["job_id"]

    # Test get job
    response = client.get(f"/v1/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["job_id"] == job_id


def test_get_job_not_found():
    """Test get job with non-existent job ID."""
    client = TestClient(app)
    response = client.get("/v1/jobs/non-existent-id")

    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_n8n_webhook_contract_only():
    """Test N8N webhook endpoint contract."""
    client = TestClient(app)

    payload = {
        "agent_id": "simple_summarizer",
        "input": {
            "text": "N8N webhook test text.",
            "max_words": 30,
        },
    }

    response = client.post("/v1/n8n/webhook", json=payload)

    assert response.status_code == 200
    data = response.json()

    assert "job_id" in data
    assert "status" in data
    assert "trace_id" in data
    assert data["status"] == "pending"


def test_job_idempotency():
    """Test that idempotency key prevents duplicate job creation."""
    client = TestClient(app)

    payload = {
        "agent_id": "simple_summarizer",
        "input": {
            "text": "Idempotency test.",
            "max_words": 20,
        },
        "idempotency_key": "idempotent-key-456",
    }

    # First request
    response1 = client.post("/v1/jobs", json=payload)
    assert response1.status_code == 200
    job_id_1 = response1.json()["job_id"]

    # Second request with same idempotency key
    response2 = client.post("/v1/jobs", json=payload)
    assert response2.status_code == 200
    job_id_2 = response2.json()["job_id"]

    # Should return the same job
    assert job_id_1 == job_id_2
