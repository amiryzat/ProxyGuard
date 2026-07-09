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
import hashlib
import io
import os
import re
import sys
from datetime import datetime

from flask import Flask, render_template, request, send_from_directory, abort, jsonify, Response

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

# Poll interval (seconds) for the smart-refresh check (Phase D5). Defined
# once here and passed into the template so the "checking every Xs" label can
# never drift out of sync with the actual poll timer -- both read this value.
REFRESH_SECONDS = 7

# ---- Phase E1: lecturer review data layer ----------------------------------
# Review decisions ("was this attempt actually suspicious?") are stored
# entirely separately from logs/attendance.csv -- that file stays the raw,
# untouched system-generated record. logs/reviews.csv is a small, independent
# CSV of review decisions keyed by a deterministic hash of the attendance
# row's own identifying fields, since attendance.csv has no id column and is
# not the dashboard's file to redesign.
REVIEWS_PATH = os.path.join(SCRIPT_DIR, "..", "logs", "reviews.csv")
REVIEW_HEADERS = ["review_id", "session_id", "date", "time", "name", "result", "reason",
                   "review_status", "review_note", "reviewed_at"]
REVIEW_STATUSES = {"unreviewed", "accepted", "suspicious"}


def build_review_id(session_id, date, time_str, name, result, reason):
    """
    Deterministic key for one attendance attempt, derived from the same
    fields that identify it in attendance.csv (session_id/date/time/name/
    result/reason). Same inputs always produce the same review_id, so a
    lecturer's review survives reloads/exports without adding an id column
    to attendance.csv itself. Not a security hash -- just a stable, safe-as-
    a-filename-or-CSV-cell slug, so a fast truncated sha256 is enough.
    """
    raw = "|".join([session_id or "", date or "", time_str or "", name or "", result or "", reason or ""])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def read_reviews(reviews_path=None):
    """All review records keyed by review_id. Empty dict if none recorded yet
    (attendance rows with no matching entry are simply "unreviewed").
    reviews_path defaults to the live REVIEWS_PATH global read at call time
    (not a def-time snapshot -- a `reviews_path=REVIEWS_PATH` default would
    bind once at import and silently ignore any later override, e.g. in
    tests that point REVIEWS_PATH at a temp file)."""
    reviews_path = reviews_path or REVIEWS_PATH
    if not os.path.exists(reviews_path):
        return {}
    with open(reviews_path, newline="") as f:
        return {row["review_id"]: row for row in csv.DictReader(f)}


def get_review_for_row(cells, reviews):
    """
    review_status/review_note/reviewed_at for one attendance row's cells
    dict, defaulting to "unreviewed"/""/"" when no review record exists yet
    (requirement: an attendance row with no review record is unreviewed).
    """
    review_id = build_review_id(
        cells.get("session_id"), cells.get("date"), cells.get("time"),
        cells.get("name"), cells.get("result"), cells.get("reason"),
    )
    record = reviews.get(review_id)
    if record is None:
        return {"review_status": "unreviewed", "review_note": "", "reviewed_at": ""}
    return {
        "review_status": record.get("review_status", "unreviewed"),
        "review_note": record.get("review_note", ""),
        "reviewed_at": record.get("reviewed_at", ""),
    }


def write_review(session_id, date, time_str, name, result, reason, review_status, review_note):
    """
    Upsert one review record. logs/reviews.csv holds one row per reviewed
    attempt (not per poll/refresh), so at this prototype's scale a full
    read-modify-write on every call is simple and fine -- no locking beyond
    what a single-lecturer dashboard needs.
    # ponytail: read-modify-write, not append-only -- fine for a handful of
    # reviews per session; move to per-row file locking if this ever needs
    # concurrent writers.
    """
    if review_status not in REVIEW_STATUSES:
        raise ValueError(f"invalid review_status: {review_status!r}")

    review_id = build_review_id(session_id, date, time_str, name, result, reason)
    reviews = read_reviews()
    reviews[review_id] = {
        "review_id": review_id,
        "session_id": session_id or "",
        "date": date or "",
        "time": time_str or "",
        "name": name or "",
        "result": result or "",
        "reason": reason or "",
        "review_status": review_status,
        "review_note": review_note or "",
        "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    os.makedirs(os.path.dirname(REVIEWS_PATH), exist_ok=True)
    with open(REVIEWS_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_HEADERS)
        writer.writeheader()
        for row in reviews.values():
            writer.writerow(row)

    return review_id


def get_attendance_version():
    """
    Cheap change-detection signal for Phase D5 smart refresh: the CSV's
    mtime + size. Every terminal check-in outcome appends exactly one row to
    this file (see CheckinSession in src/main.py) and saves its snapshot in
    the same moment, so "has the CSV changed" is a reliable proxy for "is
    there new attendance/snapshot data" without needing to separately stat
    logs/snapshots/ or hash the file contents. Returns a stable placeholder
    if the log doesn't exist yet, so /status and index() never see an
    exception from a session with no check-ins yet.
    """
    if not os.path.exists(LOG_PATH):
        return "no-log"
    stat = os.stat(LOG_PATH)
    return f"{stat.st_mtime_ns}-{stat.st_size}"


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


def resolve_selected_session(sessions):
    """
    ?session=... if it names a real session, else the most recent one (or
    None if there are no sessions yet). Shared by index() and export_csv()
    so the two routes can never disagree about what "no ?session=" means.
    """
    selected_session = request.args.get("session")
    if selected_session not in sessions:
        selected_session = sessions[0] if sessions else None
    return selected_session


def build_session_display_rows(rows, selected_session):
    """
    display_rows (cells + flagged + snapshot) for one session -- shared by
    index() and export_csv() (Phase D6) so the on-page table and the CSV
    export are always built from the exact same flagging/snapshot-matching
    logic, not a second, potentially-drifting copy of it.
    """
    filtered_rows = [r for r in rows if r.get("session_id") == selected_session]
    report = pattern_flagger.flag_patterns(LOG_PATH)
    snapshot_files = list_snapshot_files()
    return [
        {
            "cells": r,
            "flagged": is_row_flagged(r, report),
            "snapshot": find_snapshot_for_row(r, snapshot_files),
        }
        for r in filtered_rows
    ]


def matches_quick_filter(display_row, quick_filter):
    """
    Server-side mirror of rowMatchesQuickFilter() in dashboard.js (Phase D6
    export). A CSV download is a fresh request, not a DOM read, so the same
    small set of predicates is reimplemented here rather than shared code --
    kept in lockstep by using the exact same fields/reason constants the
    client-side version and build_session_analytics() already use.
    """
    result = display_row["cells"].get("result")
    if quick_filter == "success":
        return result == "success"
    if quick_filter == "failed":
        return result == "failed"
    if quick_filter == "flagged":
        return display_row["flagged"]
    if quick_filter == "unknown":
        return display_row["cells"].get("name") == "Unknown" \
            or display_row["cells"].get("reason") == pattern_flagger.NOT_RECOGNIZED_REASON
    if quick_filter == "duplicate":
        return display_row["cells"].get("reason") == pattern_flagger.DUPLICATE_REASON
    if quick_filter == "liveness":
        return "liveness" in (display_row["cells"].get("reason") or "").lower()
    return True  # "all" (or an unrecognized value) -- no filtering


def matches_review_filter(display_row, review_filter):
    """
    Server-side mirror of rowMatchesReviewFilter() in dashboard.js (Phase E3).
    display_row must already carry a "review" key (see get_review_for_row()).
    """
    if review_filter in REVIEW_STATUSES:
        return display_row["review"]["review_status"] == review_filter
    return True  # "all" (or an unrecognized value) -- no filtering


def build_review_summary(attempt_rows_with_review):
    """
    Unreviewed/Accepted/Suspicious counts across the selected session's
    Attempts rows (Phase E3) -- same session-wide-but-Attempts-scoped pattern
    as Reason Breakdown: computed from the full attempt_rows_all (every row
    already carries a "review" key by the time this is called), not narrowed
    by the quick/review filters or search, so the summary always reflects the
    whole session regardless of what's currently filtered into view.
    """
    counts = {"unreviewed": 0, "accepted": 0, "suspicious": 0}
    for d in attempt_rows_with_review:
        counts[d["review"]["review_status"]] += 1
    return counts


SESSION_ID_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}_\d{4}_(?P<code>[A-Za-z0-9]+)_Week(?P<week>\d+)$")


def build_export_filename(session_id, tab):
    """
    proxyguard_<CODE>_Week<N>_<tab>_<today>.csv when session_id matches the
    class_config.build_session_id() format -- best-effort regex, not a hard
    dependency on that format, since session_id is otherwise treated as an
    opaque string throughout this project (see docs/architecture.md). Falls
    back to the session_id verbatim when it doesn't match, per the spec's
    own fallback.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    match = SESSION_ID_PATTERN.match(session_id or "")
    base = f"{match.group('code')}_Week{match.group('week')}" if match else (session_id or "unknown_session")
    return f"proxyguard_{base}_{tab}_{today}.csv"


@app.route("/")
def index():
    rows = read_attendance_rows()
    sessions = unique_sessions(rows)

    # Default to the most recent session on first load (no ?session=... yet),
    # rather than dumping the entire log history. Fall back to the most
    # recent session too if the requested one isn't found.
    selected_session = resolve_selected_session(sessions)

    # Reuse the existing flagging logic from src/pattern_flagger.py to mark
    # which visible rows are part of a suspicious pattern. Each display row
    # carries its raw cells plus a `flagged` flag the template uses to
    # highlight it; the underlying columns/order are unchanged.
    display_rows = build_session_display_rows(rows, selected_session)

    # Phase B: split the session's rows into the two tabs by `result`, rather
    # than showing one combined table. attendance_logger.py's `result` column
    # is always exactly "success" or "failed" (see CSV_HEADERS/schema), so
    # every display row lands in exactly one of these two tabs -- nothing is
    # dropped or double-counted.
    present_rows = [d for d in display_rows if d["cells"].get("result") == "success"]
    attempt_rows_all = [d for d in display_rows if d["cells"].get("result") == "failed"]

    # Phase E2: attach each row's review decision (Phase E1 data layer) to
    # every Attempts row for the session, before any reason/review filter
    # narrows it -- so build_review_summary() below always reflects the whole
    # session, and the reason/review filters can each independently narrow
    # from the same fully-enriched list. Present rows never get a "review"
    # key at all -- the template gates the whole column on `row.review is
    # defined`, keeping Present clean with zero extra work.
    reviews = read_reviews()
    for d in attempt_rows_all:
        d["review"] = get_review_for_row(d["cells"], reviews)
    review_summary = build_review_summary(attempt_rows_all)

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

    # Note: unlike selected_reason above, review_filter (like quick_filter) is
    # never read here -- both are pure client-side/localStorage-driven chips
    # (see dashboard.js), instantly re-filtering the already-rendered rows
    # with no page reload. Only /export.csv reads ?review_filter= server-side,
    # the same division of labor already used for ?quick_filter=.

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
        review_summary=review_summary,
        refresh_seconds=REFRESH_SECONDS,
        # Phase D5: the version this page was rendered with, so dashboard.js
        # has a baseline to compare each /status poll against without an
        # extra round trip on load.
        attendance_version=get_attendance_version(),
        # Phase D4: passed through so render_table can tag each row with a
        # data-unknown/data-duplicate attribute for the client-side quick
        # filters, reusing these constants instead of hardcoding the reason
        # strings a second time in the template.
        not_recognized_reason=pattern_flagger.NOT_RECOGNIZED_REASON,
        duplicate_reason=pattern_flagger.DUPLICATE_REASON,
    )


@app.route("/status")
def status():
    """
    Lightweight JSON endpoint (Phase D5) for dashboard.js to poll instead of
    blindly reloading the whole page every REFRESH_SECONDS. Cheap: a single
    os.stat() call, no CSV parsing, no pattern_flagger run.
    """
    return jsonify({"version": get_attendance_version()})


@app.route("/export.csv")
def export_csv():
    """
    Server-side CSV export (Phase D6) mirroring exactly what the lecturer is
    currently looking at: session (?session=, same param the dashboard table
    uses), tab (?tab=present/attempts -> result success/failed), and the
    same search/quick-filter/review-filter predicates dashboard.js applies
    client-side (?search=, ?quick_filter=, ?review_filter=). Reimplemented
    server-side rather than reading the DOM, since a file download is a fresh
    request with no client-side row list to hand over -- see
    build_session_display_rows()/matches_quick_filter()/
    matches_review_filter() above, shared with index() and dashboard.js.
    """
    rows = read_attendance_rows()
    sessions = unique_sessions(rows)
    selected_session = resolve_selected_session(sessions)

    tab = request.args.get("tab") or "present"
    if tab not in ("present", "attempts"):
        tab = "present"
    search = (request.args.get("search") or "").strip().lower()
    quick_filter = request.args.get("quick_filter") or "all"
    review_filter = request.args.get("review_filter") or "all"

    display_rows = build_session_display_rows(rows, selected_session)

    # Phase E1/E3: attach each row's review decision before filtering, so
    # matches_review_filter() and the CSV columns below both read the same
    # already-computed value instead of looking it up twice.
    reviews = read_reviews()
    for d in display_rows:
        d["review"] = get_review_for_row(d["cells"], reviews)

    wanted_result = "success" if tab == "present" else "failed"
    export_rows = [
        d for d in display_rows
        if d["cells"].get("result") == wanted_result
        and (not search or search in (d["cells"].get("name") or "").lower())
        and matches_quick_filter(d, quick_filter)
        and matches_review_filter(d, review_filter)
    ]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS + ["snapshot", "review_status", "review_note", "reviewed_at"])
    for d in export_rows:
        writer.writerow(
            [d["cells"].get(header, "") for header in CSV_HEADERS]
            + [d["snapshot"] or "", d["review"]["review_status"], d["review"]["review_note"], d["review"]["reviewed_at"]]
        )

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{build_export_filename(selected_session, tab)}"'},
    )


@app.route("/review", methods=["POST"])
def review():
    """
    Record a lecturer's review decision for one attendance attempt (Phase E1
    data layer -- no visible UI wired to this yet). attendance.csv is never
    touched; this only ever reads/writes logs/reviews.csv.

    Accepts either:
      - session_id/date/time/name/result/reason (the row's own identifying
        fields, matching build_review_id()) -- creates or updates that
        attempt's review, or
      - review_id alone -- updates just review_status/review_note on an
        attempt already reviewed once (its stored identity fields are reused
        rather than re-sent).
    """
    data = request.get_json(silent=True) or request.form

    review_status = data.get("review_status", "")
    if review_status not in REVIEW_STATUSES:
        return jsonify({"error": "invalid review_status"}), 400
    review_note = data.get("review_note", "")

    session_id = data.get("session_id", "")
    date = data.get("date", "")
    time_str = data.get("time", "")
    name = data.get("name", "")
    result = data.get("result", "")
    reason = data.get("reason", "")

    if not (session_id and date and time_str and name and result and reason):
        review_id = data.get("review_id", "")
        if not review_id:
            return jsonify({"error": "provide review_id, or session_id/date/time/name/result/reason"}), 400
        existing = read_reviews().get(review_id)
        if existing is None:
            return jsonify({"error": "unknown review_id"}), 404
        session_id, date, time_str = existing["session_id"], existing["date"], existing["time"]
        name, result, reason = existing["name"], existing["result"], existing["reason"]

    new_review_id = write_review(session_id, date, time_str, name, result, reason, review_status, review_note)
    return jsonify({"review_id": new_review_id, "review_status": review_status, "review_note": review_note})


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
