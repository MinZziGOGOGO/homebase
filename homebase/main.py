"""Homebase Dashboard — FastAPI backend."""

import asyncio
import json
import httpx
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import stats, storage

app = FastAPI(title="Homebase Dashboard")

# Serve static files (frontend)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """Serve the dashboard frontend."""
    return FileResponse(str(STATIC_DIR / "index.html"))


# --- Pydantic models ---

class TodoCreate(BaseModel):
    text: str
    status: str = "todo"


class TodoStatusUpdate(BaseModel):
    status: str


class TodoResponse(BaseModel):
    id: str
    text: str
    status: str
    created_at: float


class NoteCreate(BaseModel):
    title: str
    content: str


class NoteResponse(BaseModel):
    id: str
    title: str
    content: str
    created_at: float


# --- Todo API ---

@app.get("/api/todos", response_model=list[TodoResponse])
async def list_todos():
    """List all todos."""
    return storage.get_todos()


@app.post("/api/todos", response_model=TodoResponse, status_code=201)
async def create_todo(body: TodoCreate):
    """Add a new todo."""
    valid = body.status if body.status in storage.VALID_STATUSES else "todo"
    return storage.add_todo(body.text, valid)


@app.patch("/api/todos/{todo_id}", response_model=TodoResponse)
async def update_todo_status(todo_id: str, body: TodoStatusUpdate):
    """Update a todo's status (todo / in_progress / done)."""
    if body.status not in storage.VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Must be one of: {', '.join(storage.VALID_STATUSES)}",
        )
    result = storage.set_todo_status(todo_id, body.status)
    if result is None:
        raise HTTPException(status_code=404, detail="Todo not found")
    return result


@app.delete("/api/todos/{todo_id}")
async def remove_todo(todo_id: str):
    """Delete a todo."""
    ok = storage.delete_todo(todo_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Todo not found")
    return {"ok": True}


# --- Notes API ---

@app.get("/api/notes", response_model=list[NoteResponse])
async def list_notes():
    """List all notes."""
    return storage.get_notes()


@app.post("/api/notes", response_model=NoteResponse, status_code=201)
async def create_note(body: NoteCreate):
    """Save a new note."""
    return storage.add_note(body.title, body.content)


@app.delete("/api/notes/{note_id}")
async def remove_note(note_id: str):
    """Delete a note."""
    ok = storage.delete_note(note_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


# --- Weather proxy ---

@app.get("/api/weather")
async def get_weather(city: str = "Vienna"):
    """Proxy weather data from wttr.in. Returns JSON."""
    url = f"https://wttr.in/{city}?format=j1"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"Weather API error: {str(e)}")


# --- WebSocket for live stats ---

@app.websocket("/ws/stats")
async def websocket_stats(ws: WebSocket):
    """Push system stats every 5 seconds over WebSocket."""
    await ws.accept()
    try:
        while True:
            data = stats.get_all_stats()
            await ws.send_text(json.dumps(data))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass


# --- Services status ---

SERVICES = [
    {"name": "Nextcloud", "url": "http://localhost:8888", "icon": "☁️", "desc": "Self-hosted cloud storage"},
    {"name": "Kavita", "url": "http://localhost:5000", "icon": "📚", "desc": "Manga & book reader"},
    {"name": "code-server", "url": "http://localhost:8443", "icon": "💻", "desc": "VS Code in browser"},
    {"name": "Pi-hole", "url": "http://localhost:8085/admin", "icon": "🛡️", "desc": "Network ad blocker"},
    {"name": "Stirling-PDF", "url": "http://localhost:8093", "icon": "📄", "desc": "PDF editor & converter"},
    {"name": "Portainer", "url": "http://localhost:9000", "icon": "🐳", "desc": "Docker container manager"},
    {"name": "Vaultwarden", "url": "http://localhost:8094", "icon": "🔐", "desc": "Password manager"},
    {"name": "mindbase", "url": "http://localhost:8091", "icon": "🧠", "desc": "AI knowledge base"},
    {"name": "homebase", "url": "http://localhost:8080", "icon": "🏠", "desc": "System dashboard"},
    {"name": "arcadebase", "url": "http://localhost:8090", "icon": "🕹️", "desc": "Retro arcade games"},
    {"name": "learning-tracker", "url": "http://localhost:8091", "icon": "📖", "desc": "Learning progress tracker"},
    {"name": "hermes-dashboard", "url": "http://localhost:9119", "icon": "⚡", "desc": "AI agent dashboard"},
]


@app.get("/api/services")
async def get_services(request: Request):
    """Ping each service and return status. URLs use request hostname."""
    hostname = request.headers.get("host", "localhost").split(":")[0]
    results = []
    for svc in SERVICES:
        up = False
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                # Always ping localhost — services run on the same host
                resp = await client.get(svc["url"], follow_redirects=True)
                up = resp.status_code < 500
        except Exception:
            up = False
        # Rewrite URL to use the requesting hostname
        external_url = svc["url"].replace("localhost", hostname)
        results.append({**svc, "url": external_url, "up": up})
    return results
