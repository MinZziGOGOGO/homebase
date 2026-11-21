"""Homebase Dashboard — FastAPI backend."""

import asyncio
import json
import subprocess
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from mcstatus import JavaServer
from pydantic import BaseModel

from . import stats, storage
from .config import optional_path, settings

app = FastAPI(title="Homebase Dashboard")

STATIC_DIR = Path(__file__).resolve().parent / "static"


@app.get("/static/manifest.json")
async def manifest():
    """Serve the PWA manifest with correct Content-Type."""
    return FileResponse(
        str(STATIC_DIR / "manifest.json"),
        media_type="application/manifest+json",
    )


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """Serve the dashboard frontend."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/config")
async def get_config():
    """Tell the frontend which optional widgets are enabled."""
    return {
        "city": settings["city"],
        "minecraft": bool(settings["minecraft_server"]),
        "minecraft_address": settings["minecraft_public_address"] or settings["minecraft_server"],
        "docker": bool(settings["docker"]),
        "shorts": bool(settings["shortform_dir"]),
        "notifications": bool(settings["notifications_url"]),
    }


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
    if not body.text.strip():
        raise HTTPException(status_code=422, detail="Todo text must not be empty")
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
    if not storage.delete_todo(todo_id):
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
    if not body.title.strip() or not body.content.strip():
        raise HTTPException(status_code=422, detail="Title and content must not be empty")
    return storage.add_note(body.title, body.content)


@app.delete("/api/notes/{note_id}")
async def remove_note(note_id: str):
    """Delete a note."""
    if not storage.delete_note(note_id):
        raise HTTPException(status_code=404, detail="Note not found")
    return {"ok": True}


# --- Weather proxy ---

@app.get("/api/weather")
async def get_weather(city: str | None = None):
    """Proxy weather data from wttr.in. Returns JSON."""
    url = f"https://wttr.in/{city or settings['city']}?format=j1"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, ValueError) as e:
        raise HTTPException(status_code=502, detail=f"Weather API error: {e}")


# --- Minecraft server status ---

@app.get("/api/minecraft")
async def get_minecraft():
    """Query the configured Minecraft server via mcstatus."""
    offline = {
        "online": False,
        "player_count": 0,
        "max_players": 0,
        "players": [],
        "description": "",
        "latency": 0,
    }
    if not settings["minecraft_server"]:
        return offline
    try:
        server = await JavaServer.async_lookup(settings["minecraft_server"])
        status = await server.async_status()
        return {
            "online": True,
            "player_count": status.players.online,
            "max_players": status.players.max,
            "players": [p.name for p in status.players.sample] if status.players.sample else [],
            "description": status.motd.to_plain(),
            "latency": round(status.latency, 1),
        }
    except Exception:
        return offline


# --- Network speed ---

def _read_net_bytes() -> tuple[int, int]:
    """Return (rx_bytes, tx_bytes) of the busiest non-loopback interface."""
    try:
        with open("/proc/net/dev") as f:
            lines = f.readlines()[2:]  # skip headers
    except OSError:
        return (0, 0)
    best = (0, 0)
    for line in lines:
        parts = line.split()
        name = parts[0].rstrip(":")
        rx, tx = int(parts[1]), int(parts[9])
        if name != "lo" and rx + tx > sum(best):
            best = (rx, tx)
    return best


@app.get("/api/network")
async def get_network():
    """Return current upload/download speed in MB/s by sampling 1s apart."""
    rx0, tx0 = _read_net_bytes()
    await asyncio.sleep(1)
    rx1, tx1 = _read_net_bytes()
    return {
        "download_mb_s": round((rx1 - rx0) / (1024 * 1024), 3),
        "upload_mb_s": round((tx1 - tx0) / (1024 * 1024), 3),
    }


# --- WebSocket for live stats ---

@app.websocket("/ws/stats")
async def websocket_stats(ws: WebSocket):
    """Push system stats every 5 seconds over WebSocket."""
    await ws.accept()
    try:
        while True:
            data = await asyncio.to_thread(stats.get_all_stats)
            await ws.send_text(json.dumps(data))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass


# --- Services status ---

async def _check_service(client: httpx.AsyncClient, svc: dict, hostname: str) -> dict:
    try:
        # Services run on the same host as homebase, so ping them as configured
        resp = await client.get(svc["url"], follow_redirects=True)
        up = resp.status_code < 500
    except Exception:
        up = False
    # Rewrite localhost so links work from other devices on the network
    return {**svc, "url": svc["url"].replace("localhost", hostname), "up": up}


@app.get("/api/services")
async def get_services(request: Request):
    """Ping each configured service and return its status."""
    hostname = request.url.hostname or "localhost"
    async with httpx.AsyncClient(timeout=3.0, verify=False) as client:
        return await asyncio.gather(
            *(_check_service(client, svc, hostname) for svc in settings["services"])
        )


# --- Docker container manager ---

def _docker(args: list[str]) -> str:
    """Run a docker command and return stdout, or raise HTTPException."""
    if not settings["docker"]:
        raise HTTPException(status_code=404, detail="Docker integration disabled")
    try:
        r = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=15)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="docker CLI not found")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="docker command timed out")
    if r.returncode != 0:
        raise HTTPException(status_code=500, detail=r.stderr.strip())
    return r.stdout


@app.get("/api/docker/containers")
async def list_containers():
    """Return all containers with name, status, and image."""
    out = _docker(["ps", "-a", "--format", "{{.Names}}\t{{.Status}}\t{{.Image}}"])
    containers = []
    for line in out.strip().split("\n"):
        if not line:
            continue
        name, status, image = line.split("\t", 2)
        containers.append({"name": name, "status": status, "image": image})
    return {"containers": containers}


@app.post("/api/docker/containers/{name}/{action}")
async def container_action(name: str, action: str):
    """Start, stop or restart a container by name."""
    if action not in ("start", "stop", "restart"):
        raise HTTPException(status_code=404, detail="Unknown action")
    _docker([action, name])
    return {"ok": True, "name": name, "action": action}


# --- Shorts (dashboard for the shortform-ai video creator) ---

SHORTS_DIR = optional_path(settings["shortform_dir"])

DEFAULT_SHORTS_CONFIG = {
    "videos_per_day": 2,
    "posting_times": ["09:00", "18:00"],
    "topic_focus": "all",
    "auto_post": True,
    "paused": False,
}


def _shorts_file(*parts: str) -> Path:
    if SHORTS_DIR is None:
        raise HTTPException(status_code=404, detail="Shorts integration disabled")
    return SHORTS_DIR.joinpath(*parts)


def _read_json_file(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


@app.get("/api/shorts/config")
async def get_shorts_config():
    """Return current shorts config."""
    return {**DEFAULT_SHORTS_CONFIG, **_read_json_file(_shorts_file("config.json"), {})}


@app.post("/api/shorts/config")
async def update_shorts_config(body: dict):
    """Update shorts config."""
    path = _shorts_file("config.json")
    cfg = _read_json_file(path, {})
    cfg.update(body)
    path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return {"ok": True}


@app.get("/api/shorts/stats")
async def get_shorts_stats():
    """Return a performance summary of uploaded videos."""
    records = _read_json_file(_shorts_file("results", "performance.json"), [])
    if not records:
        return {"total_videos": 0, "average_views_last_7_days": 0, "best_video_title": "",
                "best_video_views": 0, "views_trend": "No data", "last_updated": None}

    now = time.time()
    recent = [r for r in records if now - r.get("upload_timestamp", 0) < 7 * 86400]
    older = [r for r in records if now - r.get("upload_timestamp", 0) >= 7 * 86400]
    recent_avg = sum(r.get("views", 0) for r in recent) / max(1, len(recent))
    older_avg = sum(r.get("views", 0) for r in older) / max(1, len(older))
    if older_avg > 0:
        delta = round((recent_avg - older_avg) / older_avg * 100, 1)
        trend = f"{'+' if delta > 0 else ''}{delta}%"
    else:
        trend = "New"

    best = max(records, key=lambda r: r.get("views", 0))
    return {
        "total_videos": len(records),
        "average_views_last_7_days": round(recent_avg, 1) if recent else 0,
        "best_video_title": best.get("title", ""),
        "best_video_views": best.get("views", 0),
        "views_trend": trend,
        "last_updated": records[-1].get("fetched_at"),
    }


@app.get("/api/shorts/queue")
async def get_shorts_queue():
    """Return the next 3 posting slots, with the latest script if one is ready."""
    script = _read_json_file(_shorts_file("scripts", "latest_script.json"), None)
    cfg = {**DEFAULT_SHORTS_CONFIG, **_read_json_file(_shorts_file("config.json"), {})}

    now = datetime.now()
    slots = []
    for day in range(7):
        for pt in sorted(cfg["posting_times"]):
            h, m = map(int, pt.split(":"))
            slot = (now + timedelta(days=day)).replace(hour=h, minute=m, second=0, microsecond=0)
            if slot > now:
                slots.append(slot)
    slots = slots[:3]

    return [
        {
            "title": script.get("title", "Untitled") if script and i == 0 else "TBD",
            "topic": cfg["topic_focus"],
            "scheduled_time": slot.strftime("%a %H:%M"),
            "script_ready": bool(script) and i == 0,
        }
        for i, slot in enumerate(slots)
    ]


@app.get("/api/shorts/log")
async def get_shorts_log():
    """Return last 20 lines of the scheduler log."""
    path = _shorts_file("logs", "scheduler.log")
    if not path.exists():
        return {"lines": []}
    return {"lines": path.read_text(encoding="utf-8", errors="replace").strip().split("\n")[-20:]}


# --- Notifications proxy ---

@app.get("/api/notifications")
async def get_notifications():
    """Proxy the configured notification service."""
    if not settings["notifications_url"]:
        return []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(settings["notifications_url"].rstrip("/") + "/notifications")
            resp.raise_for_status()
            return resp.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="Notification service unreachable")


@app.post("/api/notifications/flush")
async def flush_notifications():
    """Ask the notification service to send its digest now."""
    if not settings["notifications_url"]:
        raise HTTPException(status_code=404, detail="Notifications disabled")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(settings["notifications_url"].rstrip("/") + "/notifications/flush")
            resp.raise_for_status()
            return {"ok": True}
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Notification service unreachable")


# --- Unified search ---

SEARCH = settings["search"]


async def _http_search(url: str, key: str, params: dict | None = None) -> list[dict]:
    """Generic HTTP search — returns a JSON list or data[key]."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params or {})
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get(key, [])
    except Exception:
        return []


async def _search_mindbase(q: str) -> list[dict]:
    base = SEARCH["mindbase_url"]
    if not base:
        return []
    entries = await _http_search(f"{base}/api/entries", "entries", {"search": q})
    ql = q.lower()
    return [
        {
            "source": "mindbase",
            "title": e.get("title", e.get("name", "")),
            "snippet": (e.get("content") or e.get("snippet", ""))[:200],
            "url": e.get("url", f"{base}/entries/{e.get('id', '')}"),
        }
        for e in entries
        if ql in (e.get("title", "") + e.get("content", "")).lower()
    ][:10]


async def _search_wiki(q: str) -> list[dict]:
    base = SEARCH["wiki_url"]
    if not base:
        return []
    pages = await _http_search(f"{base}/api/search", "results", {"q": q})
    return [
        {
            "source": "wiki",
            "title": p.get("title", ""),
            "snippet": (p.get("snippet") or p.get("content", ""))[:200],
            "url": p.get("url", f"{base}/wiki/{p.get('slug', '')}"),
        }
        for p in pages
    ][:10]


def _search_shopping(q: str) -> list[dict]:
    path = optional_path(SEARCH["shopping_list"])
    if not path or not path.exists():
        return []
    ql = q.lower()
    return [
        {"source": "shopping", "title": line.strip()[:100], "snippet": "", "url": None}
        for line in path.read_text(encoding="utf-8").splitlines()
        if ql in line.lower()
    ][:10]


def _search_reminders(q: str) -> list[dict]:
    path = optional_path(SEARCH["reminders_dir"])
    if not path or not path.exists():
        return []
    ql = q.lower()
    results = []
    for f in sorted(path.iterdir()):
        if not f.is_file() or f.suffix not in (".md", ".txt"):
            continue
        content = f.read_text(encoding="utf-8")[:2000]
        if ql in content.lower():
            results.append({"source": "reminders", "title": f.stem, "snippet": content[:200], "url": None})
        if len(results) >= 10:
            break
    return results


def _search_git(q: str) -> list[dict]:
    path = optional_path(SEARCH["projects_dir"])
    if not path or not path.exists():
        return []
    results = []
    repos = sorted(d for d in path.iterdir() if d.is_dir() and (d / ".git").exists())[:10]
    for repo in repos:
        try:
            r = subprocess.run(
                ["git", "-C", str(repo), "log", "--oneline", "--all", "-20", f"--grep={q}", "-i"],
                capture_output=True, text=True, timeout=5,
            )
        except Exception:
            continue
        for line in r.stdout.strip().splitlines():
            results.append({"source": "git", "title": f"{repo.name}: {line}", "snippet": "", "url": None})
            if len(results) >= 10:
                return results
    return results


GITHUB_CACHE = Path("/tmp/homebase_github_cache.json")


def _fetch_github_repos(user: str) -> list[dict]:
    """Fetch a user's public repos from the GitHub API with a 1-hour file cache."""
    now = time.time()
    cached = _read_json_file(GITHUB_CACHE, {})
    if cached.get("user") == user and cached.get("fetched_at", 0) > now - 3600:
        return cached.get("repos", [])
    try:
        req = urllib.request.Request(
            f"https://api.github.com/users/{user}/repos?per_page=100",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "homebase-search"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            repos = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return []
    if isinstance(repos, list):
        GITHUB_CACHE.write_text(json.dumps({"user": user, "fetched_at": now, "repos": repos}), encoding="utf-8")
        return repos
    return []


def _search_github_repos(q: str) -> list[dict]:
    user = SEARCH["github_user"]
    if not user:
        return []
    ql = q.lower()
    results = []
    for r in _fetch_github_repos(user):
        name, desc = r.get("name", ""), r.get("description") or ""
        if ql in name.lower() or ql in desc.lower():
            results.append({"source": "github", "title": name, "snippet": desc[:200], "url": r.get("html_url")})
        if len(results) >= 10:
            break
    return results


def _search_sessions(q: str) -> list[dict]:
    """Search the first user message of recent agent session logs (.jsonl)."""
    path = optional_path(SEARCH["sessions_dir"])
    if not path or not path.exists():
        return []
    ql = q.lower()
    files = sorted(
        (f for f in path.iterdir() if f.is_file() and f.suffix == ".jsonl" and not f.name.startswith(".")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:20]
    results = []
    for f in files:
        try:
            with f.open(encoding="utf-8") as fh:
                for line in fh:
                    obj = json.loads(line)
                    if obj.get("role") == "user":
                        title = (obj.get("content") or "")[:100]
                        if ql in title.lower():
                            results.append({"source": "session", "title": title, "snippet": "", "url": None})
                        break
        except Exception:
            continue
        if len(results) >= 10:
            break
    return results


@app.get("/api/search")
async def unified_search(q: str = ""):
    """Search across all configured sources."""
    if not q.strip():
        return {"results": []}
    groups = await asyncio.gather(
        _search_mindbase(q),
        _search_wiki(q),
        asyncio.to_thread(_search_shopping, q),
        asyncio.to_thread(_search_reminders, q),
        asyncio.to_thread(_search_git, q),
        asyncio.to_thread(_search_github_repos, q),
        asyncio.to_thread(_search_sessions, q),
    )
    ql = q.lower()
    results = [r for group in groups for r in group]
    results.sort(key=lambda r: -(r["title"].lower().count(ql) * 3 + r["snippet"].lower().count(ql)))
    return {"results": results[:30]}


# --- SPA catch-all: serve index.html for frontend routes ---
# Must be defined AFTER all API routes so FastAPI matches specific routes first.

@app.get("/{full_path:path}")
async def spa_catch_all(full_path: str):
    """Catch-all route for SPA navigation (/docker, /services, etc)."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(STATIC_DIR / "index.html"))
