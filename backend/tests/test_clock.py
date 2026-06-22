from __future__ import annotations

from datetime import UTC, datetime, timezone

from app.core import clock


def test_now_utc_is_aware_and_utc():
    n = clock.now_utc()
    assert n.tzinfo is not None
    assert n.utcoffset() == timezone.utc.utcoffset(None)
    # plausibel nahe an der echten Systemzeit
    assert abs((n - datetime.now(UTC)).total_seconds()) < 5


def test_now_local_uses_app_timezone():
    n = clock.now_local()
    assert n.tzinfo is not None
    assert "Europe/Berlin" in str(n.tzinfo)
    # explizite TZ wird respektiert
    assert "UTC" in str(clock.now_local("UTC").tzinfo)


def test_time_context_contains_systemclock_date_and_name():
    out = clock.time_context(name="Mefa")
    assert "AKTUELLE ZEIT" in out
    assert "Systemuhr" in out
    assert "Europe/Berlin" in out
    assert "Der Nutzer heißt Mefa." in out
    # enthält das aktuelle Jahr aus der Systemuhr
    assert str(clock.now_local().year) in out


def test_time_context_without_name_omits_name_line():
    out = clock.time_context()
    assert "Der Nutzer heißt" not in out
    assert "AKTUELLE ZEIT" in out
