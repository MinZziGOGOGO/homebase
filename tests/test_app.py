"""Tests for the FastAPI app."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from homebase.main import app


@pytest_asyncio.fixture
async def client():
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
async def test_manifest_content_type(client):
    resp = await client.get("/static/manifest.json")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/manifest+json")


@pytest.mark.asyncio
async def test_config_defaults_disable_integrations(client):
    resp = await client.get("/api/config")
    assert resp.status_code == 200
    cfg = resp.json()
    assert cfg["city"] == "Vienna"
    assert cfg["minecraft"] is False
    assert cfg["shorts"] is False
    assert cfg["notifications"] is False


@pytest.mark.asyncio
async def test_create_and_list_todos(client):
    resp = await client.post("/api/todos", json={"text": "Test todo"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["text"] == "Test todo"
    assert data["status"] == "todo"

    resp = await client.get("/api/todos")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_empty_todo_rejected(client):
    resp = await client.post("/api/todos", json={"text": "   "})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_todo_status(client):
    tid = (await client.post("/api/todos", json={"text": "Toggle me"})).json()["id"]

    resp = await client.patch(f"/api/todos/{tid}", json={"status": "done"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "done"

    resp = await client.patch(f"/api/todos/{tid}", json={"status": "todo"})
    assert resp.json()["status"] == "todo"


@pytest.mark.asyncio
async def test_update_todo_invalid_status(client):
    tid = (await client.post("/api/todos", json={"text": "x"})).json()["id"]
    resp = await client.patch(f"/api/todos/{tid}", json={"status": "nope"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_nonexistent_todo(client):
    resp = await client.patch("/api/todos/nonexistent", json={"status": "done"})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_todo(client):
    tid = (await client.post("/api/todos", json={"text": "Delete me"})).json()["id"]
    assert (await client.delete(f"/api/todos/{tid}")).status_code == 200
    assert (await client.delete(f"/api/todos/{tid}")).status_code == 404


@pytest.mark.asyncio
async def test_create_and_list_notes(client):
    resp = await client.post("/api/notes", json={"title": "Meeting", "content": "Discuss roadmap"})
    assert resp.status_code == 201
    assert resp.json()["title"] == "Meeting"

    resp = await client.get("/api/notes")
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_note(client):
    nid = (await client.post("/api/notes", json={"title": "Temp", "content": "Delete"})).json()["id"]
    assert (await client.delete(f"/api/notes/{nid}")).status_code == 200
    assert (await client.delete(f"/api/notes/{nid}")).status_code == 404


@pytest.mark.asyncio
async def test_disabled_integrations(client):
    assert (await client.get("/api/services")).json() == []
    assert (await client.get("/api/minecraft")).json()["online"] is False
    assert (await client.get("/api/notifications")).json() == []
    assert (await client.get("/api/shorts/stats")).status_code == 404


@pytest.mark.asyncio
async def test_search_empty_query(client):
    assert (await client.get("/api/search?q=")).json() == {"results": []}


@pytest.mark.asyncio
async def test_unknown_api_route_is_404(client):
    assert (await client.get("/api/does-not-exist")).status_code == 404


@pytest.mark.asyncio
async def test_spa_route_serves_frontend(client):
    resp = await client.get("/docker")
    assert resp.status_code == 200
    assert "Homebase" in resp.text


@pytest.mark.asyncio
async def test_weather_endpoint(client):
    """Weather is proxied from wttr.in; both success and a clean 502 are fine offline."""
    resp = await client.get("/api/weather")
    if resp.status_code == 200:
        assert "current_condition" in resp.json()
    else:
        assert resp.status_code == 502
