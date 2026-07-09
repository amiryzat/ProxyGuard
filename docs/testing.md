
# Testing

This document records testing plans, test cases, and results.

---

## Test Case: Identity-liveness continuity guard (anti-proxy face swap)

### Test
Manual bypass attempt (reported by the project owner) plus scripted verification of `CheckinSession._update_identity_continuity()` driven with synthetic recognition results (no camera required).

### Purpose
Confirm that a recognized identity cannot silently transfer to a different or swapped-in face (e.g. a phone screen showing another person) during an active liveness challenge, while legitimate single-frame misdetections are still tolerated. See [[decisions]] Decision 11, [[bugs]] Bug 9.

### Steps
1. Manual (pre-fix): recognize a real registered face, hide it, show an unregistered face/phone image, bring the real face back to get re-recognized, then quickly swap the phone image back in at the same position and attempt to pass the challenge.
2. Scripted (post-fix), four scenarios run against `CheckinSession`:
   - Real face recognized, then swapped to `"Unknown"` at the same position for 3 consecutive recognition checks.
   - Real face recognized, one single stray `"Unknown"` frame, then the same real face reappears.
   - Real face recognized, then swapped to a *different* registered student's name at the same position.
   - Real face recognized, then the same name reported again but at a face position far across the frame.

### Expected Result
- Pre-fix: the challenge could complete and confirm under the original (now-swapped-away) identity.
- Post-fix: scenario 1 clears the identity within 3 checks and restarts the challenge; a same-instant "passed" never confirms during the tolerance window. Scenario 2 does *not* reset (single blip tolerated). Scenarios 3 and 4 are both blocked (name mismatch and spatial jump each independently break continuity).

### Actual Result
Matches expected in all four scripted scenarios (see `src/test_face_continuity.py` for the geometric-threshold self-check, and the fix session's inline verification output for the full `CheckinSession` scenarios). Confirmed via direct method calls, not a full camera run.

### Status
Passed (fix applied 2026-07-08).

---

## Test Case: Failed liveness attempt logs the recognized student's real name

### Test
Log a check-in attempt where a registered student is recognized but then deliberately fails the head-movement/blink challenge, and inspect the resulting `logs/attendance.csv` row and its verification snapshot filename.

### Purpose
Confirm a recognized student who fails liveness is attributed correctly instead of being logged as `"Unknown"`. See [[bugs]] Bug 8.

### Steps
1. Start a check-in, get recognized as a registered student.
2. Deliberately fail the challenge (let the timer expire without matching direction).
3. Inspect the CSV row's `name` column and the saved snapshot's filename for that attempt.
4. Also verify: a genuinely unrecognized face that fails liveness still logs `"Unknown"`, and a duplicate successful check-in within the same session is still downgraded correctly.

### Expected Result
The CSV row's `name` matches the recognized student and matches the snapshot filename's name segment; a genuinely unrecognized attempt still logs `"Unknown"`; duplicate-success downgrade behavior is unaffected.

### Actual Result
Confirmed via a temp-CSV simulation of `attendance_logger.log_attendance` with the fixed `log_name = confirmed_name or last_known_name or "Unknown"` logic: recognized+failed logged the real name, never-recognized+failed logged `"Unknown"`, and a second same-session success was still downgraded to `duplicate check-in this session`. Also reproduced live: an earlier attempt to verify this against the running `checkin_app`/dashboard initially still showed `"Unknown"` — traced to the running Flask processes having started *before* the fix was written to disk (no auto-reloader), not a logic error; confirmed correct after restarting both processes.

### Status
Passed (fix applied 2026-07-08).

---

## Test Case: Dashboard snapshot matching, including the name-mismatch fallback

### Test
Match every row in the real `logs/attendance.csv` against the real files in `logs/snapshots/` using `dashboard.app.find_snapshot_for_row()`, and load the dashboard's Attempts tab in a browser for a session containing `liveness timeout` rows.

### Purpose
Confirm the dashboard displays a matching inline snapshot for every row that has one on disk, including failed-liveness rows where the CSV `name` (`"Unknown"`, pre-Bug-8-fix) differs from the snapshot filename's name segment (`last_known_name`).

### Steps
1. Run the strict `session_id + name + reason` prefix match against all real CSV rows.
2. For rows where that match fails, apply the fallback (`session_id + reason + row time`, ignoring the name segment).
3. Load `GET /?session=...&tab=attempts` in a real (subprocess) Flask instance and confirm the rendered HTML includes the expected snapshot `<img>` src, and that `GET /snapshot/<filename>` serves it as `image/jpeg`.

### Expected Result
Rows with a same-named snapshot match via the strict prefix; rows with a name-mismatched snapshot (recognized-but-failed rows logged as `"Unknown"` before Bug 8) match via the fallback; only rows with genuinely no snapshot file show the "no snapshot" placeholder.

### Actual Result
13/14 real rows matched (up from 9/14 before the fallback was added); the one remaining miss had no snapshot file on disk at all (confirmed by directory listing), not a matching bug. Live route check confirmed the thumbnail renders and `/snapshot/...` serves the correct JPEG.

### Status
Passed.

---

## Test Case Template

### Test
-

### Purpose
-

### Steps
-

### Expected Result
-

### Actual Result
-

### Status
-

##  Related Documentation

- [[project-overview]]
- [[roadmap]]
- [[decisions]]
- [[bugs]]
- [[CLAUDE]]
