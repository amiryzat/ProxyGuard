# Architecture

This document explains the high-level system architecture of ProxyGuard.

## System Overview
ProxyGuard uses a local webcam-based pipeline to perform face recognition, liveness detection (blink + head movement), attendance logging, and suspicious pattern flagging.

A voice challenge was previously part of the live pipeline but has been removed from the flow to prioritize reliability at the current proposal stage. Its module (`src/voice_challenge.py`) is retained intact and could be reintegrated later; see [[decisions]].

The system is designed as separate Python modules inside `src/`, with each module kept independent and testable. The modules are combined through `src/main.py`, which controls the live check-in flow.

A separate Flask web app in `dashboard/` provides a lecturer-facing view over the attendance log. It is read-only and reuses the existing flagging logic rather than duplicating it (see the Lecturer Dashboard section below).

## System Flow

1. Webcam captures a live video frame.
2. Face detection locates the face in the frame.
3. Face recognition compares the detected face against registered student reference images.
4. Blink detection runs continuously using MediaPipe Face Mesh.
5. A randomized head movement challenge, requiring a real blink during the same window, verifies active physical response.
6. On passing, a recognized face is confirmed directly; an unrecognized one ends as "not recognized".
7. Attendance is logged with result and reason, and a verification snapshot of the frame is saved.
8. Suspicious attendance patterns are flagged for lecturer review.

(The voice challenge and the mid-challenge identity re-verification that previously sat between steps 5 and 7 have been removed from the live flow — see the note under System Overview.)

## Main Modules

- `src/face_detector.py`  
  Handles basic face detection using OpenCV Haar Cascade.

- `src/face_recognizer.py`  
  Loads known face images, generates face encodings, performs identity matching, and provides cheaper face location tracking. Matching uses a distance tolerance of 0.45 and requires a minimum margin of 0.1 between the best and second-best match; both were tightened (from 0.5 and 0.05) to reduce false accepts between visually similar students.

- `src/liveness_check.py`  
  Handles blink detection and randomized head movement challenge using MediaPipe Face Mesh.

- `src/voice_challenge.py`  
  Generates a random 3-digit challenge number, records microphone input, transcribes speech, and compares spoken digits. **Currently not part of the live check-in flow** — it has been removed from `main.py` but the module is retained intact so it can be reintegrated later.

- `src/class_config.py`  
  Standalone, dependency-free module (only `datetime`) added for the Phase 1 session-restructuring feature. Holds the predefined, easily-editable `CLASS_SUBJECTS` list, the allowed week range (`WEEK_MIN`/`WEEK_MAX`, 1–14), `subject_code()`, and `build_session_id()` — the single source of truth for the `session_id` format (see System Flow and the Session Identity section below). Kept dependency-free so both `main.py`'s terminal setup and `checkin_app/`'s web setup page can import it without pulling in `cv2`/`mediapipe`.

- `src/attendance_logger.py`  
  Logs attendance outcomes to CSV and prevents duplicate successful check-ins within the same session.

- `src/pattern_flagger.py`  
  Reads attendance logs and flags repeated failures, duplicate attempts, and clustered unrecognized attempts.

- `src/main.py`  
  Combines face recognition, liveness detection (blink + head movement), attendance logging, and per-outcome verification snapshots into one live webcam check-in flow. Before the camera loop starts, it prompts the lecturer in the terminal (via `class_config.py`) to select a class subject and week number, then builds `session_id` from them.

## Session Identity (`session_id`)

`session_id` is generated once per run/session and is treated as an opaque string by every module that consumes it (`attendance_logger.py`, `pattern_flagger.py`, the snapshot filenames, and the dashboard) — none of them parse its internal structure.

As of Phase 1, it is built by `class_config.build_session_id(subject, week_number)` from the current timestamp plus the selected class subject's short code and week number, rather than a bare timestamp:

```
YYYY-MM-DD_HHMM_<CODE>_Week<N>
e.g. 2026-07-07_0900_CSC649_Week3
```

This was changed because a single room/date can host multiple *different* class subjects, so a timestamp alone didn't tell a lecturer which class a set of check-ins belonged to; grouping by subject + teaching week is more useful for review than a raw timestamp. See [[decisions]] Decision 8. `<CODE>` (not the full subject name) is used to keep the id space-free and filesystem-safe, since it is also embedded directly into verification snapshot filenames (see Verification Snapshots below).

Two entry points can currently build a `session_id`:
- `src/main.py`'s terminal prompt (`prompt_session_setup()`), used by the live webcam check-in flow.
- `checkin_app/`'s web setup page (Phase 2a — see below), which calls the same `class_config.build_session_id()` so both paths produce identically-formatted ids.

## Lecturer Dashboard (`dashboard/`)

A small, standalone Flask web app that lets a lecturer review the attendance log in the browser. It is kept in its own top-level `dashboard/` folder (not inside `src/`) so it stays separate from the core detection modules, matching the project's module-independence convention.

### Folder structure
```
dashboard/
├── app.py                # Flask app: reads the log, filters by session, flags rows, builds the summary
└── templates/
    └── index.html        # Single page: session dropdown, summary stat boxes, attendance table
```

### Features
- **Attendance table** — shows the same columns as the CSV (`name`, `date`, `time`, `session_id`, `result`, `reason`), most recent entries first.
- **Session filter** — a dropdown of all unique `session_id` values (most recent first). On first load it defaults to the most recent session rather than the whole log history; selecting another session reloads the table via a `?session=...` query parameter.
- **Flagged row highlighting** — rows belonging to a suspicious pattern are highlighted in red.
- **Per-session summary** — a small row of stat boxes above the table showing total attempts, successful confirmations, failed attempts, and flagged entries for the selected session only.

### Reuse of `pattern_flagger.py` (no duplicated logic)
`app.py` adds `src/` to `sys.path` and imports `pattern_flagger` directly. It calls `pattern_flagger.flag_patterns()` and reads that report (plus `pattern_flagger`'s own reason constants) to decide which visible rows are flagged — the detection logic itself is never copied or reimplemented in the dashboard. The flagged count in the summary reuses the very same per-row result, so it is not recalculated separately. Because `pattern_flagger` only depends on the standard library, importing it into the dashboard stays cheap and does not pull in OpenCV or MediaPipe.

### Data flow
The dashboard reads `logs/attendance.csv` (written by `attendance_logger.py`) **read-only** — it never writes to or modifies the log. It resolves the log path relative to its own location, mirroring `attendance_logger.py`, so it finds the same file regardless of the working directory.

### How to run
```
python dashboard/app.py
```
Then open `http://127.0.0.1:5001/` in a browser. Port 5001 is used instead of Flask's default 5000 because macOS AirPlay Receiver occupies port 5000 and returns a 403 for other requests. Flask must be installed in the environment (`pip install flask`).

## Student Check-in Web App (`checkin_app/`) — setup + live check-in

A separate, standalone Flask app for the student-facing check-in flow, kept in its own top-level `checkin_app/` folder (not inside `src/` or `dashboard/`), matching the project's module-independence convention. **Phase 2a** is the session setup step (pick a class and week → generate `session_id`); **Phase 2b** adds the live check-in page that streams the webcam into the browser and runs the full recognition + liveness + logging + snapshot flow. See [[decisions]] Decision 9.

### Folder structure
```
checkin_app/
├── app.py                 # Flask app: setup -> session_id -> live MJPEG check-in
└── templates/
    ├── setup.html          # Class-subject dropdown, week dropdown (1-14), "Start Session" button
    ├── confirm.html        # (Phase 2a leftover; /start now goes straight to the live page)
    └── checkin.html        # Live page: session header, MJPEG <img> stream, status text, "New check-in"
```

### Features
- **Setup page (`GET /`)** — dropdowns populated from `class_config.CLASS_SUBJECTS` and `WEEK_MIN`..`WEEK_MAX`, so the choices always match Phase 1's predefined list without duplicating it.
- **Session start (`POST /start`)** — validates the submitted subject and week against the known Phase 1 values (never trusting raw form input); an invalid/tampered submission re-renders the setup form with an error. A valid submission calls `class_config.build_session_id()`, starts the live check-in station for that id, and redirects to the check-in page.
- **Live check-in (`GET /checkin`, `/video_feed`, `/status`, `POST /reset`)** — the check-in page shows the class/week/`session_id`, an `<img>` pointed at the `/video_feed` MJPEG stream, a status line, and a "New check-in" button. `/status` (polled) drives the status text and enables the button only at a terminal outcome; `/reset` is the web analog of the desktop `n` key.

### Reuse of the shared check-in engine (no duplicated logic)
`app.py` adds `src/` to `sys.path` (the same pattern `dashboard/app.py` uses) and imports `class_config` (subject list, `build_session_id`), `face_recognizer.load_known_faces`, and — for Phase 2b — `main.CheckinSession`. The web app does **not** reimplement any recognition, liveness, state-machine, logging, or snapshot logic: it drives the same `CheckinSession.process_frame` the desktop app uses, so both stay in lockstep and fixes apply once. The only web-specific code is how frames are *delivered* (webcam → MJPEG) and *displayed* (`<img>` instead of an OpenCV window).

### Frame handling / streaming (performance)
Frames are captured and processed **server-side**; the browser only displays them. The MJPEG generator reads the webcam, calls `session.process_frame(...)`, JPEG-encodes the annotated frame, and yields it as a `multipart/x-mixed-replace` part. Processing resolution and display resolution are **decoupled** inside the shared `process_frame`: it downscales internally for the heavy steps (recognition every 3rd frame on a 0.25x copy, mediapipe on a 0.5x copy) and draws the resulting boxes/labels back onto the full-size frame, which is what gets streamed. So the capture size only meaningfully drives the per-frame JPEG **encode** cost, not the recognition/mediapipe cost — the web app can capture at a clear size without paying for it in processing. The streaming path is tuned for a fanless CPU-only machine (see [[bugs]] Bug 6 and Bug 7):
- **Capture (and stream) at 1280×720** (`CAP_PROP_FRAME_WIDTH/HEIGHT`) — clear and demo-friendly; the internal 0.25x recognition copy is then 320×180, the same input size the desktop flow has always used.
- **JPEG quality 80** for the stream (vs. OpenCV's default 95) — presentable for a demo, still cheaper than default.
- **~20 FPS cap** on the generator loop so it can't peg the CPU (which throttles a fanless Air).
- **Single active stream**: a `_stream_generation` counter ensures only the newest `/video_feed` generator drives the camera; older ones (from reloads/reconnects) exit, preventing thread/handle accumulation across long sessions. All frame access is serialized under `_station_lock`.

These knobs are `checkin_app`-only (named constants at the top of `app.py`); the desktop flow keeps native capture and its native `cv2.imshow` window. (Bug 6's first cut lowered capture to 640×480 and quality to 60, which over-blurred the preview; Bug 7 restored display quality while keeping processing performance separate.)

### Data / resource model
One physical webcam ⇒ one active check-in station: `_start_station` lazily opens the camera once and reuses it, and `/reset` reuses the same `CheckinSession` (and its one mediapipe `FaceMesh`) rather than recreating them per attempt. Attendance rows and verification snapshots are written by the shared engine to the same `logs/attendance.csv` and `logs/snapshots/` the desktop app uses, in the identical format.

### How to run
```
python checkin_app/app.py
```
Then open `http://127.0.0.1:5002/` in a browser. Port 5002 is used to avoid clashing with the lecturer dashboard (5001) and macOS AirPlay Receiver (5000). Runs with `threaded=True` (so the long-lived stream doesn't block other routes) and no debug reloader (it would spawn a second process fighting over the webcam) — so restart the process to pick up code changes.

## Verification Snapshots

At every terminal check-in outcome (`confirmed`, `not_recognized`, `liveness_failed`; `identity_mismatch` is retained as a terminal state but is currently unreachable now that the voice listening phase is gone), `src/main.py` saves a snapshot of the webcam frame to `logs/snapshots/` (created automatically if missing), at the same moment attendance is logged for that outcome.

- **Every outcome is captured, successes included** — not just failures. Because a check-in can pass the liveness checks and still be a photo of someone else held up to the camera, the saved image gives a lecturer a way to manually verify the actual face after the fact.
- **A pre-overlay frame is saved.** `main.py` keeps an un-annotated copy of each frame taken before any bounding boxes or status text are drawn, so the face in the snapshot is unobstructed.
- **File naming** combines the `session_id`, the identity (`confirmed_name` if recognized, otherwise `unknown`), the outcome reason, and an `HHMMSS` timestamp, e.g. `2026-07-07_0900_CSC649_Week3_unknown_liveness_timeout_171322.jpg` (the `session_id` portion now includes the class code and week per the Phase 1 format above). The timestamp keeps multiple check-ins within one session from overwriting each other.

Snapshots are a manual review aid only; the system never uses them to auto-accept or auto-reject a check-in.

## Design Principles

- Keep modules independent and importable.
- Keep functions small and testable.
- Avoid storing raw voice data.
- Avoid storing side-face images.
- Persisted data: frontal reference images, face encodings, attendance logs, and per-outcome verification snapshots (see Verification Snapshots). Still no raw voice data and no side-face images.
- Prefer clarity over premature optimization because this is an academic prototype.

## Related Documentation

- [[project-overview]]
- [[roadmap]]
- [[decisions]]
- [[testing]]
- [[bugs]]
- [[CLAUDE]]