from fastapi.testclient import TestClient
from main import app
import pytest

client = TestClient(app)

def test_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "DocuTrust API is running."}

def test_upload_invalid_file():
    # Attempting to upload a txt file instead of a PDF
    files = {'file': ('test.txt', b'this is a test text', 'text/plain')}
    response = client.post("/upload", files=files)
    assert response.status_code == 400
    assert "Only PDF files are supported" in response.json()["detail"]

def test_query_endpoint_structure():
    # We won't fully execute the SSE stream in a simple sync test, 
    # but we can verify the endpoint accepts the correct payload.
    response = client.post("/query", json={"query": "What is the policy?"})
    assert response.status_code == 200
    # The content type should be text/event-stream for SSE
    assert "text/event-stream" in response.headers.get("content-type", "")
