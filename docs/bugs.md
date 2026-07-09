# Bugs

This document tracks important bugs, causes, fixes, and current status.

---

## Bug 1: Bounding box label can flash to "Unknown" on a single bad frame

### Bug
A correctly recognized student could have their on-screen bounding box label flip to "Unknown" right as the head-movement/blink challenge locked in — even though they were recognized throughout the challenge. It was most visible when a recognized person sat still and let the challenge fail: the label read "Unknown" at the moment of locking, making it look like the system had lost track of a known person when in reality only a single frame had missed the match.

### Where
`src/main.py`, the bounding box drawing loop (the `zip(last_face_locations, last_names)` loop that draws the rectangle and identity label).

### Cause
The label was drawn from `last_names` directly — the raw per-frame result of `recognize_face`. Off-angle frames during a head turn (and stray misdetections generally) routinely produce a one-frame "Unknown". If such a frame happened to be the last one processed before `check_locked` flipped true, the raw "Unknown" was what got drawn. On a failing outcome this was compounded: once locked, the fail branch feeds the label `confirmed_name or "Unknown"`, and `confirmed_name` is `None` on a fail, so the label stayed "Unknown" as well.

This is the same class of problem the existing `identified_name` protection already solved for the *logic* path (see CLAUDE.md, Core System Design §3, "Pre-lock identity tracking") — `identified_name` ignores single "Unknown" frames so a real student isn't logged as `not_recognized`. But that protection was never applied to the value used for the *visible label*, so the label had no such guard. This bug is related to, but distinct from, that earlier fix: same root cause (a single bad frame), different affected surface (what's drawn vs. what's logged).

### Fix
Introduced a separate tracked variable `last_known_name` in `src/main.py` that only updates when `recognize_face` returns a non-"Unknown" name — the same guard `identified_name` uses. The bounding box label is now drawn from `last_known_name` (`display_name = last_known_name or name`) instead of the raw `last_names[0]`, falling back to the raw name only before any confident match has been made. Unlike `identified_name`, `last_known_name` updates in the locked phase too, so a passing check keeps showing the confirmed identity and a failing check holds the last confident identity rather than flipping to "Unknown". It is reset to `None` on the `n` restart alongside `identified_name`. The raw `last_names` list is left untouched and still used wherever the actual per-frame recognition result matters. Only `src/main.py` was changed.

### Status
Fixed.

---

## Bug 2: Verification snapshot filename saved as "unknown" for a recognized student on a failed attempt

### Bug
When a registered student was correctly recognized throughout a *failed* liveness attempt (their real name shown on the bounding box the whole time), the saved verification snapshot in `logs/snapshots/` was still named with `unknown` — e.g. `2026-07-07_1814_unknown_liveness_timeout_181625.jpg` for someone who was clearly identified as a known student. This makes the manual-review snapshots misleading and hard to attribute, since the filename contradicts the identity that was visible on screen.

### Where
`src/main.py`, the terminal-outcome block that builds the snapshot filename via `build_snapshot_filename(...)` before `cv2.imwrite`.

### Cause
The snapshot filename was built from `confirmed_name or "unknown"`. `confirmed_name` is only set on a passing liveness outcome and is `None` on every failed outcome (`liveness_failed`, `not_recognized`, `identity_mismatch`). So on a failure the filename always fell back to `"unknown"`, even when the student had been confidently recognized during the attempt. The on-screen bounding box label had already been fixed to avoid exactly this by using the bad-frame-protected `last_known_name` (see Bug 1), but the snapshot filename was never switched over to that same protected value — so the label and the filename disagreed on a failed attempt.

### Fix
Build the snapshot filename from `last_known_name or "unknown"` instead of `confirmed_name or "unknown"` in `src/main.py`. `last_known_name` holds the last confidently recognized identity regardless of pass/fail (it only updates on a non-"Unknown" recognition), so a recognized student's snapshot is now named with their real name even when the attempt fails, and it falls back to `"unknown"` only when no confident identity was ever established during the attempt (e.g. a genuine `not_recognized`). This is a direct follow-on to the Bug 1 `last_known_name` fix, reusing the very same protected variable for a second output surface (the snapshot filename) that had been left on the unprotected `confirmed_name`. The attendance log row is deliberately left keyed on `confirmed_name` — only `attendance_logger.py` is untouched and only the snapshot filename construction in `main.py` changed. Only `src/main.py` was modified.

### Status
Fixed.

---

## Bug 3: Bounding box keeps showing the previous student's name after the check locks

### Bug
After a check-in reaches a locked state (the 2s `liveness_success` phase and the terminal `confirmed` / `not_recognized` / `liveness_failed` / `identity_mismatch` states, which wait for a reset), the bounding box keeps tracking whoever is currently in frame via `locate_faces`, but the name label stayed frozen on the previously recognized identity. If one student finished their check-in and stepped away and a different student sat down before `n` (desktop) / "New check-in" (web) was pressed, the box drew the previous student's name over the new person's face — misleading, and in a proxy-detection system actively wrong.

### Where
`src/main.py`, `CheckinSession.process_frame` — the bounding box drawing loop (`zip(self.last_face_locations, self.last_names)`). Because this is the shared check-in engine, the bug appeared identically in the desktop app and the `checkin_app/` web page, which both drive `CheckinSession`.

### Cause
A direct side effect of the Bug 1 fix interacting with the `check_locked` state. `last_known_name` is deliberately never cleared to "Unknown" (that is exactly what stops the pre-lock flicker), and the drawing loop applied `display_name = last_known_name or name` unconditionally — including after `check_locked` became true. Once locked, full recognition stops running (only `locate_faces` tracks position, with `names` filled as `confirmed_name or "Unknown"`), so `last_known_name` is frozen at the last recognized identity and got painted onto whoever the box now followed, regardless of whether it was still the same person.

### Fix
Gate the label on `check_locked` in the drawing loop. While the challenge is active (`not check_locked`) the label still uses the bad-frame-protected `last_known_name or name` exactly as before, so Bug 1's protection is intact. Once `check_locked` is true, no name label is drawn at all — only the tracking rectangle. `last_known_name` itself is left untouched (still needed for the anti-flicker guard during the challenge and for the Bug 2 snapshot filename), so this changes only how the label is *displayed* after locking, not the protection logic. The fix lives in the shared `CheckinSession.process_frame`, so it applies to both the desktop flow and `checkin_app/` with no separate change. Only `src/main.py` was modified.

### Status
Fixed.

---

## Bug 4: Duplicate check-in's snapshot filename says "confirmed" while the CSV correctly logs it as a duplicate failure

### Bug
When the same student successfully checked in twice within one session, the second attempt was correctly downgraded in `logs/attendance.csv` to `result=failed`, `reason="duplicate check-in this session"` — but the verification snapshot saved for that same attempt in `logs/snapshots/` was still named `..._confirmed_....jpg`. The snapshot filename and the CSV row disagreed about the outcome of the same attempt, making a duplicate look like a confirmed success if a lecturer reviewed the snapshots rather than the CSV `result`/`reason` columns.

### Where
`src/main.py`, `CheckinSession.process_frame` — the terminal-outcome block that calls `log_attendance(...)` and then builds the snapshot filename via `build_snapshot_filename(...)`. Because this is the shared check-in engine, the behavior was identical in the desktop app and the `checkin_app/` web page (both drive `CheckinSession`).

### Cause
`attendance_logger.log_attendance` performs the session-scoped duplicate downgrade *internally* and **returns** the actual written `(result, reason)` (which may differ from what was passed in). The caller ignored that return value: it called `log_attendance(..., "success", "confirmed", ...)` and then built the snapshot filename from the local pre-downgrade `log_reason` (`"confirmed"`). So on a duplicate, the CSV row was downgraded correctly (the downgrade happens inside `log_attendance`) but the snapshot filename kept the stale `"confirmed"` reason. This was not a duplicate-detection failure — dedup worked — purely a naming inconsistency from discarding `log_attendance`'s return value.

### Fix
Capture `log_attendance`'s return value and use the actually-written reason when constructing the snapshot filename: `_, written_reason = log_attendance(...)`, then `build_snapshot_filename(session_id, last_known_name or "unknown", written_reason)` instead of passing `log_reason`. A duplicate attempt's snapshot is now named `..._duplicate_check_in_this_session_....jpg`, matching its CSV row. The fix lives in the shared `CheckinSession.process_frame`, so it applies to both the desktop flow and `checkin_app/` with no separate change. `attendance_logger.py` was not touched (it already returned the correct value); only how that return value is consumed in `main.py` changed. Only `src/main.py` was modified.

### Status
Fixed.

---

## Bug 5: Multi-face handling — shared identity label on every box, and challenge progressing with multiple people in frame

Two related issues found during testing with two people in frame at once. Both were in the shared `CheckinSession.process_frame` (`src/main.py`), so they affected the desktop app and the `checkin_app/` web page identically.

### Issue A — every face box showed the same locked identity

**Bug:** With more than one face in frame, all boxes were labeled with the single `last_known_name`, so a second (or unregistered) person's box showed the registered student's name instead of their own recognition result.

**Cause:** A side effect of the Bug 1 fix. `last_known_name` is a single-identity anti-flicker guard, but the drawing loop applied `display_name = last_known_name or name` to *every* box, and the `last_known_name`/`identified_name` updates took `last_names[0]` regardless of how many faces were present.

**Fix:** In the drawing loop, when more than one face is detected each box is labeled with its own per-face `name`; the `last_known_name` fallback is used only when exactly one face is present (where the Bug 1 protection is meaningful). The `last_known_name` and `identified_name` updates are also gated on exactly one detected face, so one face out of several can never become the tracked or to-be-confirmed identity. Only `src/main.py` changed.

### Issue B — liveness challenge progressed with multiple faces present

**Bug:** The liveness challenge could run, advance, and lock while more than one face was in frame, so one person could perform the head-movement/blink challenge while a different person's face was also present — undermining the identity/liveness binding.

**Cause:** mediapipe Face Mesh is configured `max_num_faces=1`, so blink/head-pose only ever tracked one face, and nothing checked the total detected-face count (available from `recognize_face`) before running or locking the challenge.

**Fix:** During an active (unlocked) attempt, if more than one face is detected the challenge is paused: mediapipe is not run, the challenge cannot advance or lock, and its countdown is pinned to full time so the interruption can't cause a timeout failure. A clear warning ("Only one person allowed in frame, please ensure you are alone during check-in") is shown on-frame and via `checkin_app`'s status banner. Once a single face remains, the challenge resumes with full time and the same target direction. See docs/decisions.md (Decision 10). Only `src/main.py` changed.

### Status
Fixed.

---

## Bug 6: `checkin_app` web check-in lags and crashes on extended use (MacBook Air M5)

### Bug
The web check-in (`checkin_app/`) was noticeably laggier than the desktop app and crashed during extended use, especially across many check-in attempts in one session (repeatedly pressing "New check-in").

### Where
`checkin_app/app.py` — the webcam capture setup (`_start_station`) and the MJPEG generator (`_generate_frames`). Not `src/main.py`: the recognition/mediapipe work is shared and was already optimized.

### Cause
Two separate problems, both streaming-specific (the desktop app doesn't stream, so it never paid these costs):

**Lag.** The heavy per-frame work — face recognition every 3rd frame at 0.25x scale, mediapipe at 0.5x scale — already lives in the shared `CheckinSession.process_frame`, and `checkin_app` *does* reuse it (it calls `session.process_frame`). So frame skipping/downscaling was **not** the problem. The web-only overhead was: (a) `cv2.VideoCapture(0)` opened at the camera's **native resolution** (often 1080p on a MacBook), and (b) **every** frame JPEG-encoded at OpenCV's default quality (95) for the MJPEG stream. Encoding a full-resolution, high-quality JPEG per frame — a cost the desktop's native `cv2.imshow` window never incurs — was the dominant extra load. The capture/encode loop also ran with no frame-rate cap, pegging the CPU; on a fanless MacBook Air M5 (dlib and mediapipe are CPU-only here — no usable GPU offload for this stack) sustained 100% CPU causes thermal throttling, which shows up as progressive lag.

**Crash.** Each `<img>`→`/video_feed` connection starts a `_generate_frames()` generator in its own Flask worker thread. On a page reload, a second tab, or the browser reconnecting the stream, a **new** generator started while the old one kept looping (reading the camera and running mediapipe). Nothing bounded this, so over extended use camera-read/mediapipe threads accumulated, all contending for the single webcam and the single shared session — resource growth that both worsened lag and led to crashes. (mediapipe graphs are not thread-safe; the `_station_lock` serialized `process_frame` so calls never truly overlapped, but the pile-up of live threads/handles remained.)

### Fix
All changes are in `checkin_app/app.py`; `src/main.py` and the desktop flow are untouched (desktop keeps native capture):
- **Capture resolution** lowered to 640×480 via `cap.set(CAP_PROP_FRAME_WIDTH/HEIGHT, ...)`, so every downstream step (recognition, mediapipe, and especially the per-frame JPEG encode) works on a much smaller frame.
- **JPEG stream quality** dropped from the default 95 to 60 (`cv2.imencode(".jpg", frame, [IMWRITE_JPEG_QUALITY, 60])`) — still clearly legible for a face and on-screen instructions, far cheaper to encode and transmit.
- **Frame-rate cap** of ~20 FPS added to the generator loop (a short sleep, taken *outside* the lock), so the loop can't spin the CPU flat out between recognition frames.
- **Single-stream guard**: a module-level `_stream_generation` counter is bumped when a new stream starts; each generator exits its loop once superseded, so only the newest generator ever drives the camera + session. This stops thread/handle accumulation across reloads and repeated attempts.

Frame skipping and downscaling were confirmed already-shared and left as-is (no duplication introduced). Trade-off noted: recognition now runs on a 640×480 capture (its internal 0.25x → 160×120), smaller than the desktop's native-capture input; kiosk check-ins have a large, close face so this is expected to be fine, and `CAPTURE_WIDTH/HEIGHT` are named constants that can be raised (e.g. 960×540) if recognition degrades. Snapshots are now saved at the capture resolution (640×480) rather than native.

### Status
Fixed.

---

## Bug 7: First lag fix over-corrected — web preview became blurry/low-resolution

### Bug
The Bug 6 lag fix worked, but it made the browser preview look blurry and low-resolution — a step backward for something meant to be demoed.

### Where
`checkin_app/app.py` — the capture-resolution and JPEG-quality knobs added in Bug 6.

### Cause
Bug 6 lowered **both** the processing cost and the visible quality together, by dropping the capture resolution to 640×480 and the JPEG quality to 60. But processing resolution and display resolution don't need to move together: the shared `CheckinSession.process_frame` already decouples them — it downscales *internally* for the heavy steps (recognition on a 0.25x copy, mediapipe on a 0.5x copy) and draws the resulting boxes/labels back onto the full-size frame, which is what gets streamed. So the small 640×480 capture shrank the displayed frame (and the internal 0.25x recognition copy to a marginal 160×120) with no real need — the capture size only meaningfully drives the per-frame JPEG **encode** cost, not the recognition/mediapipe cost.

### Fix
Decouple the two by capturing at a clear display resolution again and letting `process_frame`'s existing internal downscale handle processing speed:
- **Capture (and stream) at 1280×720** instead of 640×480. The internal 0.25x recognition copy is now 320×180 — the same input size the desktop flow has always used successfully — and mediapipe runs on a 0.5x (640×360) copy, with boxes/labels scaled back onto the full 1280×720 frame for display. No new code was needed for this decoupling; it is the pattern already in the shared `process_frame`.
- **JPEG stream quality raised from 60 to 80** — moderate-high, presentable for a demo.
- The Bug 6 crash/perf fixes are **unchanged**: full recognition still runs only every 3rd frame, the generator is still capped at ~20 FPS, and the single-stream `_stream_generation` guard still prevents thread/handle accumulation. Because processing resolution is now handled separately, capturing larger is affordable — the extra cost is only the JPEG encode (a larger frame at quality 80 vs. the old small frame at 60), well below the original native-1080p/quality-95 path that caused the crash. Verification snapshots are now saved at 1280×720 again.

### Values (capture / processing / stream)
- **Capture:** 1280×720
- **Processing:** recognition on 0.25x → 320×180 (every 3rd frame); mediapipe on 0.5x → 640×360
- **Stream:** 1280×720 (full frame with boxes/labels), JPEG quality 80, ≤20 FPS

### Status
Fixed.

---

## Bug 8: Failed liveness attempts from a recognized student were logged as "Unknown"

### Bug
A registered student who was correctly recognized during a check-in, but then failed the head-movement/blink liveness challenge, had their attendance row logged as `name=Unknown` instead of their real name — even though the on-screen label and the verification snapshot filename both showed the correct name the whole time. The dashboard, which reads directly from `logs/attendance.csv`, inherited the same problem.

### Where
`src/main.py`, `CheckinSession.process_frame` — the terminal-outcome block that calls `log_attendance(...)`.

### Cause
The identity passed to `log_attendance` was `self.confirmed_name or "Unknown"`. `confirmed_name` is explicitly set to `None` on **every** failed outcome (`liveness_failed`, and `not_recognized` whenever no confident match was made) regardless of whether the person had already been confidently recognized earlier in the same attempt. So any failed attempt fell straight to `"Unknown"` in the CSV, while the snapshot filename (already fixed in Bug 2) used the bad-frame-protected `last_known_name` and showed the real name — the two outputs disagreed on the same attempt.

### Fix
Changed the logged identity to `self.confirmed_name or self.last_known_name or "Unknown"`. `identified_name` and `last_known_name` are updated from the exact same trigger (a single confidently recognized face) and always move in lockstep pre-lock, and `confirmed_name` is only ever derived from `identified_name` — so `confirmed_name` is never truthy while `last_known_name` is falsy, meaning this fallback **never changes a successful "confirmed" row**, it only recovers the identity on a failure. A genuinely unrecognized attempt (`not_recognized`) still logs `"Unknown"`, since `last_known_name` is also `None` in that case. Session-based duplicate detection is unaffected, since it only triggers on `result == "success"`, which still uses `confirmed_name` unchanged. Only `src/main.py` was modified.

### Status
Fixed.

---

## Bug 9: Recognized identity could silently transfer to a different/swapped face during an active liveness challenge (proxy bypass)

### Bug
A serious anti-proxy hole: a student could be correctly recognized once, then swap in a different face (an unregistered face, another student's photo, or a phone screen) and still have the liveness challenge complete under the *first* recognized identity. Demonstrated bypass: recognize a real face as a registered student, hide it, bring it back into frame to get re-recognized, then quickly hold up a phone image of a different person at the same screen position — the bounding box and the eventual confirmed identity kept using the real student's name even though a different face was now performing the head-movement/blink challenge.

### Where
`src/main.py`, `CheckinSession` — `identified_name`/`last_known_name` tracking in `process_frame`, and the `"passed"` branch that derives `confirmed_name`.

### Cause
`identified_name` (and `last_known_name`) were **sticky with no re-validation**: once set from a single confident recognition frame, nothing ever cleared them if a later frame showed a different face or `"Unknown"` — they only ever got *overwritten* by another confident match, never invalidated by a mismatch. Meanwhile the challenge's pass/fail signal comes purely from mediapipe's blink/head-pose on whatever face is *currently* in frame, with no awareness of identity at all. The two signals were only ever glued together through the stale `identified_name`, so recognizing a face once was enough to bind that name to the rest of the attempt, regardless of who (or what image) was actually performing the challenge.

### Fix
Added a conservative identity-liveness continuity guard, `CheckinSession._update_identity_continuity()` (see [[decisions]] Decision 11 for the design rationale):
- Once an identity is locked in for the attempt, a later single-face recognition check only counts as continuous if it returns the **same name** *and* stays spatially close to the last confirmed face position (center-distance ≤ 35% of frame width — a deliberately simple check, not real object tracking).
- Up to 2 consecutive mismatched checks are tolerated (mirroring the existing single-bad-frame anti-flicker slack from Bug 1), so one stray misdetection during a head turn doesn't wipe a legitimate student's identity.
- On the 3rd consecutive mismatch, `identified_name`/`last_known_name`/the tracked face position are all cleared and the challenge restarts from scratch (fresh direction + fresh timer) — the identity must be re-earned by a continuously present, matching face.
- Separately, the `"passed"` branch now only confirms `identified_name` when `identity_mismatch_streak == 0` **at that exact instant**, closing a narrow race window where a challenge could complete during the tolerance grace period, just before the streak formally cleared the identity.
- A brief "Face changed or lost, please keep the same face in frame" message shows on-frame and via `checkin_app`'s status banner when continuity breaks.

Verified (via `CheckinSession` driven with synthetic recognition results, no camera needed): a real recognition followed by a swap to `"Unknown"` at the same position clears the identity within 3 checks and never confirms mid-grace-period; a single stray misdetection does not falsely reset a legitimate student; swapping to a *different* registered student's face is also blocked; a large spatial jump alone breaks continuity even if the name happened to still match. A minimal self-check for the geometric threshold lives in `src/test_face_continuity.py`. Multi-face blocking (Bug 5 / Decision 10) is unaffected — this guard only runs pre-lock on single-face frames and defers to the existing multi-face pause otherwise. Only `src/main.py` was modified (plus the new standalone `src/test_face_continuity.py`).

### Status
Fixed.

---

## Related Documentation

- [[project-overview]]
- [[roadmap]]
- [[decisions]]
- [[testing]]
- [[CLAUDE]]