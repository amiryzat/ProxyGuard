import csv
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_PATH = os.path.join(SCRIPT_DIR, "..", "logs", "attendance.csv")

CSV_HEADERS = ["name", "date", "time", "session_id", "result", "reason"]

DUPLICATE_REASON = "duplicate check-in this session"

def _ensure_log_file(log_path):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)

    if os.path.exists(log_path) and os.path.getsize(log_path) > 0:
        with open(log_path, newline="") as f:
            existing_header = next(csv.reader(f), [])
        if existing_header != CSV_HEADERS:
            legacy_path = os.path.join(os.path.dirname(log_path), "attendance_legacy.csv")
            os.replace(log_path, legacy_path)

    if not os.path.exists(log_path) or os.path.getsize(log_path) == 0:
        with open(log_path, "w", newline="") as f:
            csv.writer(f).writerow(CSV_HEADERS)

def has_success_this_session(name, session_id, log_path=DEFAULT_LOG_PATH):

    if not os.path.exists(log_path):
        return False

    with open(log_path, newline="") as f:
        for row in csv.DictReader(f):
            if row["name"] == name and row["session_id"] == session_id and row["result"] == "success":
                return True
    return False

def log_attendance(name, result, reason, session_id, log_path=DEFAULT_LOG_PATH):

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
