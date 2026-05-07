"""JSON file persistence for todos and notes."""

import json
import os
import time
from pathlib import Path
from typing import Optional


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _ensure_data_dir():
    """Create data directory if it doesn't exist."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_json(filename: str) -> dict:
    """Read a JSON file, return empty dict if missing or corrupt."""
    _ensure_data_dir()
    path = DATA_DIR / filename
    if not path.exists():
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _write_json(filename: str, data: dict):
    """Write a dictionary to a JSON file."""
    _ensure_data_dir()
    path = DATA_DIR / filename
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --- Todos ---

def get_todos() -> list:
    """Return all todos, sorted by creation time (oldest first)."""
    data = _read_json("todos.json")
    items = list(data.values())
    items.sort(key=lambda t: t.get("created_at", 0))
    return items


def add_todo(text: str) -> dict:
    """Add a new todo item. Returns the created item."""
    data = _read_json("todos.json")
    todo_id = str(int(time.time() * 1_000_000))
    item = {
        "id": todo_id,
        "text": text.strip(),
        "completed": False,
        "created_at": time.time(),
    }
    data[todo_id] = item
    _write_json("todos.json", data)
    return item


def toggle_todo(todo_id: str) -> Optional[dict]:
    """Toggle a todo's completed status. Returns the updated item or None."""
    data = _read_json("todos.json")
    if todo_id not in data:
        return None
    data[todo_id]["completed"] = not data[todo_id]["completed"]
    _write_json("todos.json", data)
    return data[todo_id]


def delete_todo(todo_id: str) -> bool:
    """Delete a todo by ID. Returns True if deleted, False if not found."""
    data = _read_json("todos.json")
    if todo_id not in data:
        return False
    del data[todo_id]
    _write_json("todos.json", data)
    return True


# --- Notes ---

def get_notes() -> list:
    """Return all notes, sorted by creation time (newest first)."""
    data = _read_json("notes.json")
    items = list(data.values())
    items.sort(key=lambda n: n.get("created_at", 0), reverse=True)
    return items


def add_note(title: str, content: str) -> dict:
    """Save a new note. Returns the created note."""
    data = _read_json("notes.json")
    note_id = str(int(time.time() * 1_000_000))
    item = {
        "id": note_id,
        "title": title.strip(),
        "content": content.strip(),
        "created_at": time.time(),
    }
    data[note_id] = item
    _write_json("notes.json", data)
    return item


def delete_note(note_id: str) -> bool:
    """Delete a note by ID. Returns True if deleted, False if not found."""
    data = _read_json("notes.json")
    if note_id not in data:
        return False
    del data[note_id]
    _write_json("notes.json", data)
    return True
