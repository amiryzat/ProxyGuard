# dashboard/test_analytics.py
# ponytail: single runnable self-check for build_session_analytics() (Phase D1
# session overview cards) and build_reason_breakdown()/classify_reason()
# (Phase D2 reason breakdown). Not a full test suite -- just enough to catch
# a broken count, a zero-division regression, or a miscolored reason.

from app import build_session_analytics, build_reason_breakdown, classify_reason


def _row(name, result, reason, flagged=False):
    return {"cells": {"name": name, "result": result, "reason": reason}, "flagged": flagged}


if __name__ == "__main__":
    rows = [
        _row("Amir", "success", "confirmed"),
        _row("Amir", "failed", "duplicate check-in this session"),
        _row("Unknown", "failed", "face not recognized"),
        _row("Unknown", "failed", "liveness timeout"),
        _row("Izzuddin", "failed", "liveness timeout", flagged=True),
    ]
    a = build_session_analytics(rows)
    assert a["total"] == 5
    assert a["successful"] == 1
    assert a["failed"] == 4
    assert a["flagged"] == 1
    assert a["duplicate"] == 1
    assert a["unknown"] == 2  # name=="Unknown" (2 rows) union reason==face-not-recognized (already counted)
    assert a["liveness_failures"] == 2
    assert a["success_rate"] == 20.0  # 1/5 * 100

    empty = build_session_analytics([])
    assert empty["total"] == 0
    assert empty["success_rate"] == 0  # no zero-division

    assert classify_reason("confirmed") == "good"
    assert classify_reason("liveness timeout") == "bad"
    assert classify_reason("duplicate check-in this session") == "warn"
    assert classify_reason("face not recognized") == "warn"
    assert classify_reason("something new nobody's seen yet") == "bad"  # unknown reason -> caution, not unstyled

    breakdown = build_reason_breakdown(rows)
    by_reason = {item["reason"]: item for item in breakdown}
    assert by_reason["liveness timeout"]["count"] == 2
    assert by_reason["liveness timeout"]["level"] == "bad"
    assert by_reason["confirmed"]["count"] == 1
    assert by_reason["confirmed"]["level"] == "good"
    assert breakdown[0]["count"] >= breakdown[-1]["count"]  # sorted descending
    assert sum(item["count"] for item in breakdown) == len(rows)
    assert build_reason_breakdown([]) == []

    print("dashboard analytics self-check passed")
