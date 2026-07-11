# Bugs

This document tracks important bugs, causes, fixes, and current status, organized into Resolved / Known Issues / Future Improvements. See [[decisions]] for the design rationale behind each fix and [[testing]] for how each was verified.

---

## Resolved

### Bug 1: Bounding box label can flash to "Unknown" on a single bad frame

**Bug:** A correctly recognized student could have their on-screen bounding box label flip to "Unknown" right as the head-movement/blink challenge locked in, even though they were recognized throughout the challenge.

**Cause:** The label was drawn from the raw per-frame `recognize_face` result, which routinely returns a one-frame "Unknown" on off-angle frames during a head turn.

**Fix:** Introduced `last_known_name` in `src/main.py`, which only updates on a non-"Unknown" match (the same anti-flicker guard `identified_name` already used for the logic path) and is used for the drawn label instead of the raw per-frame name.

**Status:** Fixed.

---

### Bug 2: Verification snapshot filename saved as "unknown" for a recognized student on a failed attempt

**Bug:** A registered student correctly recognized throughout a *failed* attempt still had their snapshot filename say `unknown`.

**Cause:** The snapshot filename was built from `confirmed_name`, which is `None` on every failed outcome regardless of whether the student was confidently recognized earlier in the attempt.

**Fix:** Build the snapshot filename from `last_known_name or "unknown"` instead, matching the on-screen label fix in Bug 1.

**Status:** Fixed.

---

### Bug 3: Bounding box keeps showing the previous student's name after the check locks

**Bug:** After a check-in locks, a different person stepping into frame before "New check-in" was pressed could have the *previous* student's name drawn over their face.

**Cause:** `last_known_name` is deliberately never cleared (that's what stops the pre-lock flicker in Bug 1), and the drawing loop applied it unconditionally, including after locking (when only position tracking, not full recognition, is still running).

**Fix:** Gate the drawn label on `check_locked` — once locked, only the tracking rectangle is drawn, no name label.

**Status:** Fixed.

---

### Bug 4: Duplicate check-in's snapshot filename said "confirmed" while the CSV correctly logged a duplicate failure

**Bug:** A second successful check-in within one session was correctly downgraded to `result=failed`, `reason=duplicate check-in this session` in the CSV, but its snapshot filename still said `..._confirmed_....jpg`.

**Cause:** `attendance_logger.log_attendance()` performs the downgrade internally and **returns** the actually-written `(result, reason)`, but the caller discarded that return value and built the snapshot filename from the pre-downgrade reason instead.

**Fix:** Capture and use `log_attendance()`'s return value when building the snapshot filename, so the filename always matches the CSV row for the same attempt.

**Status:** Fixed.

---

### Bug 5: Multi-face handling — shared identity label on every box, and challenge progressing with multiple people in frame

**Issue A:** With more than one face in frame, every box was labeled with the single `last_known_name`, so a second person's box wrongly showed the registered student's name.
**Fix:** Each box is labeled with its own per-face recognition result when more than one face is present; `last_known_name`'s fallback only applies with exactly one face.

**Issue B:** The liveness challenge could progress and lock while more than one face was in frame, letting one person perform the challenge while another (possibly registered) face was also present.
**Fix:** While an attempt is active, the challenge pauses entirely (no mediapipe, no progress, no timeout) whenever more than one face is detected, with an on-screen warning; it resumes with the same target direction and full time once back to one face. See [[decisions]] Decision 10.

**Status:** Fixed.

---

### Bug 6 & 7: `checkin_app` web check-in lagged/crashed on extended use, then an over-correction made the preview blurry

**Bug 6:** The web check-in noticeably lagged and crashed during extended use (many repeated check-in attempts).
**Cause:** Native-resolution camera capture plus full-quality per-frame JPEG encoding for the MJPEG stream (a cost the desktop's `cv2.imshow` window never pays), with no frame-rate cap; and an unbounded number of `/video_feed` generator threads accumulating across reloads/reconnects, all contending for one webcam and one shared session.
**Fix:** Lowered capture resolution and JPEG quality, added a ~20 FPS cap, and added a `_stream_generation` counter so only the newest stream generator drives the camera.

**Bug 7:** Bug 6's fix worked but made the browser preview blurry/low-resolution.
**Cause:** Processing resolution and display resolution don't need to move together — `CheckinSession.process_frame` already downscales internally for the heavy steps and draws results back onto the full-size frame, so shrinking the *capture* size only needlessly shrank the *display*, not the processing cost.
**Fix:** Capture/stream at a clear 1280×720 again (recognition still runs on an internal 0.25x copy), JPEG quality raised to 80; the Bug 6 perf/crash fixes (frame-rate cap, single-stream guard) are unchanged.

**Status:** Both fixed.

---

### Bug 8: Failed liveness attempts from a recognized student were logged as "Unknown"

**Bug:** A registered student recognized during a check-in but who then failed the liveness challenge was logged as `name=Unknown` in the CSV, even though the on-screen label and snapshot filename both showed the correct name.

**Cause:** The identity passed to `log_attendance()` was `confirmed_name or "Unknown"`, and `confirmed_name` is explicitly `None` on every failed outcome regardless of prior recognition.

**Fix:** Changed the logged identity to `confirmed_name or last_known_name or "Unknown"` — recovers the real name on a failure without ever changing what gets logged on an actual success (the two variables always move in lockstep pre-lock) or on a genuinely unrecognized attempt (`last_known_name` is also `None` there).

**Status:** Fixed.

---

### Bug 9: Recognized identity could silently transfer to a different/swapped face during an active liveness challenge (proxy bypass)

**Bug:** A student could be correctly recognized once, then swap in a different face (an unregistered face, another student's photo, or a phone screen), and still have the liveness challenge complete under the *first* recognized identity.

**Cause:** `identified_name`/`last_known_name` were sticky with no re-validation — once set, nothing ever cleared them if a later frame showed a different face, only overwritten by another confident match. The challenge's pass/fail signal itself has no awareness of identity at all.

**Fix:** Added the identity-liveness continuity guard, `CheckinSession._update_identity_continuity()` (see [[decisions]] Decision 11): a locked-in identity only stays valid while later checks keep matching the same name at a similar face position, tolerating a small number of consecutive mismatches (mirroring Bug 1's anti-flicker slack) before clearing and restarting the challenge. This is the project's bounding-box transfer protection. Verified via `src/test_face_continuity.py` and scripted `CheckinSession` scenarios — see [[testing]].

**Status:** Fixed.

---

### Bug 10: Dashboard smart refresh could miss changes or serve a stale cached response

**Bug:** Smart refresh worked "sometimes" — a new attendance row was occasionally not detected without a manual reload, and a lecturer review made in one tab was never reflected in another tab/device at all.

**Cause:** `get_attendance_version()` derived its change-detection token from `logs/attendance.csv`'s filesystem `mtime` + size only, which (a) never reflected changes to `logs/reviews.csv` (a review action writes a completely different file), and (b) had no explicit `Cache-Control` headers on `/status`, leaving it exposed to browser/proxy heuristic caching for a repeatedly-polled identical URL. Separately, a change detected while the lecturer was mid-interaction only re-applied on the *next* scheduled poll tick, up to `REFRESH_SECONDS` late.

**Fix:** Rebuilt `get_attendance_version()` from actual content — row count, the latest row's own fields, `logs/reviews.csv`'s size, and the newest snapshot filename — tolerant of a mid-write partial trailing row (never raises; retries next poll). Added explicit `Cache-Control: no-store, no-cache, must-revalidate, max-age=0` / `Pragma: no-cache` response headers, plus `cache: "no-store"` and a cache-busting query parameter on the client fetch. Added a `focusout` listener and explicit hooks on modal close so a pending reload applies the instant interaction ends, not on the next timer tick. A review action now also updates the acting tab's own `knownVersion` after applying its in-place UI update, so it doesn't also trigger a redundant full-page reload on itself moments later.

**Status:** Fixed.

---

### Bug 11: Disabling the session-picker `<select>` elements during skeleton loading silently stripped form data

**Bug:** Discovered while verifying the `checkin_app` session-picker skeleton loading state: submitting the picker sometimes re-rendered the picker with a validation error instead of starting the session, even though a valid class/week had been selected.

**Cause:** The skeleton-loading code disabled the picker's `<select>` elements (intending to prevent further interaction) before submitting the form. A disabled form control is excluded from the browser's submitted form data entirely, so `subject`/`week` were silently dropped from the `POST /start` body, and the server correctly rejected the resulting incomplete submission.

**Fix:** Stopped disabling the `<select>` elements. Hiding the entire picker container (already done) already prevents further interaction with them; only the submit button (whose value isn't read server-side) is safely disabled.

**Status:** Fixed.

---

### Bug 12: Duplicate check-in ran the full liveness challenge before being downgraded

**Bug:** A student who had already successfully checked in during the current session could still complete an entire second liveness challenge and see "ATTENDANCE CONFIRMED" — the duplicate was only caught afterward, silently, when `attendance_logger.log_attendance()` downgraded the CSV row to a failed duplicate. The lecturer-visible message and the actually-recorded outcome disagreed, and a full challenge ran for no reason.

**Cause:** Duplicate detection existed only inside `log_attendance()`, called once at the very end of an attempt — there was no check earlier in `CheckinSession` to short-circuit an attempt for a student already known to be checked in.

**Fix:** Added `CheckinSession._check_duplicate_checkin()`, called as soon as the recognized identity is stable (see [[decisions]] Decision 12), which reuses `attendance_logger.has_success_this_session()` and locks the attempt directly into a new `duplicate_checkin` terminal state — skipping the liveness challenge entirely — with a clear "already checked in" message and a CSV row logged directly as `failed` / `duplicate check-in this session`.

**Status:** Fixed.

---

## Known Issues

- **`identity_mismatch` terminal state is unreachable.** It is retained in `CheckinSession`'s state machine but its only trigger was the identity re-verification during the voice-listening phase, which has been removed (see [[decisions]] Decision 7). Kept so it can be rewired if the voice challenge is reintegrated.
- **Live video-call replay is not detected.** A live video call of the real, registered student — held up to the camera — can genuinely blink and turn its head on command, so it passes both the continuity guard (same face, same position) and the liveness challenge. This is a distinct threat from the swapped-photo/face-swap loophole Decision 11 closes, and is not yet addressed. See Future Improvements below.

## Future Improvements

- **Screen/replay detection** (e.g. moiré-pattern or screen-reflection detection) to catch the live video-call replay case above.
- **Move attendance storage from CSV to SQLite** if querying needs grow beyond what CSV comfortably supports (see [[decisions]] Decision 2).
- **Reintegrate the voice challenge** (`src/voice_challenge.py`), currently built but unused (see [[decisions]] Decision 7), as an additional active liveness factor if flow reliability concerns are resolved.

---

## Related Documentation

- [[project-overview]]
- [[roadmap]]
- [[decisions]]
- [[testing]]
- [[report]]
- [[CLAUDE]]
