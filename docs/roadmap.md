
## Completed
- Step 1: Environment and folder structure
- Step 2: Face detection (`face_detector.py`) using OpenCV Haar Cascade
- Step 3: Face recognition (`face_recognizer.py`) using `face_recognition` encodings, EXIF orientation correction, margin-based disambiguation
- Step 4: Liveness detection — blink detection, randomized head movement challenge, and a randomized voice/word challenge (the voice module was built but later removed from the live `main.py` flow — see [[decisions]] Decision 7)
- Step 4.5: Combined check-in flow (`main.py`) — the anti-proxy identity re-verification added here ran only during the voice listening phase and is inactive now that voice was removed
- Step 5: Attendance logging system (`attendance_logger.py`)
- Step 6: Proxy/suspicious pattern flagging (`pattern_flagger.py`)
- Step 7: Lecturer dashboard (`dashboard/`) — Flask web app: attendance table, session filter (defaults to most recent session), flagged-row highlighting reusing `pattern_flagger.py`, and a per-session summary (total / successful / failed / flagged)
- Phase 1 (session_id restructuring, not in original numbered plan): `session_id` now includes class subject + week context instead of a bare timestamp — predefined subject list and `build_session_id()` added in `src/class_config.py`; `src/main.py` prompts the lecturer for class + week in the terminal before generating it. See [[decisions]] Decision 8.
- Phase 2a (student check-in web app, setup page only): new standalone `checkin_app/` Flask app — class + week dropdowns, generates and displays `session_id` via the shared `class_config.build_session_id()`. See [[decisions]] Decision 9.
- Check-in engine refactor: `src/main.py`'s per-frame recognition/liveness/logging/snapshot logic was extracted into a `CheckinSession` class so the desktop flow and `checkin_app/` share one engine instead of duplicating it.
- Phase 2b (student check-in web app, live check-in): `checkin_app/` now streams the webcam into the browser as MJPEG, driven by the shared `CheckinSession` — full recognition + liveness + logging + snapshot flow, a "New check-in" button in place of the desktop's `n` key, and streaming performance tuning (frame-rate cap, single-active-stream guard, decoupled processing/display resolution). See [[bugs]] Bug 6/Bug 7.
- Dashboard Phase A (inline verification snapshots): each attendance row matches and displays a thumbnail of its `logs/snapshots/` file (or a "no snapshot" placeholder), with a fallback match on session+reason+timestamp for older rows where the CSV name and snapshot name diverged (see [[bugs]] Bug 8).
- Dashboard Phase B (Present / Attempts tabs): the attendance table is split into two tabs on one page, filtered by `result`, each with its own per-tab summary stats.
- Dashboard Phase C (reason filter): a reason dropdown inside the Attempts tab, scoped to the selected session and applied on top of the session filter.
- Anti-proxy safeguards in the check-in engine: single-person enforcement during the active challenge (see [[decisions]] Decision 10, [[bugs]] Bug 5), and an identity-liveness continuity guard preventing a recognized identity from transferring to a swapped-in face/photo (see [[decisions]] Decision 11, [[bugs]] Bug 9). On-screen bounding boxes are now color-coded red (unrecognized) / green (recognized).
- Logging fix: a recognized student who fails the liveness challenge is now logged (CSV and dashboard) under their real name instead of "Unknown", matching what the verification snapshot already showed (see [[bugs]] Bug 8).

## In Progress
- 

## Next
- Step 8: Testing and refinement

## Future
- Possible move from CSV to SQLite for attendance storage if the dashboard needs querying
- Countermeasure for live video call replay (screen/moiré detection) — not yet addressed. Distinct from the swapped-photo loophole closed by the identity-continuity guard (Decision 11): a live video call of the real student can genuinely blink and turn its head on command, so it isn't caught by continuity or liveness checks alone.

## Blocked
- 


## ## Related Documentation

- [[project-overview]]
- [[decisions]]
- [[testing]]
- [[bugs]]
- [[CLAUDE]]
