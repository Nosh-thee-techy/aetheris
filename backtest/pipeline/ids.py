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


def event_week(week: str) -> bytes:
    """bytes32 week id. The label log writes the week as start/end."""
    if "/" not in week:
        raise ValueError("week must be start/end")
    return keccak256(week.encode())


def trigger_id(zone: bytes, week: bytes, rule: bytes, thresholds: bytes) -> bytes:
    """keccak256(abi.encode(zoneId, eventWeek, ruleId, thresholdsHash)).

    abi.encode of four bytes32 values is their concatenation.
    """
    parts = (zone, week, rule, thresholds)
    if any(len(part) != 32 for part in parts):
        raise ValueError("trigger id parts are bytes32")
    return keccak256(b"".join(parts))


def event_bounds(start: date, end: date) -> tuple[int, int]:
    """Inclusive calendar dates as a unix window that covers the end date."""
    if end < start:
        raise ValueError("event window runs backwards")
    opened = _midnight(start)
    closed = _midnight(end + timedelta(days=1))
    return opened, closed


def _midnight(day: date) -> int:
    return int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
