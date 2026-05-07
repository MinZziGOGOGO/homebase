"""Tests for storage module."""

import os
import json
import pytest
from pathlib import Path
from homebase import storage


@pytest.fixture(autouse=True)
def clean_data():
    """Remove test data files before and after each test."""
    for fn in ["todos.json", "notes.json"]:
        p = storage.DATA_DIR / fn
        if p.exists():
            p.unlink()
    yield
    for fn in ["todos.json", "notes.json"]:
        p = storage.DATA_DIR / fn
        if p.exists():
            p.unlink()


def test_add_and_get_todos():
    storage.add_todo("Buy milk")
    storage.add_todo("Walk dog")
    todos = storage.get_todos()
    assert len(todos) == 2
    assert todos[0]["text"] == "Buy milk"
    assert todos[1]["text"] == "Walk dog"
    assert todos[0]["completed"] is False


def test_toggle_todo():
    item = storage.add_todo("Test task")
    tid = item["id"]
    assert item["completed"] is False
    updated = storage.toggle_todo(tid)
    assert updated["completed"] is True
    updated = storage.toggle_todo(tid)
    assert updated["completed"] is False


def test_toggle_todo_missing():
    result = storage.toggle_todo("nonexistent")
    assert result is None


def test_delete_todo():
    item = storage.add_todo("Delete me")
    tid = item["id"]
    assert storage.delete_todo(tid) is True
    assert storage.delete_todo(tid) is False
    assert len(storage.get_todos()) == 0


def test_add_and_get_notes():
    storage.add_note("Meeting", "Discuss Q2 goals")
    storage.add_note("Shopping", "Apples, bread")
    notes = storage.get_notes()
    assert len(notes) == 2
    # newest first
    assert notes[0]["title"] == "Shopping"
    assert notes[1]["title"] == "Meeting"


def test_delete_note():
    item = storage.add_note("Temp", "Content")
    nid = item["id"]
    assert storage.delete_note(nid) is True
    assert storage.delete_note(nid) is False


def test_empty_todos_returns_list():
    assert storage.get_todos() == []


def test_empty_notes_returns_list():
    assert storage.get_notes() == []


def test_strip_whitespace():
    item = storage.add_todo("   trimmed   ")
    assert item["text"] == "trimmed"
