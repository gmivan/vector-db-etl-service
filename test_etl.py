import os
import json
import time
import random
import asyncio
import aiohttp
import pytest
import numpy as np
import requests
import dotenv
from typing import List, Dict, Any

# Load environment variables
dotenv.load_dotenv()

# Test data
test_embedding_existing = [0.00714385649189353, -0.013157407753169537, -0.017787616699934006]
test_embedding_existing_2 = [0.009175444021821022, -0.00456630764529109, 0.0018208998953923583]
test_embedding_new = [random.uniform(-1, 1) for _ in range(3)]

# Test fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def http_session():
    """Create an aiohttp session for the test session."""
    async with aiohttp.ClientSession() as session:
        yield session

@pytest.fixture(scope="function")
async def clean_index():
    """Ensure the index is clean before each test."""
    # Delete all documents
    url = f"{API_URL}/delete_all"
    async with aiohttp.ClientSession() as session:
        async with session.post(url) as response:
            assert response.status == 200
    yield

# API Tests
async def test_health_check():
    """Test the health check endpoint."""
    url = f"{API_URL}/health"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            assert response.status == 200
            data = await response.json()
            assert data["status"] == "ok"

@pytest.mark.asyncio
async def test_add_document(clean_index, http_session):
    """Test adding a single document."""
    url = f"{API_URL}/add"
    payload = {
        "id": "test_doc_1",
        "embedding": test_embedding_existing,
        "metadata": {"text": "test document 1"}
    }
    
    async with http_session.post(url, json=payload) as response:
        assert response.status == 200
        data = await response.json()
        assert data["status"] == "success"

@pytest.mark.asyncio
async def test_bulk_add_documents(clean_index, http_session):
    """Test adding multiple documents in bulk."""
    url = f"{API_URL}/bulk_add"
    documents = [
        {
            "id": f"test_doc_{i}",
            "embedding": [random.uniform(-1, 1) for _ in range(3)],
            "metadata": {"text": f"test document {i}"}
        }
        for i in range(5)
    ]
    
    async with http_session.post(url, json={"documents": documents}) as response:
        assert response.status == 200
        data = await response.json()
        assert data["status"] == "success"
        assert data["inserted_count"] == 5

@pytest.mark.asyncio
async def test_get_similarity_scores(clean_index, http_session):
    """Test getting similarity scores for documents."""
    # First add some test documents
    add_url = f"{API_URL}/add"
    docs = [
        {"id": "doc1", "embedding": test_embedding_existing, "metadata": {"text": "doc1"}},
        {"id": "doc2", "embedding": test_embedding_existing_2, "metadata": {"text": "doc2"}}
    ]
    
    for doc in docs:
        async with http_session.post(add_url, json=doc) as response:
            assert response.status == 200
    
    # Test similarity scores
    url = f"{API_URL}/get_similarity_scores"
    payload = {
        "embedding": test_embedding_new,
        "k": 2
    }
    
    async with http_session.post(url, json=payload) as response:
        assert response.status == 200
        data = await response.json()
        assert "results" in data
        assert len(data["results"]) <= 2
        for result in data["results"]:
            assert "id" in result
            assert "score" in result
            assert "metadata" in result

@pytest.mark.asyncio
async def test_delete_document(clean_index, http_session):
    """Test deleting a document."""
    # First add a document
    doc_id = "test_delete_doc"
    add_url = f"{API_URL}/add"
    doc = {
        "id": doc_id,
        "embedding": test_embedding_existing,
        "metadata": {"text": "test delete document"}
    }
    
    async with http_session.post(add_url, json=doc) as response:
        assert response.status == 200
    
    # Delete the document
    delete_url = f"{API_URL}/delete"
    async with http_session.post(delete_url, json={"id": doc_id}) as response:
        assert response.status == 200
        data = await response.json()
        assert data["status"] == "success"

@pytest.mark.asyncio
async def test_delete_all(clean_index, http_session):
    """Test deleting all documents."""
    # First add some documents
    docs = [
        {"id": f"doc{i}", "embedding": test_embedding_existing, "metadata": {"text": f"doc{i}"}}
        for i in range(3)
    ]
    
    for doc in docs:
        async with http_session.post(f"{API_URL}/add", json=doc) as response:
            assert response.status == 200
    
    # Delete all documents
    async with http_session.post(f"{API_URL}/delete_all") as response:
        assert response.status == 200
        data = await response.json()
        assert data["status"] == "success"
    
    # Verify documents are deleted by trying to get similarity scores
    payload = {"embedding": test_embedding_new, "k": 10}
    async with http_session.post(f"{API_URL}/get_similarity_scores", json=payload) as response:
        assert response.status == 200
        data = await response.json()
        assert len(data["results"]) == 0 
