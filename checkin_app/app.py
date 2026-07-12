# checkin_app/app.py
# Student-facing check-in web interface.
#
# Phase 2a: a setup page (pick class subject + week) that builds a session_id.
# Phase 2b: after setup, a LIVE check-in page that streams the webcam (captured
#   and processed server-side) into the browser as MJPEG and runs the exact
#   same face-recognition + liveness + logging + snapshot flow as the desktop
#   app (src/main.py). The browser only displays frames via an <img> pointed at
#   a streaming route; no browser-side camera API is used.
#
# All detection/liveness/logging/snapshot behavior is REUSED from
# src/main.CheckinSession -- this app only changes how frames are delivered
# (webcam -> MJPEG) and displayed (OpenCV window -> browser).

import csv
import io
import os
import sys
import time
import threading
from datetime import datetime

from flask import (
    Flask, render_template, request, redirect, url_for, Response, jsonify
)

# Reuse the Phase 1 class list/id-builder and the shared check-in engine from
# src/. class_config is stdlib-only; importing main pulls in cv2/mediapipe,
# which Phase 2b legitimately needs since the camera is processed server-side.
SRC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from class_config import CLASS_SUBJECTS, WEEK_MIN, WEEK_MAX, build_session_id
from face_recognizer import load_known_faces
from main import CheckinSession
from attendance_logger import has_success_this_session

import cv2

import evaluation

app = Flask(__name__)

# Weeks offered in the dropdown, from the same bounds Phase 1 uses for the
# terminal prompt, so the two setup paths stay in step.
WEEK_CHOICES = list(range(WEEK_MIN, WEEK_MAX + 1))

# ---- Web preview performance knobs (see docs/bugs.md Bug 6 & Bug 7) ---------
# Processing resolution and DISPLAY resolution are decoupled. The shared
# CheckinSession.process_frame already downscales *internally* for the heavy
# steps (recognition every 3rd frame on a 0.25x copy, mediapipe on a 0.5x copy)
# and draws the resulting boxes/labels back onto the full-size frame. So the
# capture size only really drives the per-frame JPEG encode cost -- not the
# recognition/mediapipe cost -- which means we can capture at a clear,
# demo-friendly resolution without paying for it in processing.
#
# History: Bug 6's first lag fix dropped capture to 640x480, which also blurred
# the visible stream (over-correction). Bug 7 restores a clear capture/display
# size; at 1280x720 the internal 0.25x recognition copy is 320x180 -- the same
# input size the desktop flow (src/main.py) has always used successfully. The
# crash fixes (FPS cap + single-stream guard, below) are unchanged.
CAPTURE_WIDTH = 1280      # clear display/stream size, ~desktop native; 0.25x -> 320x180 for recognition
CAPTURE_HEIGHT = 720
STREAM_JPEG_QUALITY = 80  # moderate-high: presentable for a demo (default is 95)
STREAM_TARGET_FPS = 20    # cap the loop so it can't peg a fanless Air's CPU

# ---- Single check-in station -----------------------------------------------
# There is one physical webcam, so the app runs one active station at a time
# (one student at the kiosk). _station_lock serializes camera reads + frame
# processing against session (re)creation and reset, so they can't collide
# while a frame is mid-process.
_station_lock = threading.Lock()
_station = {
    "session": None,      # main.CheckinSession
    "session_id": None,
    "subject": None,
    "week": None,
    "cap": None,          # cv2.VideoCapture
}

# Encodings are expensive to load; load once and reuse for every session
# started during this server run.
_known_faces = {"encodings": None, "names": None}


def _ensure_known_faces():
    if _known_faces["encodings"] is None:
        encodings, names = load_known_faces()
        _known_faces["encodings"] = encodings
        _known_faces["names"] = names
    return _known_faces["encodings"], _known_faces["names"]


def _start_station(session_id, subject, week_number):
    """(Re)initialize the single check-in station for a new session."""
    encodings, names = _ensure_known_faces()
    with _station_lock:
        if _station["cap"] is None:                 # open webcam lazily, reuse it
            cap = cv2.VideoCapture(0)
            # Capture at a clear display resolution (the camera picks the
            # nearest supported mode). Recognition/mediapipe don't pay for this
            # -- process_frame downscales internally -- only the per-frame MJPEG
            # encode scales with it, which the moderate JPEG quality offsets.
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, CAPTURE_WIDTH)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, CAPTURE_HEIGHT)
            _station["cap"] = cap
        if _station["session"] is not None:         # release previous FaceMesh
            _station["session"].close()
        # restart_hint=None: the web page uses the "New check-in" button (and
        # /reset), not a keyboard key, so no on-frame "Press 'n'..." hint.
        _station["session"] = CheckinSession(session_id, encodings, names, restart_hint=None)
        _station["session_id"] = session_id
        _station["subject"] = subject
        _station["week"] = week_number


# Incremented each time a new MJPEG stream starts. Only the newest generator
# keeps processing the camera; older ones (from a page reload, a second tab, or
# a browser reconnecting the <img>) exit their loop instead of piling up extra
# camera-read + mediapipe threads that contend for the one webcam and the one
# shared session. Without this, threads/handles accumulated over extended use.
_stream_generation = 0


def _generate_frames():
    """MJPEG generator: read webcam -> process server-side -> stream JPEG."""
    global _stream_generation
    with _station_lock:
        _stream_generation += 1
        my_generation = _stream_generation

    min_interval = 1.0 / STREAM_TARGET_FPS
    encode_params = [int(cv2.IMWRITE_JPEG_QUALITY), STREAM_JPEG_QUALITY]

    # Stop as soon as a newer stream supersedes this one, so only one generator
    # ever drives the camera + shared session at a time.
    while my_generation == _stream_generation:
        loop_start = time.time()

        with _station_lock:
            session = _station["session"]
            cap = _station["cap"]
            if session is None or cap is None:
                frame = None
            else:
                ret, raw = cap.read()
                frame = session.process_frame(raw) if ret else None
        if frame is None:
            time.sleep(0.05)   # no active session/camera yet; keep stream open
            continue
        ok, buffer = cv2.imencode(".jpg", frame, encode_params)
        if not ok:
            continue
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n")

        # Throttle to STREAM_TARGET_FPS. The sleep is outside the lock, so it
        # never blocks /status, /reset, or /start, and keeps the capture/encode
        # loop from spinning the CPU flat out between recognition frames.
        elapsed = time.time() - loop_start
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)


@app.route("/")
def setup():
    """Render the setup form: class-subject dropdown + week dropdown."""
    return render_template("setup.html", subjects=CLASS_SUBJECTS, weeks=WEEK_CHOICES)


@app.route("/start", methods=["POST"])
def start_session():
    """
    Handle the setup form submission. Validates the submitted subject and week
    against the known Phase 1 values (never trusting the raw form input), then
    builds the session_id with the shared build_session_id() so the format
    matches main.py exactly, starts the live check-in station for it, and
    redirects to the live check-in page.
    """
    subject = request.form.get("subject", "")
    week_raw = request.form.get("week", "")

    # Re-render the form (no session started) if either field is missing or
    # outside the allowed Phase 1 set, rather than generating a malformed id.
    if subject not in CLASS_SUBJECTS or not week_raw.isdigit() or int(week_raw) not in WEEK_CHOICES:
        return render_template(
            "setup.html",
            subjects=CLASS_SUBJECTS,
            weeks=WEEK_CHOICES,
            error="Please choose a valid class subject and week number.",
        )

    week_number = int(week_raw)
    session_id = build_session_id(subject, week_number)
    _start_station(session_id, subject, week_number)
    return redirect(url_for("checkin"))


@app.route("/checkin")
def checkin():
    """Render the live check-in page for the currently active session."""
    with _station_lock:
        session_id = _station["session_id"]
        subject = _station["subject"]
        week = _station["week"]
    if session_id is None:
        # No session set up yet -> back to the setup form.
        return redirect(url_for("setup"))
    return render_template(
        "checkin.html",
        session_id=session_id,
        subject=subject,
        week_number=week,
    )


@app.route("/video_feed")
def video_feed():
    """MJPEG stream of the server-side-processed webcam frames."""
    return Response(_generate_frames(),
                    mimetype="multipart/x-mixed-replace; boundary=frame")


@app.route("/status")
def status():
    """
    Current flow state, for the page to echo the check-in message as text and
    enable the "New check-in" button only at a terminal outcome. Read lock-free
    on purpose (a slightly stale phase is fine) so polling never stutters
    behind an in-progress frame in the generator.
    """
    session = _station["session"]
    if session is None:
        return jsonify({
            "active": False, "phase": None, "can_reset": False, "message": None,
            # Evaluation Timing Phase R2 (requirement 10): additive fields
            # only -- existing consumers reading active/phase/can_reset/
            # message are unaffected.
            "timing_phase": "waiting", "attempt_elapsed_seconds": None,
            "recognition_duration_seconds": None, "liveness_duration_seconds": None,
            "decision_duration_seconds": None,
        })
    return jsonify({
        "active": True,
        "phase": session.flow_phase,
        "can_reset": session.can_reset(),
        "message": session.banner,
        **session.timing_snapshot(),
    })


@app.route("/reset", methods=["POST"])
def reset():
    """Start a fresh check-in for the next student (web analog of desktop 'n')."""
    with _station_lock:
        session = _station["session"]
        if session is not None and session.can_reset():
            session.reset()
    return ("", 204)


def _end_station():
    """
    Fully tear down the single check-in station: release the webcam, close
    the shared session's FaceMesh, and bump _stream_generation so any
    in-flight /video_feed generator's while loop sees a mismatch and exits
    on its next iteration instead of continuing to hold the camera. Guards
    every step on "is not None" so calling this repeatedly (e.g. a
    double-click, or End Session hit with no active session) is a no-op
    past the first call rather than raising.
    """
    global _stream_generation
    with _station_lock:
        _stream_generation += 1
        if _station["session"] is not None:
            _station["session"].close()
            _station["session"] = None
        if _station["cap"] is not None:
            _station["cap"].release()
            _station["cap"] = None
        _station["session_id"] = None
        _station["subject"] = None
        _station["week"] = None


@app.route("/end_session", methods=["POST"])
def end_session():
    """
    "End session / set up a different class": release the camera and clear
    the station so the MacBook camera light actually turns off, instead of
    just navigating back to the setup page while capture keeps running.
    """
    _end_station()
    return ("", 204)


# ---- Report Support Phase R1: simplified automated evaluation mode ---------
# Runs entirely by observing the same logs/attendance.csv the normal check-in
# flow already writes -- no second recognition path, no changes to
# CheckinSession. The tester picks a participant code + scenario and clicks
# Start Trial; everything else (trial numbering, timer, result capture,
# PASS/FAIL grading, CSV logging) is automatic. See checkin_app/evaluation.py
# for the data layer this just wires up as routes.

@app.route("/evaluation")
def evaluation_page():
    """
    Render the evaluation page. The active session is whatever the one
    physical check-in station is currently running (read lock-free, same
    convention as /status below) -- there is only ever one session a tester
    can actually perform check-ins against, so this is shown as the trial's
    session rather than offered as a free-choice dropdown.
    """
    active_session_id = _station["session_id"]
    trials = list(evaluation.read_trials().values())
    trials.sort(key=lambda t: t.get("start_timestamp", ""), reverse=True)
    summary = evaluation.build_summary(trials)

    return render_template(
        "evaluation.html",
        active_session_id=active_session_id,
        active_subject=_station["subject"],
        active_week=_station["week"],
        participants=evaluation.PARTICIPANTS,
        scenarios=evaluation.SCENARIOS,
        trials=trials,
        summary=summary,
    )


@app.route("/evaluation_panel")
def evaluation_panel():
    """Re-renders just the results table + summary, so the page can refresh
    in place after a trial is finalized -- mirrors dashboard/app.py's
    /assistant_panel pattern for the same reason (AJAX-refreshable fragment,
    no duplicated markup between the full page and the refresh)."""
    trials = list(evaluation.read_trials().values())
    trials.sort(key=lambda t: t.get("start_timestamp", ""), reverse=True)
    summary = evaluation.build_summary(trials)
    return render_template("_evaluation_panel.html", trials=trials, summary=summary)


@app.route("/evaluation/current-session")
def evaluation_current_session():
    """
    Lightweight polling endpoint (Evaluation Mode bug fix, requirement 2/3):
    lets the evaluation page detect an active-session change (or a session
    starting/ending) without a full page reload. Read lock-free, same
    convention as /status above -- a slightly stale read is fine for a
    few-second poll.
    """
    return jsonify({
        "active": _station["session_id"] is not None,
        "session_id": _station["session_id"],
        "subject": _station["subject"],
        "week": _station["week"],
    })


@app.route("/evaluation/cancel", methods=["POST"])
def evaluation_cancel():
    """
    Cancel a still-pending trial safely (requirement 8) -- used when the
    active check-in session changes while a trial is running, so it never
    silently attaches an attendance row from the wrong session. Marks the
    trial "cancelled" rather than leaving it "pending" forever, which would
    otherwise keep matching every future /evaluation/check poll against a
    now-stale session_id.
    """
    data = request.get_json(silent=True) or request.form
    trial_id = data.get("trial_id") or ""
    trial = evaluation.read_trials().get(trial_id)
    if trial is None:
        return jsonify({"error": "unknown trial_id"}), 404
    if trial.get("passed") != "pending":
        return jsonify({"trial": trial})  # already finalized -- nothing to cancel
    return jsonify({"trial": evaluation.cancel_trial(trial)})


@app.route("/evaluation/start", methods=["POST"])
def evaluation_start():
    """
    Start Trial: participant_code + scenario only -- trial number,
    session_id (from the active station), expected identity/result, and the
    start timestamp are all derived automatically, never supplied by the
    client. Writes a "pending" row immediately so it survives a page reload
    mid-trial and shows up in the results table right away.
    """
    data = request.get_json(silent=True) or request.form
    participant_code = data.get("participant_code") or ""
    scenario = data.get("scenario") or ""

    session_id = _station["session_id"]
    if not session_id:
        return jsonify({"error": "No active check-in session -- start one from the setup page first."}), 400
    if participant_code not in evaluation.PARTICIPANTS:
        return jsonify({"error": "Unknown participant code."}), 400
    if scenario not in evaluation.SCENARIOS:
        return jsonify({"error": "Unknown scenario."}), 400

    participant = evaluation.PARTICIPANTS[participant_code]
    expected_identity = participant["identity"]
    expected_result = evaluation.expected_result_for(scenario)

    if scenario == "Duplicate Check-in":
        if participant["type"] != "registered":
            return jsonify({"error": "Duplicate Check-in requires a registered participant (R1-R3)."}), 400
        if not has_success_this_session(expected_identity, session_id):
            return jsonify({
                "error": f"{participant_code} does not have a successful check-in in this session yet -- "
                         "run a Genuine Check-in trial for them first, then retry Duplicate Check-in."
            }), 400

    trials = list(evaluation.read_trials().values())
    trial_number = evaluation.next_trial_number(trials, participant_code, scenario)
    trial_id = f"{participant_code}-{scenario.replace(' ', '_')}-{trial_number}"
    start_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    trial = evaluation.write_trial(
        trial_id,
        participant_code=participant_code, participant_type=participant["type"],
        scenario=scenario, trial_number=trial_number, session_id=session_id,
        expected_identity=expected_identity, expected_result=expected_result,
        start_timestamp=start_timestamp, passed="pending",
    )
    return jsonify({"trial": trial, "label": f"{participant_code} - {scenario} - Trial {trial_number}"})


@app.route("/evaluation/check")
def evaluation_check():
    """
    Polled every few seconds while a trial is pending: looks for the newest
    attendance row in the trial's own session logged at or after the
    trial's start time, and finalizes the trial the instant one appears.
    """
    trials = evaluation.read_trials()
    pending = [t for t in trials.values() if t.get("passed") == "pending"]
    if not pending:
        return jsonify({"active": False})

    active = max(pending, key=lambda t: t.get("start_timestamp", ""))
    start_dt = datetime.strptime(active["start_timestamp"], "%Y-%m-%d %H:%M:%S")
    match = evaluation.find_attendance_row_after(evaluation.read_attendance_rows(), active["session_id"], start_dt)
    if match is None:
        # Include the full pending trial (not just its id) so a page reload
        # mid-trial can resume the client-side timer/session lock correctly.
        return jsonify({"active": True, "trial_id": active["trial_id"], "matched": False, "trial": active})

    # Evaluation Timing Phase R2: the live CheckinSession still holds the
    # monotonic-clock timing for the attempt that JUST produced this
    # attendance row (reset() -- "New check-in" -- hasn't run yet, since
    # that only happens after this trial is finalized), so pull the real
    # recognition/liveness/decision durations from it rather than only the
    # wall-clock start/end timestamps evaluation.py would otherwise fall
    # back to. Best-effort: if the station was somehow already reset before
    # this poll landed, timing is simply omitted (falls back to wall-clock).
    live_session = _station["session"]
    timing = live_session.timing_snapshot() if live_session is not None else None
    trial = evaluation.finalize_trial(active, match, timing=timing)
    return jsonify({"active": True, "trial_id": active["trial_id"], "matched": True, "trial": trial})


@app.route("/evaluation/attach", methods=["POST"])
def evaluation_attach():
    """Small fallback, only for when automatic detection above hasn't
    matched yet: attach the latest attendance row from the trial's own
    session regardless of timing."""
    data = request.get_json(silent=True) or request.form
    trial_id = data.get("trial_id") or ""
    trial = evaluation.read_trials().get(trial_id)
    if trial is None:
        return jsonify({"error": "unknown trial_id"}), 404

    latest = next((r for r in evaluation.read_attendance_rows() if r.get("session_id") == trial["session_id"]), None)
    if latest is None:
        return jsonify({"error": "no attendance rows found for this trial's session yet"}), 404

    live_session = _station["session"]
    timing = live_session.timing_snapshot() if live_session is not None else None
    return jsonify({"trial": evaluation.finalize_trial(trial, latest, timing=timing)})


@app.route("/evaluation/export.csv")
def evaluation_export_csv():
    trials = list(evaluation.read_trials().values())
    trials.sort(key=lambda t: t.get("start_timestamp", ""))
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(evaluation.EVALUATION_HEADERS)
    for t in trials:
        writer.writerow([t.get(h, "") for h in evaluation.EVALUATION_HEADERS])
    return Response(
        buffer.getvalue(), mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="proxyguard_evaluation_trials_{datetime.now().strftime("%Y-%m-%d")}.csv"'},
    )


if __name__ == "__main__":
    # threaded=True so the long-lived MJPEG stream doesn't block /status,
    # /reset, and page loads. No debug reloader: it would spawn a second
    # process that fights over the webcam. Port 5002 to avoid clashing with
    # the lecturer dashboard (5001) and macOS AirPlay Receiver (5000).
    app.run(port=5002, threaded=True)
