"""Tests for storage module."""

import json

from homebase import storage


def test_add_and_get_todos():
    storage.add_todo("Buy milk")
    storage.add_todo("Walk dog")
    todos = storage.get_todos()
    assert [t["text"] for t in todos] == ["Buy milk", "Walk dog"]
    assert todos[0]["status"] == "todo"


def test_add_todo_with_status():
    item = storage.add_todo("Write README", "in_progress")
    assert item["status"] == "in_progress"


def test_invalid_status_falls_back_to_todo():
    item = storage.add_todo("Odd", "whatever")
    assert item["status"] == "todo"


def test_set_todo_status():
    tid = storage.add_todo("Test task")["id"]
    assert storage.set_todo_status(tid, "done")["status"] == "done"
    assert storage.set_todo_status(tid, "todo")["status"] == "todo"


def test_set_todo_status_rejects_invalid():
    tid = storage.add_todo("Test task")["id"]
    assert storage.set_todo_status(tid, "finished") is None


def test_set_todo_status_missing():
    assert storage.set_todo_status("nonexistent", "done") is None


def test_migrates_legacy_completed_flag(isolated_data_dir):
    legacy = {"1": {"id": "1", "text": "Old", "completed": True, "created_at": 1.0}}
    (isolated_data_dir / "todos.json").write_text(json.dumps(legacy))
    todo = storage.get_todos()[0]
    assert todo["status"] == "done"
    assert "completed" not in todo


def test_delete_todo():
    tid = storage.add_todo("Delete me")["id"]
    assert storage.delete_todo(tid) is True
    assert storage.delete_todo(tid) is False
    assert storage.get_todos() == []


def test_add_and_get_notes():
    storage.add_note("Meeting", "Discuss Q2 goals")
    storage.add_note("Shopping", "Apples, bread")
    notes = storage.get_notes()
    # newest first
    assert [n["title"] for n in notes] == ["Shopping", "Meeting"]


def test_delete_note():
    nid = storage.add_note("Temp", "Content")["id"]
    assert storage.delete_note(nid) is True
    assert storage.delete_note(nid) is False


def test_empty_lists():
    assert storage.get_todos() == []
    assert storage.get_notes() == []


def test_corrupt_file_is_treated_as_empty(isolated_data_dir):
    (isolated_data_dir / "todos.json").write_text("{not json")
    assert storage.get_todos() == []


def test_strip_whitespace():
    assert storage.add_todo("   trimmed   ")["text"] == "trimmed"
