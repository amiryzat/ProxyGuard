# Project Overview

## Purpose
ProxyGuard is a liveness-aware face recognition attendance system for detecting proxy attendance. It is built for a CSC649 Special Topics in Computer Science final project proposal at UiTM.

## Problem
Normal face recognition attendance systems can be fooled when a student checks in for an absent classmate using a printed photo, video, replayed face data, or another spoofing method. ProxyGuard reduces this weakness by combining face recognition with multiple liveness checks to verify that the person checking in is physically present and actively responding.

## Target Users
- Lecturers who need to verify student attendance and review flagged/ambiguous attempts.
- Students who check in through the web-based check-in kiosk.
- Academic evaluators reviewing the project proposal and prototype.

## Objectives
- Recognize registered students using stored frontal face reference images.
- Detect liveness through blink detection and randomized head movement.
- Enforce that exactly one person is present during an active check-in, and that the recognized identity stays bound to the same continuous face throughout the challenge — preventing a recognized identity from silently transferring to a swapped-in face or photo (see [[decisions]] Decision 10/11).
- Detect an existing successful check-in for the current session as soon as the identity is stable, **before** the liveness challenge is allowed to run to completion, so a student who is already present isn't shown a false success message and doesn't waste time on a challenge whose result will be discarded anyway (see [[decisions]] Decision 12).
- Log attendance results with success or failure reasons, correctly attributing failed and duplicate attempts to the recognized student when one was identified.
- Flag suspicious attendance patterns automatically and give the lecturer a fast, actionable way to review them — filters, snapshots, a review workflow, and a rule-based recommendation assistant — without ever auto-accepting or auto-rejecting a record.

A randomized voice challenge and a mid-challenge identity re-verification were also built but have since been **removed from the live check-in flow** to prioritize reliability at the current proposal stage; the voice module (`src/voice_challenge.py`) is retained for possible reintegration. See [[decisions]] (Decision 7).

Session identity carries the selected class subject and week number, not just a timestamp, since a single room/date can host multiple different subjects. See [[decisions]] (Decision 8). The student-facing web app (`checkin_app/`) starts from a session picker (pick class + week) and then runs the full live check-in flow, streaming the webcam into the browser. See [[decisions]] (Decision 9).

## Current Features

### Check-in engine (`src/`, shared by the desktop app and `checkin_app/`)
- Face recognition against registered students, with a tightened distance/margin threshold to reduce false accepts (Decision 5).
- Continuous blink detection plus a randomized head-movement challenge (blink + head-turn liveness).
- **Multi-face detection**: the challenge pauses (no progress, no timeout) while more than one face is in frame (Decision 10).
- **Active face continuity**: a recognized identity must stay bound to the same physical face position for the rest of the attempt, or it is cleared and the challenge restarts — this is the project's **bounding-box transfer protection**, closing the loophole where a recognized identity could silently transfer onto a swapped-in face or phone photo (Decision 11).
- **Duplicate detection before liveness**: once the recognized identity is stable, the engine checks whether that student already has a successful check-in this session and, if so, stops the challenge immediately and enters a dedicated `duplicate_checkin` terminal state instead of running (and discarding) a full liveness attempt (Decision 12).
- Session-scoped duplicate downgrade in the attendance log (a second successful check-in in the same session is recorded as a failed duplicate, not a second success).
- A verification snapshot is saved to `logs/snapshots/` for every terminal outcome (success, failure, or duplicate), named consistently with the CSV row.

### Student check-in web app (`checkin_app/`)
- **Session picker**: a lecturer selects a class subject and week before the camera starts; the session id is generated from that selection (Decision 8/9).
- **Skeleton loading state**: submitting the session picker immediately shows a full check-in-page skeleton (shimmering placeholders for the heading, session card, status card, camera frame, and action buttons) while the session/camera are prepared in the background, so the picker never looks frozen during the ~20s startup. The real camera feed is only revealed once the MJPEG stream has produced a genuine first frame and `/status` confirms the station is active — never on a fixed timeout. A timeout-based failure state (with a retry action) covers genuine startup failures.
- Live MJPEG check-in stream, status polling, "New check-in", and "End session" (full camera/session cleanup so the webcam light turns off).

### Lecturer dashboard (`dashboard/`)
A standalone, read-only Flask app for reviewing attendance:
- **Present / Attempts tabs**, session filter, and an Attempts-only quick-filter set (Failed / Flagged / Unknown / Duplicate / Liveness Failed) plus independent review-status filters (Unreviewed / Accepted / Suspicious).
- **Search** by student name, applied client-side across both tabs.
- **Analytics cards** (session-wide totals, success rate, flagged/duplicate/unknown/liveness counts) and a **Reason Breakdown** bar chart.
- **Inline snapshot thumbnails** with a **snapshot preview modal** (click to enlarge, with full attempt metadata).
- **Lecturer review workflow**: each Attempts row can be marked Accepted or Suspicious with an optional note, stored independently in `logs/reviews.csv` so the raw attendance log is never modified; a per-session review summary (Unreviewed/Accepted/Suspicious counts) is shown alongside the table.
- **Smart auto-refresh**: the page polls a lightweight status endpoint and only reloads when the underlying data has actually changed (attendance rows, reviews, or snapshots) — never while the lecturer is mid-interaction (typing, an open dropdown, an open modal), and never on a stale/cached response.
- **ProxyGuard Assistant**: a floating, rule-based recommendation panel (no external AI) that summarizes session health (success rate, attention level, main concern, items needing review) and surfaces prioritized, actionable recommendation cards — each with a plain-language explanation and a button that jumps straight to the matching filtered rows or the next unreviewed attempt.
- **CSV export** of the currently filtered view, and flagged-row highlighting reusing `src/pattern_flagger.py` (no duplicated detection logic).
- Modern, separated HTML/CSS/JavaScript architecture (`templates/`, `static/css/dashboard.css`, `static/js/dashboard.js`) following a single monochromatic design system shared with `checkin_app/` (see `docs/ui-references/DESIGN.md`).

## Tech Stack
- Python 3.10+
- OpenCV for webcam capture and face detection
- face_recognition with dlib for face encoding and matching
- MediaPipe Face Mesh for blink detection and head pose tracking
- SpeechRecognition and PyAudio for the (currently unused) voice challenge
- Google Speech Recognition API for speech-to-text
- Pandas/CSV for attendance and review logging
- Flask for both the lecturer dashboard (`dashboard/`) and the student check-in web app (`checkin_app/`)
- Vanilla JavaScript and hand-written CSS for both Flask apps' front ends (no frontend framework, no build step)

## Current Scope
The prototype is a fully browser-based attendance flow. Students check in through `checkin_app/` (session picker → live MJPEG check-in, driven by the shared `CheckinSession` engine); a legacy desktop OpenCV entry point in `src/main.py` still exists and drives the same engine for local testing. Lecturers review attendance through `dashboard/`, a separate read-only Flask app with analytics, filtering, a review workflow, and the rule-based ProxyGuard Assistant. The voice challenge remains built but unused (see [[decisions]] Decision 7). Testing and refinement (Step 8) is ongoing — see [[roadmap]] and [[testing]].

## Related Documentation
- [[roadmap]]
- [[architecture]]
- [[decisions]]
- [[testing]]
- [[bugs]]
- [[report]]
- [[CLAUDE]]
