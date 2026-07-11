# Architecture

This document explains the high-level system architecture of ProxyGuard.

## System Overview
ProxyGuard uses a local webcam-based pipeline to perform face recognition, liveness detection (blink + head movement), session-scoped duplicate detection, attendance logging, and suspicious pattern flagging, surfaced to a lecturer through a separate review dashboard.

A voice challenge was previously part of the live pipeline but has been removed from the flow to prioritize reliability at the current proposal stage. Its module (`src/voice_challenge.py`) is retained intact and could be reintegrated later; see [[decisions]].

The system is designed as separate Python modules inside `src/`, with each module kept independent and testable. The modules are combined through `src/main.py`, which defines the shared check-in engine (`CheckinSession`) driving the live check-in flow.

Two standalone Flask apps sit on top of `src/`: `checkin_app/` (student-facing check-in kiosk) and `dashboard/` (lecturer-facing, read-only review UI). Both reuse `src/` modules directly rather than duplicating logic.

## Check-in Pipeline

```
Session Picker (checkin_app setup page)
        ↓
Check-in UI (live MJPEG page + skeleton loading)
        ↓
Face Detection (src/face_recognizer.py / face_detector.py)
        ↓
Identity Verification (face_recognizer -> recognize_face)
        ↓
Active Face Continuity (anti-proxy-swap guard, Decision 11)
        ↓
Duplicate Check (has_success_this_session, Decision 12)
        ↓
Liveness Challenge (blink + head movement)
        ↓
Attendance Decision (confirmed / not_recognized / liveness_failed / duplicate_checkin)
        ↓
Attendance Logger (logs/attendance.csv + logs/snapshots/)
        ↓
Dashboard (dashboard/app.py — read-only review UI)
        ↓
Lecturer Review (Accept / Suspicious + note, logs/reviews.csv)
        ↓
ProxyGuard Assistant (rule-based recommendations over the same data)
```

1. **Session Picker** — the lecturer selects a class subject and week on `checkin_app/`'s setup page; `session_id` is built from that selection (see Session Identity below). Submitting immediately shows a full-page skeleton loading state while the session/camera are prepared (see Student Check-in Web App below).
2. **Check-in UI** — the live check-in page streams the webcam (captured and processed server-side) into the browser as MJPEG; the real feed is only revealed once a genuine first frame has arrived.
3. **Face Detection** — each processed frame is scanned for face locations.
4. **Identity Verification** — detected faces are compared against registered students' encodings (`face_recognizer.recognize_face`). **Exactly one face is required** for the challenge to run — with more than one face detected, the challenge pauses with an on-screen warning instead of progressing (see [[decisions]] Decision 10).
5. **Active Face Continuity** — once a face is recognized, an identity-liveness continuity guard requires later recognition checks to keep matching that same face (name + position) for the rest of the attempt, or the identity is cleared and the challenge restarts. This is the project's **bounding-box transfer protection**: it prevents a recognized identity from silently transferring to a swapped-in face, another student's photo, or a phone screen (see [[decisions]] Decision 11).
6. **Duplicate Check** — as soon as the recognized identity is stable (continuity intact, a real registered name), `CheckinSession._check_duplicate_checkin()` checks whether that student already has a successful check-in for the current `session_id` via the existing `attendance_logger.has_success_this_session()` helper. If so, the attempt is locked directly into a dedicated `duplicate_checkin` terminal state — the liveness challenge is never run to completion for a student already present (see [[decisions]] Decision 12).
7. **Liveness Challenge** — for a non-duplicate attempt, blink detection runs continuously and a randomized head-movement challenge (with a required blink in the same window) verifies active physical response.
8. **Attendance Decision** — on passing, a recognized face is confirmed (`confirmed`, only if continuity held); an unrecognized one ends as `not_recognized`; a timed-out challenge ends as `liveness_failed`; a stable identity already checked in ends as `duplicate_checkin` (reached without ever entering `liveness_success`).
9. **Attendance Logger** — every terminal outcome is logged with a `result`/`reason` pair (a recognized student who fails liveness is still logged under their real name, not `"Unknown"` — see [[bugs]]), and a verification snapshot of the frame is saved to `logs/snapshots/`.
10. **Dashboard** — a separate, read-only Flask app reads the same `logs/attendance.csv` and `logs/snapshots/` and presents them with filtering, analytics, and inline snapshots.
11. **Lecturer Review** — the lecturer marks each Attempts row Accepted or Suspicious (with an optional note), stored independently in `logs/reviews.csv` so the raw attendance log is never modified.
12. **ProxyGuard Assistant** — a rule-based recommendation panel reads the same session analytics and review data to surface prioritized, actionable guidance (never an automatic verdict).

(The voice challenge and the mid-challenge identity re-verification that previously sat in this flow have been removed from the live flow — see the note under System Overview.)

## Main Modules (`src/`)

- `src/face_detector.py`
  Handles basic face detection using OpenCV Haar Cascade.

- `src/face_recognizer.py`
  Loads known face images, generates face encodings, performs identity matching, and provides cheaper face location tracking. Matching uses a distance tolerance of 0.45 and requires a minimum margin of 0.1 between the best and second-best match; both were tightened (from 0.5 and 0.05) to reduce false accepts between visually similar students.

- `src/liveness_check.py`
  Handles blink detection and randomized head movement challenge using MediaPipe Face Mesh.

- `src/voice_challenge.py`
  Generates a random 3-digit challenge number, records microphone input, transcribes speech, and compares spoken digits. **Currently not part of the live check-in flow** — it has been removed from `main.py` but the module is retained intact so it can be reintegrated later.

- `src/class_config.py`
  Standalone, dependency-free module (only `datetime`) holding the predefined, easily-editable `CLASS_SUBJECTS` list, the allowed week range (`WEEK_MIN`/`WEEK_MAX`, 1–14), `subject_code()`, and `build_session_id()` — the single source of truth for the `session_id` format (see Session Identity below). Kept dependency-free so both `main.py`'s terminal setup and `checkin_app/`'s session picker can import it without pulling in `cv2`/`mediapipe`.

- `src/attendance_logger.py`
  Logs attendance outcomes to CSV and prevents duplicate successful check-ins within the same session (`has_success_this_session()`, `log_attendance()`), reused both by the pre-liveness duplicate check in `main.py` and by `log_attendance()`'s own internal downgrade.

- `src/pattern_flagger.py`
  Reads attendance logs and flags repeated failures, duplicate attempts, and clustered unrecognized attempts. Reused as-is by `dashboard/app.py` (flagged-row highlighting) and by the ProxyGuard Assistant's rules.

- `src/main.py`
  Defines `CheckinSession`, the shared check-in engine: per-frame face recognition, liveness detection (blink + head movement), single-person enforcement, the identity-liveness continuity guard, the pre-liveness duplicate check-in bypass, attendance logging, and per-outcome verification snapshots, all driven through one method (`process_frame()`). Both the desktop entry point (`if __name__ == "__main__"`) and `checkin_app/`'s web app construct a `CheckinSession` and feed it frames — so the two entry points share the exact same detection/liveness/logging behavior and only differ in how frames are captured and displayed (OpenCV window vs. browser MJPEG stream).

## Session Identity (`session_id`)

`session_id` is generated once per run/session and is treated as an opaque string by every module that consumes it (`attendance_logger.py`, `pattern_flagger.py`, the snapshot filenames, and the dashboard) — none of them parse its internal structure.

It is built by `class_config.build_session_id(subject, week_number)` from the current timestamp plus the selected class subject's short code and week number, rather than a bare timestamp:

```
YYYY-MM-DD_HHMM_<CODE>_Week<N>
e.g. 2026-07-07_0900_CSC649_Week3
```

This was changed because a single room/date can host multiple *different* class subjects, so a timestamp alone didn't tell a lecturer which class a set of check-ins belonged to; grouping by subject + teaching week is more useful for review than a raw timestamp. See [[decisions]] Decision 8. `<CODE>` (not the full subject name) is used to keep the id space-free and filesystem-safe, since it is also embedded directly into verification snapshot filenames (see Verification Snapshots below).

Two entry points can build a `session_id`:
- `src/main.py`'s terminal prompt (`prompt_session_setup()`), used by the desktop webcam check-in flow.
- `checkin_app/`'s session picker, which calls the same `class_config.build_session_id()` so both paths produce identically-formatted ids.

## Anti-Proxy Safeguards in the Check-in Engine

Beyond face recognition and the blink/head-movement liveness challenge, `CheckinSession` enforces the following while an attempt is active (not yet locked), so both the desktop flow and `checkin_app/` get them identically:

- **Single-person enforcement (Multi-face detection)** — the challenge only runs with exactly one face in frame. mediapipe Face Mesh is configured for a single face, so a second face present would let one person perform the challenge while a different (possibly registered) face is also visible. If more than one face is detected, the challenge pauses (timer frozen, no mediapipe processing) and a warning is shown until only one face remains. See [[decisions]] Decision 10.
- **Active face continuity / bounding-box transfer protection** — recognizing a face once is not enough to bind that identity to the rest of the attempt. Later recognition checks must keep showing the *same* name at a *similar* position (a simple center-distance check, not real object tracking) for the identity to keep counting; a small number of consecutive mismatches is tolerated, but exceeding it clears the identity and restarts the challenge. This closes a proxy loophole where a recognized identity could silently transfer to a swapped-in face or photo. See [[decisions]] Decision 11 and [[bugs]].
- **Duplicate check before liveness** — once the identity is stable under the continuity guard above, `_check_duplicate_checkin()` looks up `has_success_this_session()` (imported from `attendance_logger.py`, not re-implemented) at most once per distinct stable identity per attempt. A match locks the attempt directly into `duplicate_checkin`, skipping the liveness challenge. See [[decisions]] Decision 12.
- **On-screen box color coding** — each detected face's bounding box is drawn red when unrecognized/`"Unknown"` and green when recognized, so an unrecognized face (including a swapped-in one, once the continuity guard clears it) is visually obvious at a glance, in both the desktop window and the `checkin_app` browser stream.

## Lecturer Dashboard (`dashboard/`)

A standalone Flask web app, read-only, that gives a lecturer a fast, actionable view over the attendance log. Kept in its own top-level `dashboard/` folder (not inside `src/`) so it stays separate from the core detection modules, matching the project's module-independence convention.

### Folder structure
```
dashboard/
├── app.py                     # Flask app: all routes, data assembly, review data layer, assistant rules
├── templates/
│   ├── index.html             # Single page: filters, tabs, table, modals, floating assistant
│   └── _assistant_panel.html  # Assistant summary + recommendation cards (re-rendered by /assistant_panel)
└── static/
    ├── css/dashboard.css      # All styling — no inline <style>, matches docs/ui-references/DESIGN.md
    └── js/dashboard.js        # All client-side behavior — no inline <script> beyond the src tag
```
HTML, CSS, and JavaScript are kept in separate files rather than inlined in templates, so each concern (markup, styling, behavior) can be edited independently and the same design system stays consistent across `dashboard/` and `checkin_app/`.

### Table, filters, and search
- **Present / Attempts tabs** — a client-side toggle (no separate routes): Present shows `result=success` rows for the selected session, Attempts shows `result=failed` rows.
- **Session filter** — a dropdown of all unique `session_id` values (most recent first), defaulting to the most recent session.
- **Attempts-tab quick filters** — instant client-side chips (All / Successful / Failed / Flagged / Unknown / Duplicate / Liveness Failed), replacing an earlier reason dropdown for a faster, no-reload narrow.
- **Review-status filters** — an independent chip group (All Reviews / Unreviewed / Accepted / Suspicious), combined with the quick filters rather than replacing them.
- **Search** — a client-side name search box, shared across both tabs, persisted in `localStorage` so it survives a smart-refresh reload.
- **CSV export** — `/export.csv` mirrors exactly what the lecturer is currently looking at (session, tab, search, quick filter, review filter), rebuilt server-side from the same row-matching predicates the client uses.

### Analytics and flagging
- **Session Overview** — stat cards for total/successful/failed/flagged/duplicate/unknown/liveness-failed counts and the success rate, covering the whole selected session regardless of which tab is open.
- **Reason Breakdown** — a bar chart of `reason` counts within the selected session, colored by a rough good/warn/bad severity.
- **Flagged-row highlighting** reuses `src/pattern_flagger.flag_patterns()` directly — no duplicated detection logic. The same per-row flag feeds the Flagged quick filter, the Session Overview's flagged count, and the ProxyGuard Assistant's rules.
- **Inline verification snapshots** — each row shows a thumbnail of its matched `logs/snapshots/` file (`find_snapshot_for_row()`, mirroring `build_snapshot_filename()` in `src/main.py`), or a "no snapshot" placeholder.
- **Snapshot preview modal** — clicking a thumbnail opens a modal with the full-size image and the row's metadata (name/date/time/session/result/reason), instead of navigating away.

### Lecturer review workflow
Review decisions ("was this attempt actually suspicious?") are stored entirely separately from `logs/attendance.csv` — that file stays the raw, untouched system-generated record. `logs/reviews.csv` holds one row per reviewed attempt, keyed by a deterministic hash of the attendance row's own identifying fields (`build_review_id()`), since `attendance.csv` has no id column of its own.
- Each Attempts row has **Accept** / **Suspicious** buttons plus an **Add/Edit note** button (opening a small note modal) — a row with no review record yet is "Unreviewed".
- A **Review Summary** (Unreviewed / Accepted / Suspicious counts) sits above the Attempts table, updated in place after every review action with no page reload.
- `POST /review` upserts a review record; the response updates the row's badge, note, review summary, active review filter, and the ProxyGuard Assistant panel in place.

### Smart refresh
The page polls a lightweight `/status` endpoint every few seconds instead of blindly reloading. `get_attendance_version()` builds a change-detection token from actual content — row count, the latest row's own fields, `logs/reviews.csv`'s size, and the newest snapshot filename — rather than filesystem `mtime` alone, so both new attendance rows *and* lecturer review changes (even from another tab/device) are detected reliably. `/status` sends explicit no-cache headers and the client fetches with `cache: "no-store"` plus a cache-busting query parameter, so no browser/proxy ever serves a stale response. A detected change while the lecturer is actively interacting (typing, an open dropdown, an open modal) is deferred (`pendingReload`) rather than discarded, and applied the instant the interaction ends (a `focusout` listener and explicit hooks on modal close) rather than waiting out the rest of the poll interval.

### ProxyGuard Assistant
A floating, rule-based recommendation panel (`#assistant-fab` / `#assistant-modal`), available from both the Present and Attempts tabs, opened without leaving the page:
- **Session summary** at the top: success-rate progress bar, overall attention level (Low/Medium/High), main concern, and how many attempts still need review.
- **Prioritized recommendation cards** (flagged/suspicious attempts, duplicate attempts, unreviewed attempts, unknown faces, liveness failures, low success rate, or a normal-session message), each resolution-aware — a card disappears once the underlying condition is resolved (e.g. all rows reviewed) rather than lingering.
- Each card shows a priority badge, an affected-attempt count, a short "Triggered by" explanation, a compact detail line (names/times, truncated), a suggested action, and one or two action buttons (**View affected attempts**, **Open next unreviewed attempt**) that reuse the existing quick/review filter chips and table — never a second, parallel filtering or preview system.
- Entirely **rule-based** — every recommendation comes from a fixed rule evaluated against numbers the dashboard already computes; there is no external AI API and no free-text chat input (see [[decisions]] Decision 13).

### Reuse of `src/pattern_flagger.py` (no duplicated logic)
`app.py` adds `src/` to `sys.path` and imports `pattern_flagger` directly. It calls `pattern_flagger.flag_patterns()` and reads that report (plus `pattern_flagger`'s own reason constants) to decide which visible rows are flagged; the detection logic itself is never copied or reimplemented in the dashboard. Because `pattern_flagger` only depends on the standard library, importing it into the dashboard stays cheap and does not pull in OpenCV or MediaPipe.

### Data flow
The dashboard reads `logs/attendance.csv` and `logs/snapshots/` **read-only**, and reads/writes only `logs/reviews.csv` for the review workflow — it never modifies `logs/attendance.csv`. It resolves all paths relative to its own location, mirroring `attendance_logger.py`, so it finds the same files regardless of the working directory.

### How to run
```
python dashboard/app.py
```
Then open `http://127.0.0.1:5001/` in a browser. Port 5001 is used instead of Flask's default 5000 because macOS AirPlay Receiver occupies port 5000 and returns a 403 for other requests.

## Student Check-in Web App (`checkin_app/`)

A separate, standalone Flask app for the student-facing check-in flow, kept in its own top-level `checkin_app/` folder, matching the project's module-independence convention. See [[decisions]] Decision 9.

### Folder structure
```
checkin_app/
├── app.py                         # Flask app: session picker -> session_id -> live MJPEG check-in
├── templates/
│   ├── setup.html                 # Session picker: class-subject dropdown, week dropdown, "Start Session"
│   ├── checkin.html                # Live page: session header, MJPEG <img>, status text, action buttons
│   ├── _checkin_skeleton.html      # Shared skeleton markup (see Skeleton loading below)
│   └── confirm.html               # Unused leftover from an earlier iteration
└── static/
    ├── css/checkin.css            # All styling, including the skeleton shimmer
    └── js/checkin.js               # All client-side behavior for both the picker and the live page
```

### Session picker and skeleton loading
- **`GET /`** renders `setup.html`: dropdowns populated from `class_config.CLASS_SUBJECTS` and `WEEK_MIN..WEEK_MAX`.
- **`POST /start`** validates the submitted subject/week against the known values (never trusting raw form input), builds `session_id` via `class_config.build_session_id()`, starts the check-in station for it (loads face encodings once, opens the camera), and redirects to `/checkin`. This can take on the order of ~20s (encodings + camera warm-up).
- Because that POST blocks until the station is ready, `checkin.js` intercepts the picker's form submit client-side: it validates the fields, disables the submit button (without disabling the `<select>` elements themselves — a disabled form control is excluded from the submitted form data, which would otherwise silently strip `subject`/`week` from the POST), hides the picker, and shows a full check-in-page skeleton (`_checkin_skeleton.html`, shared with the live page) with a "Preparing check-in session…" message — then submits the form programmatically after one paint, so the lecturer sees immediate feedback instead of an apparently frozen page.
- On the live check-in page itself, the same skeleton is shown by default and hidden only once **both** the MJPEG `<img>`'s `load` event has fired (a genuine first camera frame decoded) **and** `/status` reports the station active — never on a fixed timeout, and never revealing a black/empty camera box in between. A timeout (30s) triggers a distinct failure state with a "Try again" action if the station never becomes ready.

### Live check-in
- **`GET /checkin`** renders the session header (class/week/`session_id`) and the skeleton/real-content pair described above.
- **`GET /video_feed`** streams server-side-processed webcam frames as MJPEG (`multipart/x-mixed-replace`).
- **`GET /status`** reports the current `flow_phase`, whether a reset is allowed, and the banner text — including the new `duplicate_checkin` phase, which the dashboard-shared color mapping in `checkin.js` renders with the same "warning" tone as `not_recognized` (handled, not a failure of identity/liveness).
- **`POST /reset`** starts a fresh attempt ("New check-in").
- **`POST /end_session`** releases the camera and clears the station (so the webcam light actually turns off) before returning to the session picker.

### Reuse of the shared check-in engine (no duplicated logic)
`app.py` imports `class_config` (subject list, `build_session_id`), `face_recognizer.load_known_faces`, and `main.CheckinSession`. It does **not** reimplement any recognition, liveness, duplicate-check, state-machine, logging, or snapshot logic: it drives the same `CheckinSession.process_frame` the desktop app uses, so both stay in lockstep and fixes apply once. The only web-specific code is how frames are *delivered* (webcam → MJPEG), *displayed* (`<img>` instead of an OpenCV window), and the skeleton-loading UX described above.

### Frame handling / streaming (performance)
Frames are captured and processed **server-side**; the browser only displays them. Processing resolution and display resolution are **decoupled** inside the shared `process_frame` (recognition on a 0.25x copy, mediapipe on a 0.5x copy, boxes drawn back onto the full-size frame), so the capture size only meaningfully drives the per-frame JPEG **encode** cost:
- **Capture (and stream) at 1280×720**, JPEG quality 80, ≤20 FPS generator cap.
- **Single active stream**: a `_stream_generation` counter ensures only the newest `/video_feed` generator drives the camera; older ones (reloads/reconnects) exit. All frame access is serialized under `_station_lock`.

See [[bugs]] for the tuning history of these values.

### Data / resource model
One physical webcam ⇒ one active check-in station: `_start_station` lazily opens the camera once and reuses it, and `/reset` reuses the same `CheckinSession` (and its one mediapipe `FaceMesh`) rather than recreating them per attempt. `/end_session` is the only path that releases the camera and drops the station entirely. Attendance rows and verification snapshots are written by the shared engine to the same `logs/attendance.csv` and `logs/snapshots/` the desktop app uses, in the identical format.

### How to run
```
python checkin_app/app.py
```
Then open `http://127.0.0.1:5002/` in a browser. Port 5002 avoids clashing with the lecturer dashboard (5001) and macOS AirPlay Receiver (5000). Runs with `threaded=True` and no debug reloader (it would spawn a second process fighting over the webcam) — restart the process to pick up code changes.

## Verification Snapshots

At every terminal check-in outcome (`confirmed`, `not_recognized`, `liveness_failed`, `duplicate_checkin`; `identity_mismatch` is retained as a terminal state but is currently unreachable now that the voice listening phase is gone), `CheckinSession` saves a snapshot of the webcam frame to `logs/snapshots/` (created automatically if missing), at the same moment attendance is logged for that outcome. Both the desktop flow and `checkin_app/` write to the same folder in the same format, since both drive the same `CheckinSession`.

- **Every outcome is captured, successes included** — not just failures. Because a check-in can pass the liveness checks and still be a photo of someone else held up to the camera, the saved image gives a lecturer a way to manually verify the actual face after the fact.
- **A pre-overlay frame is saved.** `CheckinSession` keeps an un-annotated copy of each frame taken before any bounding boxes or status text are drawn, so the face in the snapshot is unobstructed.
- **File naming** combines the `session_id`, the identity (`last_known_name` if one was established this attempt, otherwise `unknown`), the outcome reason as actually written to the CSV (not any pre-downgrade reason — see [[bugs]]), and an `HHMMSS` timestamp, e.g. `2026-07-07_0900_CSC649_Week3_unknown_liveness_timeout_171322.jpg`. For a duplicate check-in, the reason segment is `duplicate_check_in_this_session`, matching the CSV row exactly.

Snapshots are a manual review aid only; the system never uses them to auto-accept or auto-reject a check-in.

## Design Principles

- Keep modules independent and importable.
- Keep functions small and testable.
- Avoid storing raw voice data.
- Avoid storing side-face images.
- Persisted data: frontal reference images, face encodings, attendance logs, lecturer review decisions, and per-outcome verification snapshots. Still no raw voice data and no side-face images.
- Prefer clarity over premature optimization because this is an academic prototype.
- Keep each Flask app's HTML, CSS, and JavaScript in separate files, following one shared design system (see `docs/ui-references/DESIGN.md`).

## Related Documentation

- [[project-overview]]
- [[roadmap]]
- [[decisions]]
- [[testing]]
- [[bugs]]
- [[report]]
- [[CLAUDE]]
