
## Completed

### Core detection pipeline
- ✅ Step 1: Environment and folder structure
- ✅ Step 2: Face detection (`face_detector.py`) using OpenCV Haar Cascade
- ✅ Step 3: Face recognition (`face_recognizer.py`) using `face_recognition` encodings, EXIF orientation correction, margin-based disambiguation
- ✅ Step 4: Liveness detection — blink detection, randomized head movement challenge, and a randomized voice/word challenge (the voice module was built but later removed from the live flow — see [[decisions]] Decision 7)
- ✅ Step 4.5: Combined check-in flow (`CheckinSession` in `src/main.py`)
- ✅ Step 5: Attendance logging system (`attendance_logger.py`)
- ✅ Step 6: Proxy/suspicious pattern flagging (`pattern_flagger.py`)
- ✅ Session identity restructuring: `session_id` includes class subject + week context (`src/class_config.py`) — see [[decisions]] Decision 8
- ✅ Check-in engine refactor: `CheckinSession` shared by the desktop flow and `checkin_app/`
- ✅ Multi-face detection: the liveness challenge pauses while more than one face is in frame — see [[decisions]] Decision 10
- ✅ Active face continuity / bounding-box transfer protection: a recognized identity cannot silently transfer to a swapped-in face or photo — see [[decisions]] Decision 11
- ✅ Duplicate check before liveness: a student who already checked in this session is stopped before the liveness challenge runs, instead of after — see [[decisions]] Decision 12
- ✅ Correct-name attribution on failed/duplicate attempts (no more spurious `"Unknown"` rows) — see [[bugs]]

### Student check-in web app (`checkin_app/`)
- ✅ Session picker (class + week → `session_id`)
- ✅ Live check-in page streaming the webcam as MJPEG, driven by the shared `CheckinSession`
- ✅ Streaming performance tuning (frame-rate cap, single-active-stream guard, decoupled processing/display resolution)
- ✅ End-session camera cleanup (webcam released and station cleared, not just navigated away from)
- ✅ Skeleton loading UI: immediate full-page skeleton on session start, revealed only once the camera stream and station are genuinely ready, with a distinct timeout/failure + retry state
- ✅ Separated HTML/CSS/JavaScript architecture (`templates/`, `static/css/checkin.css`, `static/js/checkin.js`)

### Lecturer dashboard (`dashboard/`)
- ✅ Dashboard redesign: modern, separated HTML/CSS/JS architecture on a single monochromatic design system (see `docs/ui-references/DESIGN.md`)
- ✅ Present / Attempts tabs, session filter, Attempts-only quick filters, and independent review-status filters
- ✅ Search (client-side, persisted across smart refresh)
- ✅ Analytics cards (session overview + Reason Breakdown)
- ✅ Inline verification snapshots + snapshot preview modal
- ✅ Flagged-row highlighting reusing `pattern_flagger.py`
- ✅ CSV export mirroring the currently filtered view
- ✅ Lecturer review workflow (Accept / Suspicious + note, `logs/reviews.csv`, independent of the raw attendance log)
- ✅ Smart auto-refresh: content-derived change-detection token (not filesystem mtime alone), no-cache headers, interaction-safe deferred reload
- ✅ ProxyGuard Assistant: rule-based, prioritized, actionable recommendation panel (session summary, resolution-aware cards, filter/next-unreviewed action buttons)

## In Progress
-

## Next
- Step 8: Testing and refinement (see [[testing]])
- Continue expanding automated test coverage for the dashboard review workflow and the `checkin_app` skeleton-loading UI

## Future
- Possible move from CSV to SQLite for attendance storage if querying needs grow beyond what CSV comfortably supports.
- Countermeasure for live video call replay (screen/moiré detection) — not yet addressed. Distinct from the swapped-photo loophole closed by the active-face-continuity guard (Decision 11): a live video call of the real student can genuinely blink and turn its head on command, so it isn't caught by continuity or liveness checks alone.
- Possible reintegration of the voice challenge (`src/voice_challenge.py`), currently built but unused (Decision 7).

## Blocked
-

## Related Documentation

- [[project-overview]]
- [[architecture]]
- [[decisions]]
- [[testing]]
- [[bugs]]
- [[report]]
- [[CLAUDE]]
