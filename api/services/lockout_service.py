"""In-memory account lockout tracker for brute-force protection.

Policy:
  - 5 consecutive failed login attempts within a 15-minute window locks the account.
  - Lockout duration: 15 minutes from the last failure.
  - A successful login clears the failure counter.
  - Counters are per-email (case-insensitive).

This is in-memory and does not survive restarts, which is acceptable for a
single-worker deployment. If the service restarts, counters reset — a minor
gap that is preferable to adding a dependency on Redis.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field

_MAX_FAILURES = 5
_WINDOW_MINUTES = 15
_LOCKOUT_MINUTES = 15


@dataclass
class _Record:
    failures: int = 0
    first_failure_at: datetime | None = None
    locked_until: datetime | None = None


_records: dict[str, _Record] = {}
_lock = threading.Lock()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_locked(email: str) -> bool:
    """Return True if the account is currently locked out."""
    key = email.lower().strip()
    with _lock:
        rec = _records.get(key)
        if rec is None:
            return False
        if rec.locked_until and _now() < rec.locked_until:
            return True
        if rec.locked_until:
            # Lockout expired — clear the record
            del _records[key]
        return False


def record_failure(email: str) -> bool:
    """Record a failed login attempt. Returns True if the account just became locked."""
    key = email.lower().strip()
    now = _now()
    with _lock:
        rec = _records.setdefault(key, _Record())

        # Reset window if first failure is older than the window
        if rec.first_failure_at and (now - rec.first_failure_at) > timedelta(minutes=_WINDOW_MINUTES):
            rec.failures = 0
            rec.first_failure_at = None

        if rec.first_failure_at is None:
            rec.first_failure_at = now

        rec.failures += 1

        if rec.failures >= _MAX_FAILURES:
            rec.locked_until = now + timedelta(minutes=_LOCKOUT_MINUTES)
            return True

        return False


def record_success(email: str) -> None:
    """Clear failure counter after a successful login."""
    key = email.lower().strip()
    with _lock:
        _records.pop(key, None)


def lockout_remaining_seconds(email: str) -> int:
    """Return seconds remaining on a lockout, or 0 if not locked."""
    key = email.lower().strip()
    with _lock:
        rec = _records.get(key)
        if rec and rec.locked_until:
            remaining = (rec.locked_until - _now()).total_seconds()
            return max(0, int(remaining))
        return 0
