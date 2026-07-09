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

from flask import Flask, render_template, request, send_from_directory, abort

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

# Verification snapshots live alongside the log, in logs/snapshots/. main.py
# writes one per terminal outcome (see below for the filename format).
SNAPSHOT_DIR = os.path.join(SCRIPT_DIR, "..", "logs", "snapshots")

# Column order matches the CSV schema written by attendance_logger.py.
CSV_HEADERS = ["name", "date", "time", "session_id", "result", "reason"]

# Auto-refresh interval (seconds), already implemented as a client-side
# setInterval reload in index.html. Defined once here and passed into the
# template so the "Auto-refresh every Xs" label can never drift out of sync
# with the actual reload timer -- both read this single value.
REFRESH_SECONDS = 7


def _slug(text):
    """
    Mirror of the `slug()` helper inside build_snapshot_filename() in
    src/main.py, so the dashboard reconstructs the same name/reason portions
    that appear in snapshot filenames: lowercase, every non-alphanumeric
    character becomes "_", surrounding "_" stripped, and an empty result
    falls back to "unknown". (Reimplemented rather than imported, since
    importing main.py would pull in cv2/mediapipe/dlib.)
    """
    return "".join(c if c.isalnum() else "_" for c in (text or "")).strip("_").lower() or "unknown"


def list_snapshot_files(snapshot_dir=SNAPSHOT_DIR):
    """All .jpg snapshot filenames currently in logs/snapshots/ (empty if the
    folder doesn't exist yet). Listed once per request and reused across rows."""
    if not os.path.isdir(snapshot_dir):
        return []
    return [f for f in os.listdir(snapshot_dir) if f.lower().endswith(".jpg")]


def find_snapshot_for_row(row, snapshot_files):
    """
    Match an attendance row to its verification snapshot filename.

    main.py builds snapshot names as:
        {session_id}_{slug(name)}_{slug(reason)}_{HHMMSS}.jpg
    with session_id left raw and name/reason slugged. We rebuild that prefix
    from the row's session_id/name/reason and return the file that starts with
    it. When one session has several rows sharing the same (name, reason)
    prefix -- e.g. repeated failed attempts -- we disambiguate with the row's
    `time` (HH:MM:SS -> HHMMSS), which the snapshot's trailing timestamp was
    generated from at the same moment. Returns None if nothing matches.
    """
    session_id = row.get("session_id") or ""
    time_key = (row.get("time") or "").replace(":", "")
    prefix = f"{session_id}_{_slug(row.get('name'))}_{_slug(row.get('reason'))}_"

    candidates = [f for f in snapshot_files if f.startswith(prefix)]
    if candidates:
        if len(candidates) == 1:
            return candidates[0]
        # Several attempts share the prefix -> prefer the exact timestamp match.
        exact = f"{prefix}{time_key}.jpg"
        return exact if exact in candidates else candidates[0]

    # ponytail: name mismatch fallback. main.py names the snapshot after
    # last_known_name (the last confidently recognized identity), but a FAILED
    # attempt logs the CSV row under "Unknown" (confirmed_name is None on
    # failure) -- e.g. a recognized student who then fails the liveness
    # challenge. So the name segment can differ between the CSV row and its
    # own snapshot file, even though both were written at the same moment.
    # session_id + reason + the row's own HHMMSS timestamp is still unique per
    # attempt, so match on that instead of the name segment.
    if time_key:
        suffix = f"_{_slug(row.get('reason'))}_{time_key}.jpg"
        for f in snapshot_files:
            if f.startswith(f"{session_id}_") and f.endswith(suffix):
                return f
    return None


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


def unique_reasons(display_subset):
    """
    Distinct `reason` values among a subset of already-built display rows
    (dicts with a "cells" key), ordered by first appearance. display_subset is
    newest-first (it's built from read_attendance_rows' order), so this lists
    reasons in order of most-recent occurrence, mirroring unique_sessions().
    """
    reasons = []
    for d in display_subset:
        reason = d["cells"].get("reason")
        if reason and reason not in reasons:
            reasons.append(reason)
    return reasons


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


def classify_reason(reason):
    """
    Maps a `reason` string to a rough good/warn/bad severity for coloring the
    Reason Breakdown (Phase D2). Data-driven substring matching, the same
    style already used in build_session_analytics(), rather than a fixed
    whitelist -- so a reason this project hasn't seen yet (e.g. a future
    "identity mismatch"/"face changed" outcome) still gets a sensible color
    instead of falling through unstyled.
    """
    reason = (reason or "").lower()
    if reason == "confirmed":
        return "good"
    if "liveness" in reason:
        return "bad"
    if "duplicate" in reason:
        return "warn"
    if "not recognized" in reason or "unknown" in reason:
        return "warn"
    return "bad"  # anything else (mismatch, changed/blocked, etc.) is non-routine -> caution


def build_reason_breakdown(display_rows):
    """
    Counts per `reason` across the selected session (Phase D2), sorted by
    count descending so the most common outcomes stand out first. Scope
    matches build_session_analytics() -- the full session, not narrowed by
    the Attempts-tab reason filter -- since the point of a breakdown is to
    show all reasons at a glance, including whichever one the filter has
    currently narrowed to.
    """
    counts = {}
    for d in display_rows:
        reason = d["cells"].get("reason") or "(none)"
        counts[reason] = counts.get(reason, 0) + 1

    total = len(display_rows)
    breakdown = [
        {
            "reason": reason,
            "count": count,
            "pct": round(count / total * 100, 1) if total else 0,
            "level": classify_reason(reason),
        }
        for reason, count in counts.items()
    ]
    breakdown.sort(key=lambda item: item["count"], reverse=True)
    return breakdown


def build_session_analytics(display_rows):
    """
    Session-wide analytics cards (Phase D1). Unlike build_summary() (scoped
    per tab), this always covers the FULL selected session -- Present and
    Attempts combined -- since a lecturer wants one at-a-glance picture of the
    session regardless of which tab is open. Built purely from the
    already-computed display_rows (same rows/flags used everywhere else on
    the page): no extra CSV read, no extra pattern_flagger call, and no
    suspicious-pattern rules reimplemented -- `flagged` reuses each row's
    already-computed flag from is_row_flagged().
    """
    total = len(display_rows)
    successful = sum(1 for d in display_rows if d["cells"].get("result") == "success")
    failed = sum(1 for d in display_rows if d["cells"].get("result") == "failed")
    duplicate = sum(1 for d in display_rows if d["cells"].get("reason") == pattern_flagger.DUPLICATE_REASON)
    unknown = sum(
        1 for d in display_rows
        if d["cells"].get("name") == "Unknown" or d["cells"].get("reason") == pattern_flagger.NOT_RECOGNIZED_REASON
    )
    liveness_failures = sum(1 for d in display_rows if "liveness" in (d["cells"].get("reason") or "").lower())

    return {
        "total": total,
        "successful": successful,
        "failed": failed,
        "flagged": sum(1 for d in display_rows if d["flagged"]),
        "duplicate": duplicate,
        "unknown": unknown,
        "liveness_failures": liveness_failures,
        "success_rate": round(successful / total * 100, 1) if total else 0,
    }


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
    # List the snapshot folder once, then match each visible row to its file.
    snapshot_files = list_snapshot_files()
    display_rows = [
        {
            "cells": r,
            "flagged": is_row_flagged(r, report),
            "snapshot": find_snapshot_for_row(r, snapshot_files),
        }
        for r in filtered_rows
    ]

    # Phase B: split the session's rows into the two tabs by `result`, rather
    # than showing one combined table. attendance_logger.py's `result` column
    # is always exactly "success" or "failed" (see CSV_HEADERS/schema), so
    # every display row lands in exactly one of these two tabs -- nothing is
    # dropped or double-counted.
    present_rows = [d for d in display_rows if d["cells"].get("result") == "success"]
    attempt_rows_all = [d for d in display_rows if d["cells"].get("result") == "failed"]

    # Phase C: reason filter, scoped to the Attempts tab and applied on top of
    # the session filter (not instead of it) -- options are the distinct
    # reasons among *this session's* failed rows (attempt_rows_all, before the
    # reason filter itself is applied), so the dropdown always matches what's
    # actually in the currently selected session rather than the whole log.
    reasons = unique_reasons(attempt_rows_all)
    selected_reason = request.args.get("reason") or "all"
    if selected_reason != "all" and selected_reason not in reasons:
        # Stale/invalid reason (e.g. left over after switching to a session
        # that doesn't have it) -- fall back to "all", same defensive pattern
        # used for selected_session above, instead of silently showing nothing.
        selected_reason = "all"

    if selected_reason == "all":
        attempt_rows = attempt_rows_all
    else:
        attempt_rows = [d for d in attempt_rows_all if d["cells"].get("reason") == selected_reason]

    # Which tab should render as active. Explicit ?tab=... wins; otherwise a
    # ?reason=... in the URL implies the user was narrowing Attempts (e.g. a
    # bookmarked/shared link), so default to that tab; plain "/" defaults to
    # Present, matching Phase B's original behavior.
    active_tab = request.args.get("tab") or ("attempts" if "reason" in request.args else "present")
    if active_tab not in ("present", "attempts"):
        active_tab = "present"

    # Session-wide overview cards (Phase D1) and reason breakdown (Phase D2)
    # -- both from display_rows, i.e. the full selected session before the
    # tab split above, so they stay correct regardless of which tab is open
    # or how the Attempts-tab reason filter narrowed it. This replaces the
    # old per-tab mini summaries (Phase B), which duplicated these same
    # numbers in a second, smaller summary section -- removed rather than
    # kept alongside, per Phase D2.
    session_analytics = build_session_analytics(display_rows)
    reason_breakdown = build_reason_breakdown(display_rows)

    return render_template(
        "index.html",
        headers=CSV_HEADERS,
        present_rows=present_rows,
        attempt_rows=attempt_rows,
        sessions=sessions,
        selected_session=selected_session,
        reasons=reasons,
        selected_reason=selected_reason,
        active_tab=active_tab,
        session_analytics=session_analytics,
        reason_breakdown=reason_breakdown,
        refresh_seconds=REFRESH_SECONDS,
    )


@app.route("/snapshot/<path:filename>")
def snapshot(filename):
    """
    Serve a verification snapshot image from logs/snapshots/ for inline display
    in the attendance table. send_from_directory safe-joins the path, so it
    can't be used to read files outside the snapshot folder.
    """
    if not os.path.isdir(SNAPSHOT_DIR):
        abort(404)
    return send_from_directory(SNAPSHOT_DIR, filename)


if __name__ == "__main__":
    # debug=True for local development convenience; this is a lecturer-facing
    # tool run locally, not a production deployment.
    # Port 5001 (not Flask's default 5000) to avoid macOS AirPlay Receiver,
    # which occupies port 5000 and returns a 403 for any other request.
    app.run(debug=True, port=5001)
