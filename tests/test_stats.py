"""Tests for stats module."""

import pytest
from homebase import stats


def test_get_cpu_count():
    count = stats.get_cpu_count()
    assert isinstance(count, int)
    assert count > 0


def test_get_cpu_percent():
    pct = stats.get_cpu_percent()
    assert isinstance(pct, float)
    assert 0.0 <= pct <= 100.0


def test_get_ram():
    ram = stats.get_ram()
    assert "total_gb" in ram
    assert "used_gb" in ram
    assert "available_gb" in ram
    assert "percent" in ram
    assert ram["total_gb"] > 0
    assert ram["used_gb"] >= 0
    assert 0.0 <= ram["percent"] <= 100.0


def test_get_disk():
    disk = stats.get_disk()
    assert "total_gb" in disk
    assert "used_gb" in disk
    assert "free_gb" in disk
    assert "percent" in disk
    assert disk["total_gb"] > 0
    assert 0.0 <= disk["percent"] <= 100.0


def test_get_uptime():
    up = stats.get_uptime()
    assert isinstance(up, int)
    assert up > 0


def test_get_all_stats():
    data = stats.get_all_stats()
    assert "cpu_percent" in data
    assert "cpu_count" in data
    assert "ram" in data
    assert "disk" in data
    assert "uptime_seconds" in data
