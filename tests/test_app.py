"""Tests for FastAPI app."""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from homebase.main import app


@pytest_asyncio.fixture
async def client():
    """Async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_root_returns_html(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Homebase" in resp.text


@pytest.mark.asyncio
async def test_create_and_list_todos(client):
    resp = await client.post("/api/todos", json={"text": "Test todo"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["text"] == "Test todo"
    assert data["completed"] is False
    assert "id" in data

    resp = await client.get("/api/todos")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_toggle_todo(client):
    resp = await client.post("/api/todos", json={"text": "Toggle me"})
    tid = resp.json()["id"]

    resp = await client.put(f"/api/todos/{tid}")
    assert resp.status_code == 200
    assert resp.json()["completed"] is True

    resp = await client.put(f"/api/todos/{tid}")
    assert resp.json()["completed"] is False


@pytest.mark.asyncio
async def test_toggle_nonexistent_todo(client):
    resp = await client.put("/api/todos/nonexistent")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_todo(client):
    resp = await client.post("/api/todos", json={"text": "Delete me"})
    tid = resp.json()["id"]

    resp = await client.delete(f"/api/todos/{tid}")
    assert resp.status_code == 200

    resp = await client.delete(f"/api/todos/{tid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_create_and_list_notes(client):
    resp = await client.post("/api/notes", json={
        "title": "Meeting", "content": "Discuss roadmap"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "Meeting"

    resp = await client.get("/api/notes")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_note(client):
    resp = await client.post("/api/notes", json={
        "title": "Temp", "content": "Delete"
    })
    nid = resp.json()["id"]

    resp = await client.delete(f"/api/notes/{nid}")
    assert resp.status_code == 200

    resp = await client.delete(f"/api/notes/{nid}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_weather_endpoint(client):
    """Test that weather endpoint returns JSON (requires internet)."""
    resp = await client.get("/api/weather?city=Vienna")
    # wttr.in might be reachable or not; both are OK in test
    if resp.status_code == 200:
        data = resp.json()
        assert "current_condition" in data
    else:
        assert resp.status_code == 502
