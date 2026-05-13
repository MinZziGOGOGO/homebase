#!/usr/bin/env python3
"""homebase dashboard — unified control panel for shortform-ai and other projects."""

import json
import os
import shlex
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# ── Paths ──────────────────────────────────────────────────────────────────
REAL_HOME = Path(os.environ.get("REAL_HOME", os.path.expanduser("~")))
PROJECTS_DIR = REAL_HOME / "projects"
SHORTFORM_DIR = PROJECTS_DIR / "shortform-ai"
CONFIG_PATH = SHORTFORM_DIR / "config.json"
PERFORMANCE_PATH = SHORTFORM_DIR / "results" / "performance.json"
STYLE_GUIDE_PATH = SHORTFORM_DIR / "STYLE_GUIDE.md"
LOGS_DIR = SHORTFORM_DIR / "logs"
SCHEDULER_LOG = LOGS_DIR / "scheduler.log"
SCRIPTS_DIR = SHORTFORM_DIR / "scripts"
LATEST_SCRIPT = SCRIPTS_DIR / "latest_script.json"
STATIC_DIR = Path(__file__).parent

app = FastAPI(title="homebase")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Config ─────────────────────────────────────────────────────────────────

@app.get("/api/shorts/config")
def get_config():
    """Read and return config.json."""
    if not CONFIG_PATH.exists():
        return {"videos_per_day": 2, "posting_times": ["09:00", "18:00"],
                "topic_focus": "all", "auto_post": True, "paused": False}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


@app.post("/api/shorts/config")
def update_config(body: dict):
    """Update config.json with request body."""
    existing = {}
    if CONFIG_PATH.exists():
        existing = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    existing.update(body)
    CONFIG_PATH.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "config": existing}


# ── Stats ──────────────────────────────────────────────────────────────────

@app.get("/api/shorts/stats")
def get_stats():
    """Read performance data and return summary stats."""
    if not PERFORMANCE_PATH.exists():
        return {
            "total_videos": 0,
            "average_views_last_7_days": 0,
            "best_video_title": None,
            "best_video_views": 0,
            "views_trend": "flat",
            "last_updated": None,
        }

    records = json.loads(PERFORMANCE_PATH.read_text(encoding="utf-8"))

    if not records:
        return {
            "total_videos": 0,
            "average_views_last_7_days": 0,
            "best_video_title": None,
            "best_video_views": 0,
            "views_trend": "flat",
            "last_updated": None,
        }

    total_videos = len(records)

    # Best video
    best = max(records, key=lambda r: r.get("views", 0))
    best_video_title = best.get("title", "Unknown")
    best_video_views = best.get("views", 0)

    # Average views in last 7 days
    cutoff = time.time() - 7 * 86400
    recent = [r for r in records if r.get("upload_timestamp", 0) >= cutoff]
    if recent:
        avg_views = round(sum(r.get("views", 0) for r in recent) / len(recent), 1)
    else:
        avg_views = 0

    # Views trend: compare last 7 days vs previous 7 days
    last_7 = [r for r in records if r.get("upload_timestamp", 0) >= cutoff]
    prev_cutoff = time.time() - 14 * 86400
    prev_7 = [r for r in records if prev_cutoff <= r.get("upload_timestamp", 0) < cutoff]

    if last_7 and prev_7:
        last_avg = sum(r.get("views", 0) for r in last_7) / len(last_7)
        prev_avg = sum(r.get("views", 0) for r in prev_7) / len(prev_7)
        if last_avg > prev_avg * 1.1:
            views_trend = "up"
        elif last_avg < prev_avg * 0.9:
            views_trend = "down"
        else:
            views_trend = "flat"
    else:
        views_trend = "flat"

    # Last updated
    last_updated = max(r.get("fetched_at", "") for r in records) if records else None

    return {
        "total_videos": total_videos,
        "average_views_last_7_days": avg_views,
        "best_video_title": best_video_title,
        "best_video_views": best_video_views,
        "views_trend": views_trend,
        "last_updated": last_updated,
    }


# ── Queue ──────────────────────────────────────────────────────────────────

@app.get("/api/shorts/queue")
def get_queue():
    """Return next 3 scheduled videos with scripts if available."""
    # Load config for posting times
    cfg = {}
    if CONFIG_PATH.exists():
        cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    posting_times = cfg.get("posting_times", ["09:00", "18:00"])
    topic_focus = cfg.get("topic_focus", "all")

    # Generate next 3 upcoming posting times
    now = datetime.now()
    upcoming = []

    for day_offset in range(7):  # Look up to 7 days ahead
        d = now + timedelta(days=day_offset)
        for pt in posting_times:
            h, m = map(int, pt.split(":"))
            slot = d.replace(hour=h, minute=m, second=0, microsecond=0)
            if slot > now:
                upcoming.append(slot)
            if len(upcoming) >= 3:
                break
        if len(upcoming) >= 3:
            break

    # Load latest script if available
    script_data = None
    if LATEST_SCRIPT.exists():
        try:
            script_data = json.loads(LATEST_SCRIPT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass

    queue_items = []
    for i, slot in enumerate(upcoming[:3]):
        item = {
            "title": script_data.get("title", "Untitled") if script_data and i == 0 else "TBD",
            "topic": topic_focus,
            "scheduled_time": slot.strftime("%Y-%m-%d %H:%M"),
            "has_script": script_data is not None and i == 0,
        }
        if script_data and i == 0:
            item["script"] = {
                "hook": script_data.get("hook", ""),
                "title": script_data.get("title", ""),
                "hashtags": script_data.get("hashtags", ""),
            }
        queue_items.append(item)

    return {"queue": queue_items}


# ── Log ────────────────────────────────────────────────────────────────────

@app.get("/api/shorts/log")
def get_log():
    """Return last 20 lines of scheduler.log."""
    if not SCHEDULER_LOG.exists():
        return {"lines": []}

    text = SCHEDULER_LOG.read_text(encoding="utf-8", errors="replace")
    lines = text.strip().split("\n")
    return {"lines": lines[-20:]}


# ── Improvement log ────────────────────────────────────────────────────────

@app.get("/api/shorts/improvement")
def get_improvement():
    """Return last self-improvement summary."""
    if not STYLE_GUIDE_PATH.exists():
        return {"summary": None, "timestamp": None}

    stat = STYLE_GUIDE_PATH.stat()
    timestamp = datetime.fromtimestamp(stat.st_mtime).isoformat()

    # Read first few lines of STYLE_GUIDE.md as summary
    content = STYLE_GUIDE_PATH.read_text(encoding="utf-8")
    first_lines = [l for l in content.split("\n") if l.strip() and not l.startswith("# ")][:3]
    summary = " ".join(first_lines)[:200] if first_lines else "Style guide updated"

    return {"summary": summary, "timestamp": timestamp}


# ── Static files ───────────────────────────────────────────────────────────

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html", media_type="text/html")


# ── Run ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
