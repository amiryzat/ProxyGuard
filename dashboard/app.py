# dashboard/app.py
# Phase 1 of the lecturer-facing dashboard.
#
# A small, standalone Flask app that reads logs/attendance.csv and shows it
# as a plain HTML table (newest entries first). This lives in its own
# top-level `dashboard/` folder rather than inside src/, keeping it separate
# from the core detection modules and matching the project's convention of
# independent, self-contained modules.
#
# Phase 1 is intentionally minimal: raw table only. No auth, filtering,
# highlighting, summaries, or pattern-flagging integration -- those come in
# later phases.

import csv
import os
import sys

from flask import Flask, render_template, request

# Make the core detection modules in src/ importable so we can reuse the
# existing flagging logic instead of duplicating it here. pattern_flagger
# only depends on the stdlib (csv/os/collections/datetime), so importing it
# stays cheap and doesn't pull in cv2/mediapipe.
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import pattern_flagger

app = Flask(__name__)

# Resolve the log file relative to this script's own location (not the
# current working directory), mirroring attendance_logger.py so the
# dashboard finds the same CSV no matter where it's launched from.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(SCRIPT_DIR, "..", "logs", "attendance.csv")

# Column order matches the CSV schema written by attendance_logger.py.
CSV_HEADERS = ["name", "date", "time", "session_id", "result", "reason"]


def read_attendance_rows(log_path=LOG_PATH):
    """
    Reads attendance.csv and returns its rows as a list of dicts, ordered
    most-recent-first. Returns an empty list if the log file doesn't exist
    yet (e.g. no check-ins have been run), so the page still renders.
    """
    if not os.path.exists(log_path):
        return []

    with open(log_path, newline="") as f:
        rows = list(csv.DictReader(f))

    # The CSV is appended to in chronological order, so reversing gives
    # newest-first without needing to parse/sort dates.
    rows.reverse()
    return rows


def unique_sessions(rows):
    """
    Returns the distinct session_id values in `rows`, ordered most-recent
    first. `rows` is already newest-first (see read_attendance_rows), so
    collecting session_ids in order of first appearance here yields sessions
    ordered by most-recent activity, without parsing the session timestamp.
    """
    sessions = []
    for row in rows:
        sid = row.get("session_id")
        if sid and sid not in sessions:
            sessions.append(sid)
    return sessions


def is_row_flagged(row, report):
    """
    Decides whether a single attendance row belongs to one of the suspicious
    patterns already detected by pattern_flagger.flag_patterns(). The `report`
    is that function's output; we only read from it and reuse pattern_flagger's
    own reason constants, so none of the detection logic is duplicated here.

    - Repeated failures: a "failed" row whose name is a flagged repeat-offender
      identity (this check is whole-log by design in pattern_flagger).
    - Duplicate attempts: a duplicate-reason row whose (name, session_id) pair
      was flagged.
    - Unrecognized clusters: a "face not recognized" row in a session that
      pattern_flagger flagged as having a cluster. flag_patterns only reports
      which sessions cluster (not which individual rows), so within a flagged
      session we highlight all such rows.
    """
    name = row.get("name")
    session = row.get("session_id")

    if row.get("result") == "failed" and name in report["repeated_failures"]:
        return True

    if row.get("reason") == pattern_flagger.DUPLICATE_REASON and \
            (name, session) in report["duplicate_attempts"]:
        return True

    if row.get("reason") == pattern_flagger.NOT_RECOGNIZED_REASON and \
            session in report["unrecognized_clusters"]:
        return True

    return False


@app.route("/")
def index():
    rows = read_attendance_rows()
    sessions = unique_sessions(rows)

    # Default to the most recent session on first load (no ?session=... yet),
    # rather than dumping the entire log history. Fall back to the most
    # recent session too if the requested one isn't found.
    selected_session = request.args.get("session")
    if selected_session not in sessions:
        selected_session = sessions[0] if sessions else None

    # Rows are already newest-first; filtering preserves that order within
    # the selected session.
    filtered_rows = [r for r in rows if r.get("session_id") == selected_session]

    # Reuse the existing flagging logic from src/pattern_flagger.py to mark
    # which visible rows are part of a suspicious pattern. Each display row
    # carries its raw cells plus a `flagged` flag the template uses to
    # highlight it; the underlying columns/order are unchanged.
    report = pattern_flagger.flag_patterns(LOG_PATH)
    display_rows = [
        {"cells": r, "flagged": is_row_flagged(r, report)}
        for r in filtered_rows
    ]

    # Summary stats for the *selected session only*. These are counted over
    # the same display_rows built above, so the flagged count reuses the
    # Phase 3 flagging result rather than recomputing it.
    summary = {
        "total": len(display_rows),
        "successful": sum(1 for d in display_rows if d["cells"].get("result") == "success"),
        "failed": sum(1 for d in display_rows if d["cells"].get("result") == "failed"),
        "flagged": sum(1 for d in display_rows if d["flagged"]),
    }

    return render_template(
        "index.html",
        headers=CSV_HEADERS,
        rows=display_rows,
        sessions=sessions,
        selected_session=selected_session,
        summary=summary,
    )


if __name__ == "__main__":
    # debug=True for local development convenience; this is a lecturer-facing
    # tool run locally, not a production deployment.
    # Port 5001 (not Flask's default 5000) to avoid macOS AirPlay Receiver,
    # which occupies port 5000 and returns a 403 for any other request.
    app.run(debug=True, port=5001)
