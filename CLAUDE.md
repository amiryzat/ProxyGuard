# ProxyGuard

## Claude Code Startup

- [[START_SESSION]]
## Documentation

Detailed documentation is located in the `docs/` folder.

- [[project-overview]]
- [[architecture]]
- [[roadmap]]
- [[decisions]]
- [[testing]]
- [[bugs]]


## Project Overview
ProxyGuard is a liveness aware face recognition system for proxy attendance detection. It is being built for a CSC649 (Special Topics in Computer Science) final project proposal at UiTM. The core problem it solves: normal face recognition attendance systems can be fooled when one student checks in on behalf of an absent classmate using a photo, video, or replayed face data. ProxyGuard adds multiple liveness checks on top of face recognition to confirm the person checking in is physically present and actively responding, not a static image or recording.

## Group Members
1. Muhammad Amir Izzat bin Rosdi (2025394889)
2. Muhammad Adli Fadhlan bin Azame (2025180775)
3. Muhammad Izzuddin bin Izad Emi (2025181293)

## Tech Stack
- Python 3.10+
- OpenCV (`opencv-python`) for video capture and face detection
- `face_recognition` (built on dlib) for face encoding and matching
- MediaPipe Face Mesh for blink detection and head pose tracking
- Speech to text: decided — Google Speech Recognition API via the `SpeechRecognition` + `PyAudio` packages (needs internet). Note for Apple Silicon dev machines: `SpeechRecognition`'s bundled `flac-mac` binary is Intel-only and fails with `OSError: Bad CPU type in executable`; fix is `brew install flac` so a native arm64 `flac` is on `PATH` (it's preferred over the bundled binary automatically).
- Flask for the lecturer-facing dashboard (`dashboard/`, built — see `docs/architecture.md`)
- Pandas for attendance logging (CSV based for now)

## Core System Design

### 1. Face Recognition (implemented — `src/face_recognizer.py`)
- Registered students each have one to three frontal reference photos stored in `data/known_faces/` (filenames may have a trailing `_N` for multiple photos of the same person, e.g. `NAME_1.JPG`; the trailing number is stripped when deriving the display name).
- Photos are loaded through PIL with EXIF-based orientation correction before encoding, since phone photos often store rotation as metadata rather than rotating the pixels.
- Each photo is converted into a 128 dimensional face encoding using `face_recognition`.
- Encodings are compared against a live detected face using distance matching (default tolerance 0.45, tightened over two steps: from the originally planned 0.6 to 0.5, then to 0.45 after a false-match incident involving Izzuddin, to reduce false-accept risk between similar-looking students).
- A minimum margin check (default 0.1, raised from 0.05 in the same tightening) between the best and second-best match distances is used to reject ambiguous matches instead of guessing between two close candidates. Tradeoff: with few reference photos per student, more legitimate matches may fall to "Unknown" — the intended direction to err for attendance integrity, since a rejected student can retry but a false accept is a proxy slipping through.
- The standalone test loop (`if __name__ == "__main__"`) downscales frames to 0.25x and only runs recognition every 3rd frame for smoother webcam playback; detection boxes are scaled back up for display.
- `locate_faces(frame)` is a second, cheaper entry point that returns only face bounding boxes (no encoding/comparison). `main.py` uses it to keep the on-screen box tracking a face after identity is already locked in, without repeating the more expensive encoding + distance comparison every frame.
- No side angle photos are needed for recognition. Side angle data is not stored anywhere.

### 2. Liveness Detection (multi-factor, this is the differentiator of the project) — `src/liveness_check.py` (+ `src/voice_challenge.py`, built but removed from the live flow)
Two checks currently run in the live flow (blink + head movement). A third, the voice challenge, is fully implemented as a standalone module but has been **removed from the live check-in loop** at the current proposal stage — see subsection 3 below, the flow note, and `docs/decisions.md` Decision 7. Together the active checks confirm a real, present, responsive person:

1. **Blink detection** (continuous, no prompt needed) — implemented
   Runs in the background the whole time a face is being checked. `BlinkDetector` uses MediaPipe Face Mesh eye landmarks to calculate eye aspect ratio (EAR) per eye and averages both eyes. A blink is counted when EAR drops below `EAR_THRESHOLD` (0.21) for at least `CONSECUTIVE_FRAMES` (2) frames and then recovers. A static photo or frozen video frame will not blink.

2. **Randomized head movement challenge** (active, prompted) — implemented
   `HeadMovementChallenge` picks a random direction from `left`, `right`, `up` (`CHALLENGE_DIRECTIONS`) and gives a 10 second window (`CHALLENGE_DURATION_SECONDS`) to match it. Direction is derived from MediaPipe Face Mesh landmarks (nose tip, left/right eye corners, chin) via normalized horizontal/vertical offset of the nose from face center (`get_head_pose`); the same offsets can also resolve to `down` or `center`, though `down` is not currently one of the challenge's random targets. Randomized per attempt so a pre-recorded video cannot reliably fake it. `main.py` additionally requires a blink to occur during the same window before counting the direction match as a pass, since a tilted static photo can mimic head movement but cannot blink.

3. **Randomized voice/word challenge** (active, prompted) — module implemented (`src/voice_challenge.py`), **NOT currently wired into the live flow** (removed from `main.py`; see subsection 3 and `docs/decisions.md` Decision 7). The module is kept intact and unimported so it can be reintegrated later. As built: `generate_challenge_number()` produces a random 3-digit number. `listen_for_number()` records via the mic (`speech_recognition` + `PyAudio`, 5s timeout / 5s phrase limit) and transcribes with the Google Speech Recognition API; `extract_digits()` converts spoken digit-words ("four", "two"...) or literal digits into a digit string for comparison. `get_digit_matches()` compares the expected number against the transcript position-by-position, returning a per-digit correct/incorrect list (intended for coloring each digit green or red on screen). It checks that a correct, timely verbal response occurred; it does NOT identify who is speaking and no voice biometric data is stored.

### 3. Combined Check-in Flow & Anti-Proxy Safeguards — `src/main.py`, implemented
`main.py` wires face recognition and liveness (blink + head movement) into one live webcam loop, driven by an explicit `flow_phase` state machine once the head-movement/blink challenge locks in. **The voice challenge is no longer part of this flow** (removed to prioritize flow reliability at the proposal stage — see `docs/decisions.md` Decision 7); the `countdown`, `listening`, and `voice_result` phases and the mid-challenge identity re-verification described in earlier revisions have been removed.

Current state machine:

`liveness_success` → `confirmed`, or `liveness_success` → `not_recognized`, or `liveness_failed`. Only `confirmed`, `not_recognized`, and `liveness_failed` are terminal (wait for the operator to press `n` to reset); `liveness_success` advances automatically on a timer. `identity_mismatch` is retained as a terminal state in the code but is **currently unreachable**, since it was only triggered during the (now removed) voice listening phase; it is kept so the flow can be reintegrated later.

- **Pre-lock identity tracking (`identified_name`)**: while the head-movement/blink challenge is still in progress (not yet locked), `identified_name` only updates when a processed frame produces a real match (`last_names[0] != "Unknown"`); an "Unknown" result is ignored and the last known good identification is kept. This matters because turning left/right/up during the challenge routinely causes a stray frame or two where `face_recognition` can't match the off-angle face — without this guard, that single bad frame would overwrite `identified_name` with "Unknown" right as the challenge passes, causing a real registered student to be logged as `not_recognized` purely from momentary angle-induced misdetection during their own head turn.
- **`liveness_success`** (2s, `LIVENESS_MESSAGE_SECONDS`): shows "LIVENESS DETECTION SUCCESSFUL" bottom-center, then routes to `confirmed` if a face was recognized, or `not_recognized` if not.
- **`confirmed`**: a recognized face that passed the blink + head-movement liveness challenge is confirmed directly (shows "ATTENDANCE CONFIRMED: {name}"). Terminal.
- Bounding box tracking during any locked phase uses `locate_faces()` (position only) rather than full recognition.

### 4. Attendance Logging (implemented — `src/attendance_logger.py`)
- CSV schema is `name`, `date`, `time`, `session_id`, `result`, `reason` — split into a `result` column (always `"success"` or `"failed"`) and a separate `reason` column (short human-readable string: `"confirmed"`, `"liveness timeout"`, `"face not recognized"`, or `"duplicate check-in this session"`; plus `"identity mismatch"`, which the code can still write but is currently unreachable now that the voice listening phase is removed), replacing an earlier single combined `status` column (e.g. `"liveness_failed"`, `"voice_failed"`) that mixed outcome and reason together.
- `log_attendance(name, result, reason, session_id, log_path=DEFAULT_LOG_PATH)` appends one row, creating the file with a header row the first time it's called if the file doesn't exist yet (or exists but is empty). If an existing file has a different/older header (schema mismatch), `_ensure_log_file` archives it to `attendance_legacy.csv` instead of overwriting or mixing row formats, then starts a fresh file with the current header — this ran once automatically when the schema changed from the old single-`status` format.
- **Duplicate detection is scoped to a session (`session_id`), not a calendar date.** `has_success_this_session(name, session_id, log_path)` only compares rows with a matching `session_id`; a new `"success"` result is downgraded to `"failed"` / `"duplicate check-in this session"` if that session already has one. This was changed from date-based dedup because a single room/date can host multiple separate class sessions — a date check would wrongly treat two different classes as duplicates of each other, or block a legitimate re-check-in in a later class the same day.
- `main.py` generates `session_id` exactly once per run, near the top of its `if __name__ == "__main__"` entry point — restarting `main.py` naturally starts a fresh session, so duplicate check-ins from a previous run no longer count against the new one. As of Phase 1 of a session-restructuring feature, `session_id` is no longer a bare timestamp: before the camera loop starts, `main.py` calls `prompt_session_setup()` to ask the lecturer (in the terminal) to pick a class subject from a small predefined list and a week number (1–14), then builds `session_id` with `build_session_id(subject, week_number)`. Both the predefined subject list (`CLASS_SUBJECTS`) and `build_session_id()` live in a new standalone module, `src/class_config.py` (dependency-free, matching the module-independence convention), not in `main.py` itself, so other entry points can reuse the exact same format without importing `cv2`/`mediapipe`. Format: `YYYY-MM-DD_HHMM_<CODE>_Week<N>`, e.g. `2026-07-07_0900_CSC649_Week3` — `<CODE>` is the short code portion of the selected subject (e.g. `CSC649` from `"CSC649 - Special Topics in Computer Science"`), kept space-free since it also feeds into snapshot filenames. See `docs/decisions.md` Decision 8. `attendance_logger.py` and `pattern_flagger.py` were confirmed to treat `session_id` as an opaque string (string equality / grouping only, never parsed), so neither needed changes for this new format.
- Every terminal outcome gets logged, not just successful ones: `main.py` calls `log_attendance` exactly once per check-in attempt, the moment `flow_phase` reaches a terminal state (`confirmed`, `not_recognized`, `liveness_failed`, or the currently-unreachable `identity_mismatch`), guarded by an `outcome_logged` flag so it isn't re-logged every frame while the terminal message is on screen. The student name logged is `confirmed_name` if one was recognized, otherwise `"Unknown"`.
- **Verification snapshot per outcome**: at the same terminal moment (inside the same `outcome_logged` guard), `main.py` also saves a snapshot of the webcam frame to `logs/snapshots/` (auto-created), for successes as well as failures. It saves a pre-overlay `clean_frame` copy taken right after the flip — before any boxes/text/challenge number are drawn — so the face is unobstructed. Filename is `{session_id}_{name}_{reason}_{HHMMSS}.jpg` (name = `confirmed_name` or `unknown`, slugified). This is a manual lecturer-review aid only (never used to auto-accept/reject), motivated by the Izzuddin false-match incident: a check-in can pass the liveness checks and still be a photo of someone else, so the actual image needs to be reviewable after the fact.
- The module has no dependency on any other `src/` module (only `csv`, `os`, `datetime`), matching the project's independent-module convention, and has a manual smoke-test block under `if __name__ == "__main__"` that logs sample rows under two different fake `session_id`s to demonstrate both the duplicate downgrade (same session) and the non-duplicate case (different session, same student).

### 5. Proxy/Suspicious Pattern Flagging (implemented — `src/pattern_flagger.py`)
Reads `logs/attendance.csv` and flags three patterns for lecturer review (never auto-rejects):
- **Repeated failures** (`find_repeated_failures`): any registered (non-`"Unknown"`) name with at least `REPEATED_FAILURE_THRESHOLD` (3) `"failed"` rows across the whole log, regardless of session — a signal about that person, not scoped to one class.
- **Duplicate attempts** (`find_duplicate_attempts`): groups rows with reason `"duplicate check-in this session"` by `(name, session_id)`, surfacing who tried to check in more than once successfully within the same session.
- **Clustered unrecognized attempts** (`find_unrecognized_clusters`): flags a `session_id` where `"face not recognized"` rows occur at least `UNRECOGNIZED_CLUSTER_THRESHOLD` (2) times within `UNRECOGNIZED_CLUSTER_WINDOW_MINUTES` (5) of each other. Grouped by session rather than name, since these rows are always logged under `"Unknown"`.
- `flag_patterns(log_path)` returns all three as a dict; `print_report(report)` renders it for the CLI. The module defines its own `DEFAULT_LOG_PATH` rather than importing it from `attendance_logger.py`, keeping it independently importable per project convention. Its `if __name__ == "__main__"` block writes a small sample CSV (in the system temp dir, not the real log) with two fake `session_id`s and runs all three checks against it.

### 6. Session Setup Config (implemented — `src/class_config.py`)
Standalone, dependency-free module (only `datetime`) introduced in Phase 1 of the session-restructuring feature described in section 4 above. Holds `CLASS_SUBJECTS` (the predefined, easily-editable list of `"<CODE> - <Full subject name>"` entries a lecturer can pick from), `WEEK_MIN`/`WEEK_MAX` (1–14), `subject_code(subject)` (splits out the short code before `" - "`), and `build_session_id(subject, week_number, now=None)` (the single source of truth for the `session_id` format — see section 4). Kept dependency-free and outside `main.py` specifically so a second entry point could import the same subject list and id-building logic without pulling in `cv2`/`mediapipe`; this is exactly what `checkin_app/` (section 7 below) does.

### 7. Student Check-in Web App, Setup Page Only (Phase 2a, implemented — `checkin_app/`)
A new, standalone Flask app — separate from the lecturer `dashboard/` app — living in its own top-level `checkin_app/` folder, matching the project's module-independence convention. **This is Phase 2a only: it implements the session setup page, nothing else.** It imports `CLASS_SUBJECTS`, `WEEK_MIN`, `WEEK_MAX`, and `build_session_id()` directly from `src/class_config.py` (added to `sys.path` the same way `dashboard/app.py` already does) rather than duplicating the Phase 1 subject list or the `session_id` format.
- `GET /` renders `templates/setup.html`: a class-subject dropdown and a week-number dropdown (1–14), plus a "Start Session" button.
- `POST /start` validates the submitted subject/week against the known Phase 1 values (never trusting raw form input — an invalid or tampered submission re-renders the setup form with an error instead of building a malformed id), builds `session_id` via `build_session_id()`, and renders `templates/confirm.html`, which simply displays the generated `session_id` alongside the chosen subject and week.
- Runs on port 5002 (`python checkin_app/app.py`), distinct from the dashboard's 5001 and macOS AirPlay's 5000.
- **Camera streaming and the live check-in/liveness flow for this web app are Phase 2b and are NOT built yet.** No check-in logic, camera access, or attendance logging happens here — `confirm.html` explicitly notes this. The only existing place a real check-in happens is still the webcam loop in `src/main.py`.
- See `docs/decisions.md` Decision 9 for why this is a separate app and why `build_session_id()` was relocated to `class_config.py` rather than imported from `main.py`.

## Planned Project Structure
```
proxyguard/
├── data/
│   └── known_faces/        # one to three frontal reference photos per student
├── src/
│   ├── face_detector.py    # OpenCV Haar Cascade face detection (done)
│   ├── face_recognizer.py  # face_recognition based identity matching (done)
│   ├── liveness_check.py   # blink detection + head movement challenge (done)
│   ├── voice_challenge.py  # randomized number generation + speech-to-text check (built, but not wired into main.py's live flow)
│   ├── class_config.py     # predefined class subject list, week bounds, build_session_id() (done — Phase 1)
│   ├── attendance_logger.py# logs check-ins to CSV (name/date/time/session_id/result/reason), session-scoped duplicate-check (done)
│   ├── pattern_flagger.py  # reads attendance CSV, flags repeated failures / duplicates / unrecognized clusters (done)
│   └── main.py             # combines everything into the live webcam check-in loop; prompts for class+week, saves a verification snapshot per outcome (done)
├── dashboard/              # standalone Flask lecturer dashboard (done — see docs/architecture.md)
│   ├── app.py              # reads attendance CSV, session filter, flagged-row highlighting (reuses pattern_flagger.py), per-session summary
│   └── templates/
│       └── index.html
├── checkin_app/            # standalone Flask student check-in web app, setup page only so far (Phase 2a — done; camera/check-in flow is Phase 2b, not built)
│   ├── app.py              # setup form (class + week dropdowns) -> builds session_id via class_config.build_session_id() -> confirmation page
│   └── templates/
│       ├── setup.html
│       └── confirm.html
├── logs/
│   ├── attendance.csv
│   └── snapshots/          # per-outcome verification snapshots (session_id + name + reason + timestamp .jpg)
├── requirements.txt
└── README.md
```

## Build Status
- [x] Step 1: Environment and folder structure
- [x] Step 2: Face detection (`face_detector.py`) using OpenCV Haar Cascade
- [x] Step 3: Face recognition (`face_recognizer.py`) using `face_recognition` encodings, EXIF orientation correction, and margin-based disambiguation
- [x] Step 4: Liveness detection
  - [x] Blink detection (EAR-based, continuous) — `liveness_check.py`
  - [x] Randomized head movement challenge (left/right/up, 10s window) — `liveness_check.py`
  - [x] Randomized voice/word challenge (Google Speech Recognition API, 3-digit number, per-digit matching) — `voice_challenge.py` (module built, but **removed from the live `main.py` flow** — see Core System Design §2/§3 and `docs/decisions.md` Decision 7)
- [x] Step 4.5 (not in original plan, added during integration): combined check-in flow — `main.py` (see Core System Design section 3). Note: the anti-proxy identity re-verification added here only ran during the voice listening phase, which has since been removed, so that safeguard is currently inactive.
- [x] Step 5: Attendance logging system (`attendance_logger.py`) — logs every terminal outcome to `logs/attendance.csv` with a `result`/`reason` split (not a single combined status column), a `session_id` per run, auto-creates/migrates the file's headers, and prevents duplicate successful check-ins scoped to a session (not a calendar date)
- [x] Step 6: Proxy detection / suspicious pattern flagging logic (`pattern_flagger.py`) — reads the attendance log from Step 5 and flags repeated failures per identity, duplicate attempts per session, and clusters of unrecognized-face attempts per session (beyond the real-time identity-swap check already in `main.py`, which prevents the swap live rather than flagging it after the fact)
- [x] Step 7: Lecturer dashboard (`dashboard/`) — standalone Flask web app with an attendance table, session filter (defaults to most recent session), flagged-row highlighting that reuses `pattern_flagger.py` (no duplicated logic), and a per-session summary (total/successful/failed/flagged). Run with `python dashboard/app.py` (port 5001). See `docs/architecture.md`.
- [x] Step 7.5 (not in original plan, Phase 1 of a session-restructuring feature): `session_id` now includes class subject + week context, not just a timestamp — `src/class_config.py` holds the predefined subject list and `build_session_id()`; `src/main.py` prompts the lecturer in the terminal for class + week before generating it. See Core System Design section 6 and `docs/decisions.md` Decision 8.
- [x] Step 7.6 (not in original plan, Phase 2a of a planned student check-in web page): `checkin_app/` — standalone Flask app implementing only the session **setup page** (class + week dropdowns, builds and displays `session_id` via the shared `class_config.build_session_id()`). Run with `python checkin_app/app.py` (port 5002). Camera streaming and the live check-in flow are Phase 2b and are **not yet built**. See Core System Design section 7 and `docs/decisions.md` Decision 9.
- [ ] Step 8: Testing and refinement

## Working Conventions
- Each module in `src/` should stay independent and importable on its own (`face_detector.py`, `face_recognizer.py`, `liveness_check.py`, `voice_challenge.py`, `class_config.py`, `attendance_logger.py`, `pattern_flagger.py`), combined together in `main.py`. This is intentional since three group members are working on separate modules to avoid merge conflicts.
- Keep functions small and testable in isolation (for example, a function should detect faces, a separate function should draw them, rather than combining both).
- Prefer clear, well-commented code over premature optimization since this is an academic proposal build, not a production system.
- No raw voice data or side-face images should ever be stored. What persists: frontal face images/encodings, attendance logs, and per-outcome verification snapshots (`logs/snapshots/`, frontal webcam frames used only for manual lecturer review).
- When adding new liveness checks or modifying thresholds (like the 0.45 face match tolerance or blink ratio threshold), note the reasoning in a comment since these values affect both accuracy and the project's write-up later.

## Known Open Decisions
- ~~Speech to text engine not finalized~~ — resolved: Google Speech Recognition API via `SpeechRecognition`/`PyAudio` (needs internet). Whisper was not adopted. Note: the voice challenge that used this has since been **removed from the live check-in flow** (module retained for possible reintegration — see `docs/decisions.md` Decision 7).
- Attendance storage implemented as CSV (`attendance_logger.py`); may still move to SQLite if the dashboard step needs querying, but CSV is sufficient for now.
- Dashboard (Flask) is now built (`dashboard/`, Step 7 done). Liveness checks, attendance logging, pattern flagging, and the lecturer dashboard all work end to end; only testing/refinement (Step 8) remains of the planned steps.
- Known limitation, not yet addressed: a live video call of the real student held up to the camera can genuinely blink and turn its head on command, so the current liveness checks can't distinguish "real webcam capture" from "webcam capturing a screen showing a live call." Would need a separate countermeasure (e.g. screen/moiré detection) — out of scope for now.
- Student check-in web app (`checkin_app/`) currently implements only the Phase 2a setup page (class + week selection, `session_id` generation/display). Camera streaming and the live check-in/liveness flow for this web app (Phase 2b) are not yet built; the webcam loop in `src/main.py` remains the only place a real check-in happens.


## Documentation Maintenance

When completing a task:

- Update `docs/roadmap.md` if project progress has changed.
- Update `docs/decisions.md` if an important technical decision was made.
- Update `docs/testing.md` if new testing was performed.
- Update other documentation if it becomes outdated.
- Never leave the documentation inconsistent with the codebase.
