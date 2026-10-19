"""Ids the contract and the attesters share.

zoneId is keccak256 of the zone slug. ruleHash is keccak256 of the frozen
rule file bytes. An evidence hash names the scene or the CHIRPS window.
It does not hide the fraction or the millimetre total.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from backtest.pipeline.keccak import keccak256

CHIRPS = "UCSB-CHG/CHIRPS/DAILY"


def zone_id(slug: str) -> bytes:
    if not slug:
        raise ValueError("empty zone")
    return keccak256(slug.encode())


def evidence_radar(item_id: str) -> bytes:
    if not item_id:
        raise ValueError("empty scene")
    return keccak256(f"sentinel-1-rtc:{item_id}".encode())


def evidence_rainfall(first: date, last: date) -> bytes:
    if last < first:
        raise ValueError("rainfall window runs backwards")
    return keccak256(f"{CHIRPS}:{first.isoformat()}:{last.isoformat()}".encode())


def event_bounds(start: date, end: date) -> tuple[int, int]:
    """Inclusive calendar dates as a unix window that covers the end date."""
    if end < start:
        raise ValueError("event window runs backwards")
    opened = _midnight(start)
    closed = _midnight(end + timedelta(days=1))
    return opened, closed


def _midnight(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
