# Decisions

This document records important technical decisions made during the project.

---

## Decision 1: Use Google Speech Recognition API for voice challenge

### Decision
Use Google Speech Recognition API through `SpeechRecognition` and `PyAudio` for the randomized voice challenge.

### Reason
It is simpler to implement within the project timeline and is sufficient for verifying that the student gives a timely spoken response. Whisper was not adopted because it adds more setup and processing complexity.

### Status
Accepted.

---

## Decision 2: Use CSV for attendance logging

### Decision
Store attendance records in `logs/attendance.csv`.

### Reason
CSV is simple, readable, easy to inspect, and enough for the current academic prototype. SQLite may be added later if the lecturer dashboard needs stronger querying.

### Status
Accepted for current prototype.

---

## Decision 3: Use session-based duplicate detection

### Decision
Prevent duplicate successful check-ins based on `session_id`, not calendar date.

### Reason
A student may attend multiple classes on the same date. Date-based duplicate checking would incorrectly block legitimate check-ins for different sessions.

### Status
Accepted.

---

## Decision 4: Do not store raw voice data or side-face images

### Decision
Only store frontal reference images, face encodings, and attendance logs. Do not store raw voice recordings or side-face images.

### Reason
This keeps the prototype simpler, reduces privacy risk, and matches the project scope.

### Status
Accepted.

---

## Decision 5: Tighten face matching thresholds

### Decision
Lower the default `recognize_face` tolerance from 0.5 to 0.45 and raise the default `min_margin` from 0.05 to 0.1 in `src/face_recognizer.py`.

### Reason
A false-match incident involving Izzuddin, where a visually similar student was accepted under the wrong identity, showed the previous thresholds were too permissive. A lower tolerance rejects more distant matches and a larger required margin between the best and second-best candidate rejects more ambiguous ones, reducing false accepts between similar-looking students. The tradeoff is that with only a few reference photos per student, more legitimate matches may fall back to "Unknown" — an acceptable direction to err for an attendance-integrity system, since a rejected legitimate student can simply retry, whereas a false accept is a proxy that slips through.

### Status
Accepted.

---

## Decision 6: Capture a verification snapshot at every terminal outcome

### Decision
In `src/main.py`, save a snapshot of the (pre-overlay) webcam frame to `logs/snapshots/` at every terminal check-in outcome — successes and failures alike — at the same point attendance is logged.

### Reason
The same Izzuddin false-match incident showed that automated matching, even after tightening, can still be fooled (e.g. a photo of another student that passes liveness and the voice challenge). A saved image at each outcome gives lecturers a manual verification safety net: they can review the actual face afterward, especially for check-ins that technically passed but may have used a photo of someone else. Successes are captured too because those are exactly the cases automated checks cannot catch on their own. This introduces a new class of persisted image data (webcam frames of every attempt, including unknowns) beyond the frontal reference images of Decision 4; the frames are frontal captures and the snapshots are used only for manual review, never for automated accept/reject.

### Status
Accepted.

---

## Decision 7: Remove the voice challenge from the live check-in flow

### Decision
Remove the countdown, listening, and voice-result phases (and the mid-challenge identity re-verification that only ran during listening) from the `flow_phase` state machine in `src/main.py`. A recognized face that passes the blink + head-movement liveness challenge is now confirmed directly. `src/voice_challenge.py` is left untouched and unimported so it can be reintegrated later.

### Reason
At the current proposal stage, flow reliability matters more than stacking an additional active challenge. The voice step depended on the mic, `PyAudio`, and a live internet round-trip to the Google Speech Recognition API, and its listening phase added a multi-second blocking window and several failure modes (mis-transcription, timeouts, ambient noise) that failed legitimate students. The blink + head-movement liveness check plus tightened face matching (Decision 5) and the per-outcome verification snapshots (Decision 6) already give a defensible liveness-and-review story for the proposal. The same false-match incident involving Izzuddin motivated leaning on tighter matching and the snapshot safety net rather than the voice layer. Removing voice also retires the identity re-verification, which existed only to catch a proxy swap during the voice listening window — with no listening phase, that window no longer exists, so the `identity_mismatch` terminal state is retained but currently unreachable.

### Status
Accepted for the current proposal stage; the voice module is preserved for possible reintegration.

---

## Decision 8: Include class subject and week in session_id

### Decision
Build `session_id` from the timestamp plus the selected class subject code and week number, rather than a bare timestamp. The format becomes `YYYY-MM-DD_HHMM_<CODE>_Week<N>` (e.g. `2026-07-07_0900_CSC649_Week3`). Before the camera loop starts, `src/main.py` prompts the lecturer in the terminal to pick a class from a small predefined list (`src/class_config.py`) and a week number (1–14). This is Phase 1 of a larger session-restructuring feature; the terminal prompt is a temporary stand-in for a planned web-based setup screen.

### Reason
A single classroom on a single date is routinely used by multiple *different* subjects, so a timestamp-only `session_id` doesn't tell a lecturer which class a set of check-ins belongs to. Duplicate detection is already scoped per session (Decision 3), but the session itself was previously identifiable only by when it ran. Embedding the subject code and week makes each session self-describing and lets attendance be grouped the way lecturers actually think about it — by subject and teaching week — which is more useful than a raw timestamp. The subject *code* (not the full name) is used so the id stays space-free and filesystem-safe, since it is also embedded in verification snapshot filenames.

The subjects live in a standalone, dependency-free `src/class_config.py` (matching the project's module-independence convention) so the list is easy to edit and can be reused by the future web setup screen without duplicating it.

`session_id` remains an opaque string to every other module. `attendance_logger.py` and `pattern_flagger.py` compare and group by it as a string and were confirmed not to parse its internal structure, so they needed no changes; the old format already contained an underscore, so the extra underscore-separated pieces are consistent with what those modules already tolerated.

### Status
Accepted (Phase 1). The web-based setup screen and any dashboard changes to surface subject/week are deferred to later phases.

---

## Decision 9: Separate student check-in web app; relocate `build_session_id` into `class_config.py`

### Decision
Build the student-facing check-in setup page as its own standalone Flask app in a new top-level `checkin_app/` folder (Phase 2a), separate from the existing lecturer `dashboard/` app. Relocate `build_session_id()` out of `src/main.py` into `src/class_config.py`, alongside the Phase 1 subject list it already depended on.

### Reason
`checkin_app/` needs to build `session_id` using the exact same format established in Phase 1 (Decision 8), so a session started from the web setup page is indistinguishable in format from one started via the terminal. Reusing it by importing `src/main.py` directly would have pulled in `cv2` and `mediapipe` (plus executed `main.py`'s module-level setup, e.g. `random.seed(os.urandom(8))`) purely to reach one string-building function. `class_config.py` was already a standalone, dependency-free config module by design (see Decision 8), so moving `build_session_id()` there gives both the terminal flow and the new web app a single lightweight source of truth for the `session_id` format, matching the project's existing module-independence convention (mirroring how `dashboard/` already reuses `pattern_flagger.py` without duplicating its logic). `src/main.py`'s terminal flow is otherwise unchanged — it now imports the function from `class_config` instead of defining it locally.

### Status
Accepted (Phase 2a — setup page only). Camera streaming and the live check-in flow for `checkin_app/` are Phase 2b and not yet built.

---

## Decision 10: Enforce a single person in frame during the active liveness challenge

### Decision
While a check-in attempt is active (not yet locked), require exactly one detected face in frame. If more than one face is detected, pause the liveness challenge — it cannot run, advance, time out, or lock — and display "Only one person allowed in frame, please ensure you are alone during check-in" until one face remains.

### Reason
The liveness challenge binds "a real, present, responsive person" to the recognized identity, but mediapipe Face Mesh is configured `max_num_faces=1`, so blink and head-pose are only ever evaluated for a single face. With two faces in frame, one person could perform the head movement and blink while a different person's (e.g. a registered student's) face is also present, letting the challenge pass without the challenged actions actually coming from the identified person — a direct hole in the proxy-detection the project exists to provide. Detecting more than one face is already cheap (`recognize_face` returns all face locations), so gating the challenge on a single face closes the gap without new dependencies. The countdown is frozen rather than failed during the interruption so a legitimate solo student isn't penalized for someone briefly passing behind them. This lives in the shared `CheckinSession.process_frame`, so both the desktop flow and `checkin_app/` enforce it identically. See docs/bugs.md (Bug 5).

### Status
Accepted.

---

## Related Documentation

- [[project-overview]]
- [[roadmap]]
- [[architecture]]
- [[testing]]
- [[bugs]]
- [[CLAUDE]]