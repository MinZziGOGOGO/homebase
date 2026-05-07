"""Homebase Dashboard — FastAPI backend."""

import asyncio
import json
import httpx
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
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


class TodoResponse(BaseModel):
    id: str
    text: str
    completed: bool
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
    return storage.add_todo(body.text)


@app.put("/api/todos/{todo_id}", response_model=TodoResponse)
async def toggle_todo(todo_id: str):
    """Toggle completion status of a todo."""
    result = storage.toggle_todo(todo_id)
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
