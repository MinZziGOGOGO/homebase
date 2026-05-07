"""System metrics using psutil."""

import psutil


def get_cpu_percent() -> float:
    """Return overall CPU usage percentage (0-100)."""
    return round(psutil.cpu_percent(interval=0.5), 1)


def get_cpu_count() -> int:
    """Return number of logical CPUs."""
    return psutil.cpu_count(logical=True)


def get_ram() -> dict:
    """Return RAM usage info."""
    mem = psutil.virtual_memory()
    return {
        "total_gb": round(mem.total / (1024**3), 1),
        "used_gb": round(mem.used / (1024**3), 1),
        "available_gb": round(mem.available / (1024**3), 1),
        "percent": mem.percent,
    }


def get_disk() -> dict:
    """Return disk usage for root partition."""
    usage = psutil.disk_usage("/")
    return {
        "total_gb": round(usage.total / (1024**3), 1),
        "used_gb": round(usage.used / (1024**3), 1),
        "free_gb": round(usage.free / (1024**3), 1),
        "percent": usage.percent,
    }


def get_uptime() -> int:
    """Return system uptime in seconds."""
    import time
    uptime_seconds = time.time() - psutil.boot_time()
    return int(uptime_seconds)


def get_all_stats() -> dict:
    """Return all system stats in one dict."""
    return {
        "cpu_percent": get_cpu_percent(),
        "cpu_count": get_cpu_count(),
        "ram": get_ram(),
        "disk": get_disk(),
        "uptime_seconds": get_uptime(),
    }
