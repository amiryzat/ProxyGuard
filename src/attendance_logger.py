# src/attendance_logger.py
# Logs check-in attempts to logs/attendance.csv and flags suspicious patterns
# (e.g. identical head angles across attempts, repeated liveness failures) for lecturer review.
#
# Every attempt gets logged, not just successful ones -- failed/incomplete
# attempts are exactly what the pattern flagging step (pattern_flagger.py)
# needs to analyze, so they're written to the same CSV with a "failed"
# result and a specific human-readable reason instead of being discarded.

import csv
import os
from datetime import datetime

# Resolve the log file relative to this script's own location, matching
# the convention used in face_recognizer.py, so it works the same
# regardless of what directory the script is run from.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_PATH = os.path.join(SCRIPT_DIR, "..", "logs", "attendance.csv")

# result is always "success" or "failed"; reason is a short human-readable
# string describing the specific outcome (e.g. "confirmed", "voice mismatch").
CSV_HEADERS = ["name", "date", "time", "session_id", "result", "reason"]

DUPLICATE_REASON = "duplicate check-in this session"


def _ensure_log_file(log_path):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
        with open(log_path, newline="") as f:
            existing_header = next(csv.reader(f), [])
        if existing_header != CSV_HEADERS:
            # Schema changed (old single "status" column -> session_id +
            # result + reason). Archive the old file instead of silently
            # overwriting it or mixing two row formats in one CSV.
            legacy_path = os.path.join(os.path.dirname(log_path), "attendance_legacy.csv")
            os.replace(log_path, legacy_path)

    if not os.path.exists(log_path) or os.path.getsize(log_path) == 0:
        with open(log_path, "w", newline="") as f:
            csv.writer(f).writerow(CSV_HEADERS)


def has_success_this_session(name, session_id, log_path=DEFAULT_LOG_PATH):
    """
    Checks whether `name` already has a "success" row for this session_id.
    Duplicate detection is scoped to a session rather than a calendar date,
    since a single room/date can host multiple separate class sessions --
    a date-based check would wrongly treat two different classes as
    duplicates of each other, or block a legitimate re-check-in in a later
    class the same day.
    """
    if not os.path.exists(log_path):
        return False

    with open(log_path, newline="") as f:
        for row in csv.DictReader(f):
            if row["name"] == name and row["session_id"] == session_id and row["result"] == "success":
                return True
    return False


def log_attendance(name, result, reason, session_id, log_path=DEFAULT_LOG_PATH):
    """
    Appends one row (name, date, time, session_id, result, reason) to
    logs/attendance.csv, creating the file with headers first if it
    doesn't exist yet (or migrating an old-schema file out of the way,
    see _ensure_log_file).

    A "success" result is downgraded to "failed" / DUPLICATE_REASON if
    this person already has a successful check-in for this same
    session_id, so attendance records stay accurate even if the check-in
    flow is re-run within one session. Failed/incomplete outcomes are
    logged as-is every time (no dedup), since repeated failures are
    themselves useful signal for pattern_flagger.py.

    Returns the (result, reason) actually written (which may differ from
    what was passed in, if it was downgraded to a duplicate).
    """
    _ensure_log_file(log_path)

    name = name or "Unknown"

    if result == "success" and has_success_this_session(name, session_id, log_path):
        result = "failed"
        reason = DUPLICATE_REASON

    now = datetime.now()
    with open(log_path, "a", newline="") as f:
        csv.writer(f).writerow([
            name,
            now.strftime("%Y-%m-%d"),
            now.strftime("%H:%M:%S"),
            session_id,
            result,
            reason,
        ])

    return result, reason


if __name__ == "__main__":
    # Manual smoke test: logs a few sample rows under two different fake
    # session_ids so the CSV output and the session-scoped duplicate
    # logic can both be checked without running the full webcam flow.
    session_a = "2026-07-05_1900"
    session_b = "2026-07-05_2030"

    print("Session A: confirmed check-in...")
    print(" ->", log_attendance("Test Student", "success", "confirmed", session_a))

    print("Session A: failed liveness attempt...")
    print(" ->", log_attendance("Test Student", "failed", "liveness timeout", session_a))

    print("Session A: second confirmed attempt, same session (expect duplicate downgrade)...")
    print(" ->", log_attendance("Test Student", "success", "confirmed", session_a))

    print("Session B: confirmed attempt for the same student, different session (should NOT be a duplicate)...")
    print(" ->", log_attendance("Test Student", "success", "confirmed", session_b))

    print(f"Done. Check {DEFAULT_LOG_PATH}")
