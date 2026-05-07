# Homebase Dashboard

A self-hosted personal dashboard showing live system stats, weather, todos, and notes.

## Features

- **Live System Stats** — CPU, RAM, disk usage with auto-refresh every 5 seconds via WebSocket
- **Server Uptime** — Shows how long the machine has been running
- **Todo List** — Add, complete, and delete tasks, persisted to JSON
- **Markdown Notes** — Write and save notes, persisted to JSON
- **Weather Widget** — Current conditions for Vienna (configurable) via wttr.in
- **Dark Mode UI** — Clean, modern dark theme

## Tech Stack

- **Backend**: FastAPI with WebSockets
- **Frontend**: Vanilla HTML/CSS/JS (no build step, no npm)
- **System metrics**: psutil
- **Storage**: JSON files
- **Weather**: wttr.in (free, no API key needed)

## Setup

### Requirements

- Python 3.10+
- pip

### Install

```bash
cd ~/projects/homebase
pip install -r requirements.txt
```

### Run

```bash
cd ~/projects/homebase
python -m uvicorn homebase.main:app --host 0.0.0.0 --port 8080
```

Then open `http://<server-ip>:8080` in your browser.

### Run Tests

```bash
cd ~/projects/homebase
pytest tests/ -v
```

## Project Structure

```
homebase/
  homebase/
    __init__.py
    main.py          # FastAPI app, routes, WebSocket
    stats.py         # System metrics via psutil
    storage.py       # JSON CRUD for todos and notes
    static/
      index.html     # Single-page dashboard frontend
  tests/
    __init__.py
    test_stats.py    # Tests for system metrics
    test_storage.py  # Tests for JSON persistence
    test_app.py      # Tests for API endpoints
  data/              # Runtime JSON storage (auto-created)
    todos.json
    notes.json
  requirements.txt
  README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard frontend |
| GET | `/api/todos` | List all todos |
| POST | `/api/todos` | Create a todo |
| PUT | `/api/todos/{id}` | Toggle todo completion |
| DELETE | `/api/todos/{id}` | Delete a todo |
| GET | `/api/notes` | List all notes |
| POST | `/api/notes` | Create a note |
| DELETE | `/api/notes/{id}` | Delete a note |
| GET | `/api/weather?city=Vienna` | Weather data from wttr.in |
| WS | `/ws/stats` | WebSocket: live system stats |

## License

MIT
