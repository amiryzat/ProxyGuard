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
- Log attendance results with success or failure reasons.
- Flag suspicious attendance patterns for lecturer review.

A randomized voice challenge and a mid-challenge identity re-verification were also built but have since been **removed from the live check-in flow** to prioritize reliability at the current proposal stage; the voice module (`src/voice_challenge.py`) is retained for possible reintegration. See [[decisions]] (Decision 7).

Session identity has since been extended (Phase 1): rather than a bare timestamp, `session_id` now also carries the selected class subject and week number, since a single room/date can host multiple different subjects. See [[decisions]] (Decision 8). A Phase 2a student-facing web setup page (`checkin_app/`) now lets a lecturer build one of these session IDs from a browser instead of the terminal; it does not yet perform any check-in itself. See [[decisions]] (Decision 9).

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
The current prototype focuses on a local webcam-based attendance flow. It includes face recognition, liveness detection (blink + head movement), attendance logging, duplicate detection, and suspicious pattern flagging. The voice challenge is built as a module but is not currently part of the live flow (see [[decisions]] Decision 7). The lecturer dashboard is built (`dashboard/`). A student-facing check-in web app (`checkin_app/`) is being built in phases: Phase 2a (setup page only — pick class + week, generate and display `session_id`) is done; Phase 2b (camera streaming and the live check-in/liveness flow inside that web app) is not yet built. Only testing and refinement (plus the remaining check-in web app phase) remain.

## Related Documentation
- [[roadmap]]
- [[architecture]]
- [[decisions]]
- [[testing]]
- [[bugs]]
- [[CLAUDE]]