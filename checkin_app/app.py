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

import os
import sys
import time
import threading

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

import cv2

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
        return jsonify({"active": False, "phase": None, "can_reset": False, "message": None})
    return jsonify({
        "active": True,
        "phase": session.flow_phase,
        "can_reset": session.can_reset(),
        "message": session.banner,
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


if __name__ == "__main__":
    # threaded=True so the long-lived MJPEG stream doesn't block /status,
    # /reset, and page loads. No debug reloader: it would spawn a second
    # process that fights over the webcam. Port 5002 to avoid clashing with
    # the lecturer dashboard (5001) and macOS AirPlay Receiver (5000).
    app.run(port=5002, threaded=True)
