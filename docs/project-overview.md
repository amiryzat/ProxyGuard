# Project Overview

## Purpose
ProxyGuard is a liveness-aware face recognition attendance system for detecting proxy attendance. It is built for a CSC649 Special Topics in Computer Science final project proposal at UiTM.

## Problem
Normal face recognition attendance systems can be fooled when a student checks in for an absent classmate using a printed photo, video, replayed face data, or another spoofing method. ProxyGuard reduces this weakness by combining face recognition with multiple liveness checks to verify that the person checking in is physically present and actively responding.

## Target Users
- Lecturers who need to verify student attendance.
- Students who check in through the attendance system.
- Academic evaluators reviewing the project proposal and prototype.

## Objectives
- Recognize registered students using stored frontal face reference images.
- Detect liveness through blink detection.
- Detect liveness through randomized head movement.
- Enforce that exactly one person is present during an active check-in, and that the recognized identity stays bound to the same continuous face throughout the challenge — preventing a recognized identity from silently transferring to a swapped-in face or photo.
- Log attendance results with success or failure reasons, correctly attributing failed attempts to the recognized student when one was identified.
- Flag suspicious attendance patterns for lecturer review.

A randomized voice challenge and a mid-challenge identity re-verification were also built but have since been **removed from the live check-in flow** to prioritize reliability at the current proposal stage; the voice module (`src/voice_challenge.py`) is retained for possible reintegration. See [[decisions]] (Decision 7).

Session identity has since been extended (Phase 1): rather than a bare timestamp, `session_id` now also carries the selected class subject and week number, since a single room/date can host multiple different subjects. See [[decisions]] (Decision 8). A student-facing web app (`checkin_app/`) lets a lecturer build one of these session IDs from a browser (Phase 2a) and now also runs the full live check-in flow there, streaming the webcam into the browser (Phase 2b). See [[decisions]] (Decision 9).

Two anti-proxy safeguards were added after live testing surfaced real bypasses: single-person enforcement during the active challenge (Decision 10), and an identity-liveness continuity guard that requires the recognized face to remain the same one throughout the challenge (Decision 11) — see [[bugs]] Bug 5 and Bug 9.

## Tech Stack
- Python 3.10+
- OpenCV for webcam capture and face detection
- face_recognition with dlib for face encoding and matching
- MediaPipe Face Mesh for blink detection and head pose tracking
- SpeechRecognition and PyAudio for the voice challenge
- Google Speech Recognition API for speech-to-text
- Pandas and CSV for attendance logging
- Flask for the lecturer-facing dashboard (`dashboard/`, built)

## Current Scope
The current prototype focuses on a webcam-based attendance flow, available through two interfaces that share one underlying check-in engine (`CheckinSession`): a desktop OpenCV app (`src/main.py`) and a browser-based app (`checkin_app/`, streaming the webcam as MJPEG). Both include face recognition, liveness detection (blink + head movement), single-person enforcement, the identity-liveness continuity guard, attendance logging with correct name attribution on failed attempts, duplicate detection, and per-outcome verification snapshots. The voice challenge is built as a module but is not currently part of the live flow (see [[decisions]] Decision 7). The lecturer dashboard (`dashboard/`) shows the attendance log split into Present/Attempts tabs, with a reason filter, flagged-row highlighting, per-tab summaries, and inline verification-snapshot thumbnails for each row. Only testing and refinement (Step 8) remain of the originally planned steps.

## Related Documentation
- [[roadmap]]
- [[architecture]]
- [[decisions]]
- [[testing]]
- [[bugs]]
- [[CLAUDE]]