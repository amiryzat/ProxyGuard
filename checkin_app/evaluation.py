# checkin_app/evaluation.py
# Report Support Phase R1 (simplified automated evaluation mode): the data
# layer behind checkin_app's /evaluation page. Kept as its own small,
# independent module (matching the project's per-module-independence
# convention) rather than folded into app.py, and rather than importing
# dashboard/app.py's near-identical helpers -- that file is a full Flask app
# of its own with its own module-level setup, and importing it here just to
# reuse a handful of pure functions would be a much heavier coupling than
# reimplementing them (they're small). Only depends on the stdlib; app.py
# supplies the one real reuse point (attendance_logger.has_success_this_session)
# by importing it itself and passing the result in, so this module doesn't
# need its own sys.path/src/ wiring.
#
# Does NOT run any recognition of its own -- every trial's outcome is read
# back from logs/attendance.csv, which is only ever written by the shared
# CheckinSession the normal check-in flow already drives. This module only
# reads that file (never writes to it) and owns logs/evaluation_trials.csv.

import csv
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ATTENDANCE_PATH = os.path.join(SCRIPT_DIR, "..", "logs", "attendance.csv")
SNAPSHOT_DIR = os.path.join(SCRIPT_DIR, "..", "logs", "snapshots")
EVALUATION_PATH = os.path.join(SCRIPT_DIR, "..", "logs", "evaluation_trials.csv")

EVALUATION_HEADERS = [
    "trial_id", "participant_code", "participant_type", "scenario", "trial_number",
    "session_id", "expected_identity", "expected_result",
    "actual_identity", "actual_result", "actual_reason",
    "start_timestamp", "end_timestamp", "duration_seconds",
    # Evaluation Timing Phase R2: the engine's own monotonic-clock durations
    # (CheckinSession.timing_snapshot()), not just the wall-clock
    # start/end_timestamp difference duration_seconds already was. That
    # column is kept (for compatibility) but is now defined as equal to
    # decision_duration_seconds wherever the engine's timing was available --
    # see finalize_trial().
    "recognition_duration_seconds", "liveness_duration_seconds", "decision_duration_seconds",
    "passed", "notes", "snapshot_filename",
]

# ---- Participant mapping: one clear configuration structure -----------------
PARTICIPANTS = {
    "R1": {"type": "registered", "identity": "MOHAMAD AMIR IZZAT BIN ROSDI"},
    "R2": {"type": "registered", "identity": "MUHAMMAD ADLI FADHLAN BIN AZAME"},
    "R3": {"type": "registered", "identity": "MUHAMMAD IZZUDDIN BIN IZAD EMI"},
    "U1": {"type": "unknown", "identity": "Unknown"},
    "U2": {"type": "unknown", "identity": "Unknown"},
}

SCENARIOS = [
    "Genuine Check-in",
    "Unknown Person",
    "Deliberate Liveness Failure",
    "Duplicate Check-in",
    "Static Photo Attack",
]

# Only "Genuine Check-in" expects an actual success; every other scenario in
# this phase is a deliberate negative-path test.
_EXPECTED_RESULT = {
    "Genuine Check-in": "success",
    "Unknown Person": "failed",
    "Deliberate Liveness Failure": "failed",
    "Duplicate Check-in": "failed",
    "Static Photo Attack": "failed",
}


def expected_identity_for(participant_code):
    participant = PARTICIPANTS.get(participant_code)
    return participant["identity"] if participant else None


def expected_result_for(scenario):
    return _EXPECTED_RESULT.get(scenario)


def determine_pass(scenario, expected_identity, actual_identity, actual_result, actual_reason):
    """Grading rules exactly as specified for this phase. `scenario` is
    always one of SCENARIOS (validated at /evaluation/start), so every
    branch is covered -- no None/unknown-scenario fallback needed here."""
    reason = (actual_reason or "").lower()

    if scenario == "Genuine Check-in":
        return (actual_result == "success" and reason == "confirmed"
                and actual_identity == expected_identity)

    if scenario == "Unknown Person":
        return (actual_result == "failed" and actual_identity == "Unknown"
                and "face not recognized" in reason)

    if scenario == "Deliberate Liveness Failure":
        return (actual_identity == expected_identity and actual_result == "failed"
                and "liveness" in reason)

    if scenario == "Duplicate Check-in":
        return actual_result == "failed" and "duplicate check-in this session" in reason

    # Static Photo Attack
    return actual_result != "success"


def _slug(text):
    """Mirrors slug() inside build_snapshot_filename() in src/main.py exactly,
    so filenames built here match real snapshot files on disk."""
    return "".join(c if c.isalnum() else "_" for c in (text or "")).strip("_").lower() or "unknown"


def list_snapshot_files():
    if not os.path.isdir(SNAPSHOT_DIR):
        return []
    return [f for f in os.listdir(SNAPSHOT_DIR) if f.lower().endswith(".jpg")]


def find_snapshot_for_row(row, snapshot_files):
    """Same prefix-match approach as dashboard/app.py's find_snapshot_for_row
    (reimplemented independently -- see module docstring)."""
    session_id = row.get("session_id") or ""
    time_key = (row.get("time") or "").replace(":", "")
    prefix = f"{session_id}_{_slug(row.get('name'))}_{_slug(row.get('reason'))}_"

    candidates = [f for f in snapshot_files if f.startswith(prefix)]
    if candidates:
        if len(candidates) == 1:
            return candidates[0]
        exact = f"{prefix}{time_key}.jpg"
        return exact if exact in candidates else candidates[0]

    if time_key:
        suffix = f"_{_slug(row.get('reason'))}_{time_key}.jpg"
        for f in snapshot_files:
            if f.startswith(f"{session_id}_") and f.endswith(suffix):
                return f
    return None


def read_attendance_rows():
    """Newest-first, read-only -- never written to from here. Mirrors
    dashboard/app.py's read_attendance_rows() (reimplemented independently,
    same reasoning as find_snapshot_for_row above)."""
    if not os.path.exists(ATTENDANCE_PATH):
        return []
    with open(ATTENDANCE_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    rows.reverse()
    return rows


def find_attendance_row_after(rows, session_id, start_dt):
    """Newest row for `session_id` timestamped at or after `start_dt`, or
    None. `rows` must already be newest-first."""
    for row in rows:
        if row.get("session_id") != session_id:
            continue
        try:
            row_dt = datetime.strptime(f"{row.get('date', '')} {row.get('time', '')}", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
        if row_dt >= start_dt:
            return row
    return None


def read_trials():
    """
    All evaluation trials keyed by trial_id. Empty dict if none yet, or if
    the file's header doesn't match EVALUATION_HEADERS -- e.g. a leftover
    file from a different evaluation-page schema pointed at this same path.
    Rather than crash with a confusing KeyError partway through a request,
    archive the mismatched file (mirroring attendance_logger.py's own
    _ensure_log_file() schema-migration behavior) and start fresh.
    """
    if not os.path.exists(EVALUATION_PATH):
        return {}
    with open(EVALUATION_PATH, newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != EVALUATION_HEADERS:
            mismatched = True
        else:
            return {row["trial_id"]: row for row in reader}
    if mismatched:
        legacy_path = os.path.join(os.path.dirname(EVALUATION_PATH), "evaluation_trials_legacy.csv")
        os.replace(EVALUATION_PATH, legacy_path)
        return {}


def write_trial(trial_id, **fields):
    """
    Upsert one trial row -- created "pending" on Start Trial, updated in
    place once a matching attendance row is found. Read-modify-write, same
    small-file tradeoff already accepted for dashboard/app.py's reviews.csv.
    # ponytail: read-modify-write, fine for one tester's evaluation session;
    # not built for concurrent testers.
    """
    trials = read_trials()
    row = {h: fields.get(h, "") for h in EVALUATION_HEADERS}
    row["trial_id"] = trial_id
    trials[trial_id] = row

    os.makedirs(os.path.dirname(EVALUATION_PATH), exist_ok=True)
    with open(EVALUATION_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=EVALUATION_HEADERS)
        writer.writeheader()
        for r in trials.values():
            writer.writerow(r)
    return row


def next_trial_number(trials, participant_code, scenario):
    """1-based count of trials already recorded for this exact
    (participant, scenario) pair -- gives the "R1 - Genuine Check-in -
    Trial 1" style label with no manual numbering."""
    existing = [t for t in trials if t["participant_code"] == participant_code and t["scenario"] == scenario]
    return len(existing) + 1


def cancel_trial(trial):
    """
    Mark a still-pending trial "cancelled" (the active check-in session
    changed mid-trial -- see the Evaluation Mode bug fix, requirement 8)
    rather than leaving it "pending" forever, which would otherwise keep
    matching future attendance rows against a now-stale session_id.
    Excluded from build_summary()'s metrics the same way a "pending" trial
    is (only "pass"/"fail" count), so a cancelled trial never skews a rate.
    """
    return write_trial(
        trial["trial_id"],
        participant_code=trial["participant_code"], participant_type=trial["participant_type"],
        scenario=trial["scenario"], trial_number=trial["trial_number"], session_id=trial["session_id"],
        expected_identity=trial["expected_identity"], expected_result=trial["expected_result"],
        start_timestamp=trial["start_timestamp"], end_timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        passed="cancelled", notes="Active check-in session changed during trial.",
    )


def finalize_trial(trial, attendance_row, timing=None):
    """
    Attach `attendance_row` (a raw attendance.csv row dict) to `trial` (a row
    from read_trials()): compute duration, match a snapshot, grade
    PASS/FAIL, and save. Shared by the auto-poll path and the manual
    fallback attach, so neither duplicates the other's finalization logic.

    `timing` (optional) is CheckinSession.timing_snapshot()'s dict, captured
    by the caller from the live station at the moment the matching
    attendance row was found (Evaluation Timing Phase R2) -- gives the
    engine's own monotonic-clock recognition/liveness/decision durations,
    which are far more meaningful than the wall-clock trial start/end
    timestamps alone (those still include however long the poll took to
    notice the result, not just the attempt itself). Falls back to the
    wall-clock-derived duration for `duration_seconds` when timing is
    unavailable (e.g. the station was somehow already reset), so a trial is
    never left without any duration at all.
    """
    start_dt = datetime.strptime(trial["start_timestamp"], "%Y-%m-%d %H:%M:%S")
    end_dt = datetime.now()
    wall_clock_duration = round((end_dt - start_dt).total_seconds(), 1)

    timing = timing or {}
    recognition_duration = timing.get("recognition_duration_seconds")
    liveness_duration = timing.get("liveness_duration_seconds")
    decision_duration = timing.get("decision_duration_seconds")
    # duration_seconds is kept for backward compatibility, now defined as the
    # engine's own decision_duration_seconds where available (requirement 11).
    duration_seconds = decision_duration if decision_duration is not None else wall_clock_duration

    actual_identity = attendance_row.get("name", "")
    actual_result = attendance_row.get("result", "")
    actual_reason = attendance_row.get("reason", "")
    snapshot = find_snapshot_for_row(attendance_row, list_snapshot_files())

    passed = determine_pass(trial["scenario"], trial["expected_identity"],
                             actual_identity, actual_result, actual_reason)

    return write_trial(
        trial["trial_id"],
        participant_code=trial["participant_code"],
        participant_type=trial["participant_type"],
        scenario=trial["scenario"],
        trial_number=trial["trial_number"],
        session_id=trial["session_id"],
        expected_identity=trial["expected_identity"],
        expected_result=trial["expected_result"],
        actual_identity=actual_identity,
        actual_result=actual_result,
        actual_reason=actual_reason,
        start_timestamp=trial["start_timestamp"],
        end_timestamp=end_dt.strftime("%Y-%m-%d %H:%M:%S"),
        duration_seconds=duration_seconds,
        recognition_duration_seconds=recognition_duration if recognition_duration is not None else "",
        liveness_duration_seconds=liveness_duration if liveness_duration is not None else "",
        decision_duration_seconds=decision_duration if decision_duration is not None else "",
        passed=("pass" if passed else "fail"),
        notes=trial.get("notes", ""),
        snapshot_filename=snapshot or "",
    )


def _metric(label, n, total):
    if total == 0:
        return {"label": label, "n": n, "total": total, "text": "No data yet"}
    pct = round(n / total * 100)
    return {"label": label, "n": n, "total": total, "text": f"{pct}% ({n}/{total})"}


def build_summary(trials):
    """
    The 9 report-ready metrics for this phase, each as {label, n, total,
    text} so the template only ever prints "No data yet" or "NN% (n/total)"
    -- never a bare N/A card. Only finalized trials (passed in
    {"pass","fail"}) count; a still-"pending" trial has no actual_* fields
    yet and would only pollute the denominators.
    """
    finalized = [t for t in trials if t.get("passed") in ("pass", "fail")]

    def _scenario(name):
        return [t for t in finalized if t["scenario"] == name]

    genuine = _scenario("Genuine Check-in")
    unknown = _scenario("Unknown Person")
    liveness = _scenario("Deliberate Liveness Failure")
    duplicate = _scenario("Duplicate Check-in")
    photo = _scenario("Static Photo Attack")
    registered_any = [t for t in finalized if t.get("participant_type") == "registered"]

    recognition_correct = sum(1 for t in registered_any if t["actual_identity"] == t["expected_identity"])
    genuine_pass = sum(1 for t in genuine if t["passed"] == "pass")
    genuine_rejected = sum(1 for t in genuine if t["actual_result"] != "success")
    unknown_pass = sum(1 for t in unknown if t["passed"] == "pass")
    unknown_accepted = sum(1 for t in unknown if t["actual_result"] == "success")
    liveness_pass = sum(1 for t in liveness if t["passed"] == "pass")
    duplicate_pass = sum(1 for t in duplicate if t["passed"] == "pass")
    photo_pass = sum(1 for t in photo if t["passed"] == "pass")

    return {
        "recognition_accuracy": _metric("Face Recognition Accuracy", recognition_correct, len(registered_any)),
        "genuine_acceptance_rate": _metric("Genuine Acceptance Rate", genuine_pass, len(genuine)),
        "false_rejection_rate": _metric("False Rejection Rate", genuine_rejected, len(genuine)),
        "unknown_rejection_rate": _metric("Unknown Face Rejection Rate", unknown_pass, len(unknown)),
        "unknown_false_accept_rate": _metric("Unknown False Accept Rate", unknown_accepted, len(unknown)),
        "liveness_detection_rate": _metric("Liveness Failure Detection Rate", liveness_pass, len(liveness)),
        "duplicate_detection_rate": _metric("Duplicate Detection Rate", duplicate_pass, len(duplicate)),
        "photo_attack_rejection_rate": _metric("Static Photo Attack Rejection Rate", photo_pass, len(photo)),
        # Evaluation Timing Phase R2: mean durations sourced from the engine's
        # own monotonic-clock timing (CheckinSession.timing_snapshot()), not
        # wall-clock trial start/end -- see finalize_trial()'s docstring.
        # Replaces the old avg_genuine_time (wall-clock based) metric.
        "mean_recognition_time": _mean_duration(genuine, "recognition_duration_seconds", "Mean Recognition Time (Genuine)"),
        "mean_genuine_decision_time": _mean_duration([t for t in genuine if t["passed"] == "pass"], "decision_duration_seconds", "Mean Genuine Check-in Time"),
        "mean_unknown_rejection_time": _mean_duration([t for t in unknown if t["passed"] == "pass"], "decision_duration_seconds", "Mean Unknown Rejection Time"),
        "mean_duplicate_detection_time": _mean_duration([t for t in duplicate if t["passed"] == "pass"], "decision_duration_seconds", "Mean Duplicate Detection Time"),
        "mean_liveness_failure_time": _mean_duration([t for t in liveness if t["passed"] == "pass"], "decision_duration_seconds", "Mean Liveness-Failure Decision Time"),
        "mean_photo_rejection_time": _mean_duration([t for t in photo if t["passed"] == "pass"], "decision_duration_seconds", "Mean Static Photo Rejection Time"),
    }


def _mean_duration(rows, field, label):
    """Mean of `field` (a timing_snapshot()-derived column) across `rows`,
    skipping trials where that duration was never recorded (e.g. duplicates
    caught before liveness ever started leave liveness_duration_seconds
    blank). Same {label, n, total, text} shape as _metric() so the template
    doesn't need a second card format."""
    values = [float(t[field]) for t in rows if t.get(field)]
    mean = round(sum(values) / len(values), 1) if values else None
    return {
        "label": label, "n": len(values), "total": len(values),
        "text": f"{mean} s (n={len(values)})" if mean is not None else "No data yet",
    }
