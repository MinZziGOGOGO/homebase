"""Homebase Dashboard — FastAPI backend."""

import asyncio
import json
import subprocess
import time
from datetime import datetime, timedelta
import httpx
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from mcstatus import JavaServer

from . import stats, storage

app = FastAPI(title="Homebase Dashboard")

# Serve static files (frontend)
STATIC_DIR = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    """Serve the dashboard frontend."""
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/static/manifest.json")
async def manifest():
    """Serve the PWA manifest with correct Content-Type."""
    return FileResponse(
        str(STATIC_DIR / "manifest.json"),
        media_type="application/manifest+json",
    )


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


# --- Minecraft server status ---

@app.get("/api/minecraft")
async def get_minecraft():
    """Query local Minecraft server via mcstatus."""
    try:
        server = JavaServer.lookup("localhost:25565")
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
        return {
            "online": False,
            "player_count": 0,
            "max_players": 0,
            "players": [],
            "description": "",
            "latency": 0,
        }


# --- Network speed ---

def _read_net_bytes():
    """Return (rx_bytes, tx_bytes) for the main interface from /proc/net/dev."""
    with open("/proc/net/dev") as f:
        lines = f.readlines()[2:]  # skip headers
    best = (0, 0)
    best_name = "lo"
    for line in lines:
        parts = line.split()
        name = parts[0].rstrip(":")
        rx = int(parts[1])
        tx = int(parts[9])
        if name != "lo" and rx + tx > best[0] + best[1]:
            best = (rx, tx)
            best_name = name
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
            data = stats.get_all_stats()
            await ws.send_text(json.dumps(data))
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        pass


# --- Services status ---

SERVICES = [
    {"name": "Nextcloud", "url": "http://localhost:8888", "icon": "☁️", "desc": "Self-hosted cloud storage"},
    {"name": "Kavita", "url": "http://localhost:5000", "icon": "📚", "desc": "Manga & book reader"},
    {"name": "Hermes IDE", "url": "https://localhost:8445", "icon": "🤖", "desc": "VS Code + Hermes AI agent"},
    {"name": "Pi-hole", "url": "http://localhost:8085/admin", "icon": "🛡️", "desc": "Network ad blocker"},
    {"name": "Stirling-PDF", "url": "http://localhost:8093", "icon": "📄", "desc": "PDF editor & converter"},
    {"name": "Portainer", "url": "http://localhost:9000", "icon": "🐳", "desc": "Docker container manager"},
    {"name": "Vaultwarden", "url": "http://localhost:8094", "icon": "🔐", "desc": "Password manager"},
    {"name": "mindbase", "url": "http://localhost:8091", "icon": "🧠", "desc": "AI knowledge base"},
    {"name": "homebase", "url": "http://localhost:8080", "icon": "🏠", "desc": "System dashboard"},
    {"name": "arcadebase", "url": "http://localhost:8090", "icon": "🕹️", "desc": "Retro arcade games"},
    {"name": "learning-tracker", "url": "http://localhost:8091", "icon": "📖", "desc": "Learning progress tracker"},
    {"name": "hermes-dashboard", "url": "http://localhost:9119", "icon": "⚡", "desc": "AI agent dashboard"},
    {"name": "minecraft", "url": "http://localhost:25565", "icon": "⛏️", "desc": "Minecraft Paper server"},
    {"name": "crafty", "url": "http://localhost:8444", "icon": "🖥️", "desc": "Minecraft web management"},
]


@app.get("/api/services")
async def get_services(request: Request):
    """Ping each service and return status. URLs use request hostname."""
    hostname = request.headers.get("host", "localhost").split(":")[0]
    results = []
    for svc in SERVICES:
        up = False
        try:
            async with httpx.AsyncClient(timeout=3.0, verify=False) as client:
                # Always ping localhost — services run on the same host
                resp = await client.get(svc["url"], follow_redirects=True)
                up = resp.status_code < 500
        except Exception:
            up = False
        # Rewrite URL to use the requesting hostname
        external_url = svc["url"].replace("localhost", hostname)
        results.append({**svc, "url": external_url, "up": up})
    return results


# --- Docker container manager ---

def _docker(args: list[str]) -> str:
    """Run a docker command and return stdout, or raise HTTPException."""
    try:
        r = subprocess.run(["docker"] + args, capture_output=True, text=True, timeout=15)
        if r.returncode != 0:
            raise HTTPException(status_code=500, detail=r.stderr.strip())
        return r.stdout
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="docker CLI not found")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="docker command timed out")


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


@app.post("/api/docker/containers/{name}/start")
async def start_container(name: str):
    """Start a container by name."""
    _docker(["start", name])
    return {"ok": True, "name": name, "action": "start"}


@app.post("/api/docker/containers/{name}/stop")
async def stop_container(name: str):
    """Stop a container by name."""
    _docker(["stop", name])
    return {"ok": True, "name": name, "action": "stop"}


@app.post("/api/docker/containers/{name}/restart")
async def restart_container(name: str):
    """Restart a container by name."""
    _docker(["restart", name])
    return {"ok": True, "name": name, "action": "restart"}


# ── Shorts (short-form video creator) ──────────────────────────────────────

SHORTS_DIR = Path("/home/martin/projects/shortform-ai")
SHORTS_CONFIG = SHORTS_DIR / "config.json"
SHORTS_PERF = SHORTS_DIR / "results" / "performance.json"
SHORTS_UPLOADS = SHORTS_DIR / "results" / "uploads.json"
SHORTS_LOG = SHORTS_DIR / "logs" / "scheduler.log"
SHORTS_SCRIPT = SHORTS_DIR / "scripts" / "latest_script.json"

DEFAULT_SHORTS_CONFIG = {
    "videos_per_day": 2,
    "posting_times": ["09:00", "18:00"],
    "topic_focus": "all",
    "auto_post": True,
    "paused": False,
}

TOPICS = ["all", "ai", "tech", "coding", "science"]


@app.get("/api/shorts/config")
async def get_shorts_config():
    """Return current shorts config."""
    if SHORTS_CONFIG.exists():
        return json.loads(SHORTS_CONFIG.read_text(encoding="utf-8"))
    return DEFAULT_SHORTS_CONFIG


@app.post("/api/shorts/config")
async def update_shorts_config(body: dict):
    """Update shorts config."""
    cfg = json.loads(SHORTS_CONFIG.read_text(encoding="utf-8")) if SHORTS_CONFIG.exists() else {}
    cfg.update(body)
    SHORTS_CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    return {"ok": True}


@app.get("/api/shorts/stats")
async def get_shorts_stats():
    """Return performance summary."""
    if not SHORTS_PERF.exists():
        return {"total_videos": 0, "average_views_last_7_days": 0, "best_video_title": "", "best_video_views": 0, "views_trend": "No data", "last_updated": None}

    records = json.loads(SHORTS_PERF.read_text(encoding="utf-8"))
    if not records:
        return {"total_videos": 0, "average_views_last_7_days": 0, "best_video_title": "", "best_video_views": 0, "views_trend": "No data", "last_updated": None}

    total = len(records)

    # Average views last 7 days
    now = time.time()
    recent = [r for r in records if now - r.get("upload_timestamp", 0) < 7 * 86400]
    avg_views = round(sum(r.get("views", 0) for r in recent) / max(1, len(recent)), 1) if recent else 0

    # Best video
    best = max(records, key=lambda r: r.get("views", 0))
    best_title = best.get("title", "")
    best_views = best.get("views", 0)

    # Trend (simple: compare last 7 vs previous 7 days)
    recent_ids = {r.get("video_id") for r in recent}
    older = [r for r in records if r.get("video_id") not in recent_ids]
    recent_avg = sum(r.get("views", 0) for r in recent) / max(1, len(recent))
    older_avg = sum(r.get("views", 0) for r in older) / max(1, len(older))
    if older_avg > 0:
        delta = round((recent_avg - older_avg) / older_avg * 100, 1)
        trend = f"{'+' if delta > 0 else ''}{delta}%"
    else:
        trend = "New"

    return {
        "total_videos": total,
        "average_views_last_7_days": avg_views,
        "best_video_title": best_title,
        "best_video_views": best_views,
        "views_trend": trend,
        "last_updated": records[-1].get("fetched_at") if records else None,
    }


@app.get("/api/shorts/queue")
async def get_shorts_queue():
    """Return next 3 scheduled videos with scripts if available."""
    queue = []
    now = time.time()

    # Check if latest_script exists
    script = None
    if SHORTS_SCRIPT.exists():
        script = json.loads(SHORTS_SCRIPT.read_text(encoding="utf-8"))

    # Generate future posting times from config
    cfg = DEFAULT_SHORTS_CONFIG
    if SHORTS_CONFIG.exists():
        cfg = json.loads(SHORTS_CONFIG.read_text(encoding="utf-8"))
    posting_times = cfg.get("posting_times", ["09:00", "18:00"])
    topic = cfg.get("topic_focus", "all")

    for i in range(3):
        scheduled = datetime.now() + timedelta(hours=i * 3 + 1)
        entry = {
            "title": script.get("title", f"Scheduled video {i+1}") if script else f"Scheduled video {i+1}",
            "topic": topic,
            "scheduled_time": scheduled.strftime("%H:%M"),
            "script_ready": script is not None,
        }
        queue.append(entry)
    return queue


@app.get("/api/shorts/log")
async def get_shorts_log():
    """Return last 20 lines of scheduler log."""
    if not SHORTS_LOG.exists():
        return {"lines": []}
    content = SHORTS_LOG.read_text(encoding="utf-8")
    lines = content.strip().split("\n")[-20:]
    return {"lines": lines}


# --- Unified Search ---

REAL_HOME = Path("/home/martin")
SHOPPING_LIST = REAL_HOME / ".hermes" / "shopping_list.md"
REMINDERS_DIR = REAL_HOME / ".hermes" / "reminders"
PROJECTS_DIR = REAL_HOME / "projects"


async def _http_search(url: str, key: str, params: dict | None = None) -> list[dict]:
    """Generic HTTP search — returns JSON list or data[key] list."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url, params=params or {})
            resp.raise_for_status()
            data = resp.json()
            return data if isinstance(data, list) else data.get(key, [])
    except Exception:
        return []


async def _search_mindbase(q: str) -> list[dict]:
    entries = await _http_search(
        "http://localhost:8091/api/entries", "entries", {"search": q},
    )
    ql = q.lower()
    return [
        {
            "source": "mindbase", "icon": "🧠",
            "title": e.get("title", e.get("name", "")),
            "snippet": (e.get("content") or e.get("snippet", ""))[:200],
            "url": e.get("url", f"http://localhost:8091/entries/{e.get('id', '')}"),
        }
        for e in entries
        if ql in (e.get("title", "") + e.get("content", "")).lower()
    ][:10]


async def _search_wiki(q: str) -> list[dict]:
    pages = await _http_search(
        "http://localhost:8101/api/search", "results", {"q": q},
    )
    return [
        {
            "source": "wiki", "icon": "📖",
            "title": p.get("title", ""),
            "snippet": (p.get("snippet") or p.get("content", ""))[:200],
            "url": p.get("url", f"http://localhost:8101/wiki/{p.get('slug', '')}"),
        }
        for p in pages
    ][:10]


async def _search_notifications(q: str) -> list[dict]:
    notifs = await _http_search(
        "http://localhost:8102/notifications", "notifications",
    )
    ql = q.lower()
    return [
        {
            "source": "notifications", "icon": "🔔",
            "title": (n.get("title") or n.get("message", ""))[:100],
            "snippet": (n.get("body") or n.get("message", ""))[:200],
            "url": None,
        }
        for n in notifs[:20]
        if ql in (n.get("title", "") + n.get("body", "") + n.get("message", "")).lower()
    ][:10]


def _search_shopping(q: str) -> list[dict]:
    if not SHOPPING_LIST.exists():
        return []
    ql = q.lower()
    return [
        {
            "source": "shopping", "icon": "🛒",
            "title": line.strip()[:100], "snippet": line.strip()[:200],
            "url": None,
        }
        for line in SHOPPING_LIST.read_text(encoding="utf-8").splitlines()
        if ql in line.lower()
    ][:10]


def _search_reminders(q: str) -> list[dict]:
    if not REMINDERS_DIR.exists():
        return []
    ql = q.lower()
    results = []
    for f in sorted(REMINDERS_DIR.iterdir()):
        if not f.is_file() or f.suffix not in (".md", ".txt"):
            continue
        content = f.read_text(encoding="utf-8")[:2000]
        if ql in content.lower():
            results.append({
                "source": "reminders", "icon": "📝",
                "title": f.stem, "snippet": content[:200], "url": None,
            })
        if len(results) >= 10:
            break
    return results


def _search_git(q: str) -> list[dict]:
    if not PROJECTS_DIR.exists():
        return []
    results = []
    repos = sorted(
        d for d in PROJECTS_DIR.iterdir()
        if d.is_dir() and (d / ".git").exists()
    )[:10]
    for repo in repos:
        try:
            r = subprocess.run(
                ["git", "-C", str(repo), "log", "--oneline", "--all",
                 "-20", f"--grep={q}", "-i"],
                capture_output=True, text=True, timeout=5,
            )
            for line in r.stdout.strip().splitlines():
                if not line:
                    continue
                results.append({
                    "source": "git", "icon": "📦",
                    "title": f"{repo.name}: {line}",
                    "snippet": line, "url": None,
                })
                if len(results) >= 10:
                    return results
        except Exception:
            continue
    return results


GITHUB_CACHE = Path("/tmp/github_cache.json")


def _fetch_github_repos() -> list[dict]:
    """Fetch MinZziGOGOGO repos from GitHub API with 1-hour file cache."""
    now = time.time()
    if GITHUB_CACHE.exists():
        try:
            cached = json.loads(GITHUB_CACHE.read_text(encoding="utf-8"))
            if cached.get("fetched_at", 0) > now - 3600:
                return cached.get("repos", [])
        except Exception:
            pass
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://api.github.com/users/MinZziGOGOGO/repos",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "homebase-search"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            repos = json.loads(resp.read().decode("utf-8"))
            if isinstance(repos, list):
                GITHUB_CACHE.write_text(
                    json.dumps({"fetched_at": now, "repos": repos}), encoding="utf-8"
                )
                return repos
    except Exception:
        pass
    return []


def _search_github_repos(q: str) -> list[dict]:
    repos = _fetch_github_repos()
    ql = q.lower()
    results = []
    for r in repos:
        name = r.get("name", "")
        desc = r.get("description") or ""
        if ql in name.lower() or ql in desc.lower():
            results.append({
                "source": "github", "icon": "📇",
                "title": name,
                "snippet": desc[:200],
                "url": r.get("html_url", ""),
            })
        if len(results) >= 10:
            break
    return results


SESSIONS_DIR = REAL_HOME / ".hermes" / "sessions"


def _search_sessions(q: str) -> list[dict]:
    if not SESSIONS_DIR.exists():
        return []
    ql = q.lower()
    files = sorted(
        (f for f in SESSIONS_DIR.iterdir() if f.is_file() and f.suffix == ".jsonl" and not f.name.startswith(".")),
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
                            results.append({
                                "source": "session", "icon": "🤖",
                                "title": title,
                                "snippet": title[:200],
                                "url": None,
                            })
                        break
                if len(results) >= 10:
                    break
        except Exception:
            continue
    return results


@app.get("/api/search")
async def unified_search(q: str = ""):
    """Search across mindbase, wiki, notifications, shopping, reminders, git, github, sessions."""
    if not q.strip():
        return []
    loop = asyncio.get_event_loop()
    mindbase, wiki, notifications, shopping, reminders, git, github, sessions = await asyncio.gather(
        _search_mindbase(q),
        _search_wiki(q),
        _search_notifications(q),
        loop.run_in_executor(None, _search_shopping, q),
        loop.run_in_executor(None, _search_reminders, q),
        loop.run_in_executor(None, _search_git, q),
        loop.run_in_executor(None, _search_github_repos, q),
        loop.run_in_executor(None, _search_sessions, q),
    )
    all_results = mindbase + wiki + notifications + shopping + reminders + git + github + sessions
    ql = q.lower()
    all_results.sort(key=lambda r: -sum((
        r["title"].lower().count(ql) * 3,
        r["snippet"].lower().count(ql),
    )))
    return {"results": all_results[:30]}


# --- SPA catch-all: serve index.html for frontend routes ---
# Must be defined AFTER all API routes so FastAPI matches specific routes first.

@app.get("/{full_path:path}")
async def spa_catch_all(full_path: str):
    """Catch-all route for SPA navigation (/docker, /services, etc)."""
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(STATIC_DIR / "index.html"))
