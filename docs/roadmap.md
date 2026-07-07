
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

## In Progress
- 

## Next
- Step 8: Testing and refinement
- Phase 2b: camera streaming and the live check-in/liveness flow inside `checkin_app/` (the setup page from Phase 2a only builds and displays `session_id` so far; no check-in actually happens through the web app yet)

## Future
- Possible move from CSV to SQLite for attendance storage if the dashboard needs querying
- Countermeasure for live video call replay (screen/moiré detection) — not yet addressed

## Blocked
- 


## ## Related Documentation

- [[project-overview]]
- [[decisions]]
- [[testing]]
- [[bugs]]
- [[CLAUDE]]
