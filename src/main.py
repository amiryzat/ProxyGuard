# src/main.py
# Combines face recognition with liveness detection (head movement plus
# blink) to prevent proxy attendance. A check in only counts as valid if
# the face is recognized and the person passes the head movement challenge
# with a real blink.
#
# A voice challenge (src/voice_challenge.py) was previously part of this
# flow but has been removed from the live loop to prioritize flow
# reliability at the current proposal stage. The module is kept intact so
# it can be reintegrated later.

import cv2
import mediapipe as mp
import random
import time
import os
from datetime import datetime

from face_recognizer import load_known_faces, recognize_face, locate_faces
from liveness_check import (
    BlinkDetector,
    HeadMovementChallenge,
    get_head_pose,
    mp_face_mesh
)
from attendance_logger import log_attendance
from class_config import CLASS_SUBJECTS, WEEK_MIN, WEEK_MAX, build_session_id

random.seed(os.urandom(8))

LIVENESS_MESSAGE_SECONDS = 2

# Shown when more than one face is detected during an active check-in. The
# liveness challenge only makes sense for a single person: mediapipe Face Mesh
# tracks just one face for blink/head-pose, so a second face in frame could let
# one person perform the challenge while another's (e.g. a registered student's)
# face is also present. While multiple faces are detected the challenge is
# paused rather than allowed to progress or lock. See docs/decisions.md
# (Decision 10).
MULTI_FACE_MESSAGE = "Only one person allowed in frame, please ensure you are alone during check-in"
# Wrapped for the on-frame overlay so it stays legible on narrow webcam frames;
# the full single-line message above is what checkin_app shows as its banner.
MULTI_FACE_MESSAGE_LINES = [
    "Only one person allowed in frame,",
    "please ensure you are alone during check-in",
]

# Snapshots of every terminal check-in outcome are written here as a manual
# verification safety net for lecturers. Resolved relative to this file (like
# the other modules) so it works regardless of the working directory.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_DIR = os.path.join(SCRIPT_DIR, "..", "logs", "snapshots")


def build_snapshot_filename(session_id, name, reason):
    # Combines session_id + identity + outcome reason + an HHMMSS timestamp so
    # each terminal outcome gets a unique, human-scannable file. The timestamp
    # keeps multiple check-ins within one session from overwriting each other.
    def slug(text):
        return "".join(c if c.isalnum() else "_" for c in text).strip("_").lower() or "unknown"

    timestamp = datetime.now().strftime("%H%M%S")
    return f"{session_id}_{slug(name)}_{slug(reason)}_{timestamp}.jpg"


def prompt_session_setup():
    """
    Ask the lecturer, in the terminal, to pick a class subject (by number,
    from class_config.CLASS_SUBJECTS) and a week number before the camera
    loop starts. Returns (subject, week_number).

    This is deliberately a simple terminal prompt for now -- a proper
    web-based setup screen is a separate planned phase. Both inputs are
    re-prompted until valid so an operator typo can't start a session with a
    bad class/week.
    """
    print("\n=== ProxyGuard session setup ===")
    print("Select a class subject:")
    for index, subject in enumerate(CLASS_SUBJECTS, start=1):
        print(f"  {index}. {subject}")

    while True:
        choice = input(f"Enter class number (1-{len(CLASS_SUBJECTS)}): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(CLASS_SUBJECTS):
            subject = CLASS_SUBJECTS[int(choice) - 1]
            break
        print("  Invalid choice, please try again.")

    while True:
        week_input = input(f"Enter week number ({WEEK_MIN}-{WEEK_MAX}): ").strip()
        if week_input.isdigit() and WEEK_MIN <= int(week_input) <= WEEK_MAX:
            week_number = int(week_input)
            break
        print(f"  Invalid week, please enter a number from {WEEK_MIN} to {WEEK_MAX}.")

    return subject, week_number


class CheckinSession:
    """
    One check-in station: face recognition + liveness (blink + head movement)
    driving the flow_phase state machine, plus terminal-outcome logging and
    snapshotting. Extracted from the old inline main loop so both the desktop
    entry point (below) and the student web app (checkin_app/) share the exact
    same detection, liveness, logging, and snapshot behavior -- the web app
    only swaps how frames are delivered (webcam -> MJPEG) and displayed
    (OpenCV window -> browser <img>), never the underlying checks.

        session = CheckinSession(session_id, encodings, names)
        annotated = session.process_frame(raw_bgr_frame)   # annotated BGR out
        if session.can_reset(): session.reset()            # 'n' / "new check-in"
        session.close()
    """

    def __init__(self, session_id, known_encodings, known_names):
        self.session_id = session_id
        self.known_encodings = known_encodings
        self.known_names = known_names

        # One FaceMesh per session (was a `with` block wrapping the old loop).
        # close() releases it. Same parameters as before.
        self.face_mesh = mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self.blink_detector = BlinkDetector()
        self.challenge = HeadMovementChallenge()

        # Frame cadence + last-result state persists across attempts, exactly
        # like the old loop where these lived outside the 'n' reset.
        self.frame_count = 0
        self.process_every_n_frames = 3
        self.last_names = []
        self.last_face_locations = []

        # Mirrors the primary on-screen message so a browser can show the same
        # text outside the video; the desktop just relies on the overlay.
        self.banner = None

        self._start_attempt()

    def _start_attempt(self):
        # Per-attempt state -- exactly what the old 'n' reset re-initialized.
        self.challenge.start()
        self.blink_count_at_challenge_start = self.blink_detector.blink_count
        self.identified_name = None
        # last_known_name mirrors identified_name's single-bad-frame protection,
        # but for the on-screen bounding box LABEL specifically. It only updates
        # when recognize_face returns a real (non-"Unknown") name, so the label
        # never flashes to "Unknown" on a stray misdetected frame -- notably the
        # last processed frame right before the challenge locks. identified_name
        # protects the logic path (who gets confirmed); this protects what the
        # operator sees.
        self.last_known_name = None
        self.confirmed_name = None
        self.check_locked = False
        self.locked_status = None

        # flow_phase drives what's on screen after the head-movement/blink
        # challenge locks in: liveness_success -> confirmed, or
        # liveness_success -> not_recognized, or liveness_failed. confirmed /
        # not_recognized / liveness_failed are terminal (wait for a reset);
        # liveness_success advances on its own timer.
        #
        # identity_mismatch is retained as a terminal state but is currently
        # unreachable: its only trigger was the identity re-verification during
        # the (now removed) voice listening phase. It is kept so it can be
        # rewired if the voice challenge is reintegrated later.
        self.flow_phase = None
        self.phase_start = None
        self.outcome_logged = False

    def reset(self):
        """Start a fresh attempt (desktop 'n' / web 'New check-in')."""
        self._start_attempt()

    def can_reset(self):
        """True once the current attempt reached a terminal outcome."""
        return self.check_locked and self.flow_phase in (
            "confirmed", "not_recognized", "liveness_failed", "identity_mismatch"
        )

    def close(self):
        self.face_mesh.close()

    def process_frame(self, frame):
        """
        Run one frame through recognition + liveness + the flow_phase state
        machine, draw all overlays, advance terminal logging/snapshotting once
        per attempt, and return the annotated BGR frame.
        """
        frame = cv2.flip(frame, 1)
        # Keep an un-annotated copy for the terminal-outcome snapshot below,
        # taken before any boxes/text/challenge number are drawn onto `frame`
        # -- a lecturer reviewing the snapshot needs the face unobstructed.
        clean_frame = frame.copy()
        frame_height, frame_width = frame.shape[:2]

        self.frame_count += 1
        if self.frame_count % self.process_every_n_frames == 0:
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)

            if self.check_locked:
                # Identity is already established by the time the challenge
                # locks in, so just track the face's position for the on-screen
                # box (cheaper locate_faces, no re-encoding). The full
                # recognize_face re-verification that used to run here existed
                # only to catch a proxy swap during the voice listening phase,
                # which no longer exists.
                face_locations = locate_faces(small_frame)
                names = [self.confirmed_name or "Unknown"] * len(face_locations)
            else:
                names, face_locations = recognize_face(
                    small_frame, self.known_encodings, self.known_names
                )

            scaled_locations = []
            for (top, right, bottom, left) in face_locations:
                scaled_locations.append((top * 4, right * 4, bottom * 4, left * 4))

            self.last_names = names
            self.last_face_locations = scaled_locations

            # Only adopt an identity from a frame with exactly one face. In a
            # multi-face frame last_names[0] is just whichever face sorted first,
            # which must not become the to-be-confirmed identity -- and the
            # challenge can't lock while multiple faces are present anyway (see
            # the single-person enforcement below).
            if not self.check_locked and len(self.last_face_locations) == 1 \
                    and self.last_names and self.last_names[0] != "Unknown":
                self.identified_name = self.last_names[0]

            # Protect the drawn box label the same way (see last_known_name in
            # _start_attempt), and only from a single-face frame -- last_known_name
            # is a single-identity guard and must never be set from one face out
            # of several (that is exactly what made every box show the same name).
            # Unlike identified_name this also updates in the locked phase: on a
            # pass, the locked branch feeds confirmed_name through as the name so
            # the label keeps showing it; on a fail, the locked branch feeds
            # "Unknown", which is ignored here so the label holds the last
            # confident identity instead of flipping to "Unknown".
            if len(self.last_face_locations) == 1 \
                    and self.last_names and self.last_names[0] != "Unknown":
                self.last_known_name = self.last_names[0]

        num_faces = len(self.last_face_locations)
        for (top, right, bottom, left), name in zip(self.last_face_locations, self.last_names):
            cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
            if not self.check_locked:
                if num_faces > 1:
                    # Multiple faces: label each box with its OWN recognition
                    # result. last_known_name is a single-identity anti-flicker
                    # guard (Bug 1) and must not be painted onto every box, or a
                    # second person would wrongly show the registered student's
                    # name. See docs/bugs.md (Bug 5, Issue A).
                    display_name = name
                else:
                    # Single face: keep the last_known_name anti-flicker guard.
                    # It labels with the last confidently recognized identity, not
                    # the raw per-frame `name`, so a single bad "Unknown" frame
                    # (notably the one right before the challenge locks) can't
                    # flash the label to "Unknown". Falls back to the raw name
                    # only before any confident match has been made this attempt.
                    display_name = self.last_known_name or name
                cv2.putText(frame, display_name, (left, top - 10), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 2)
            # Once check_locked is true (liveness_success through the terminal
            # states, which wait for a reset), draw NO name label -- only the
            # tracking rectangle. locate_faces keeps the box following whoever
            # is in frame, but that may no longer be the student who just
            # checked in (they can step away and someone else sits down before
            # 'n' / "New check-in" is pressed). last_known_name is deliberately
            # left uncleared for its anti-flicker role and for the snapshot
            # filename, so we gate the *display* on check_locked here rather
            # than clearing the variable. See docs/bugs.md (Bug 3).

        direction = "center"
        status = "waiting"

        if not self.check_locked:
            # Single-person enforcement: the liveness challenge can only be
            # trusted with exactly one face in frame (mediapipe tracks one face
            # for blink/head-pose, so a second person could perform the challenge
            # alongside a registered face). While more than one face is detected,
            # pause -- don't run mediapipe, advance, time out, or lock the
            # challenge -- and show a clear warning. See docs/decisions.md
            # (Decision 10) and docs/bugs.md (Bug 5, Issue B).
            if num_faces > 1:
                # Pin the countdown to full time so the multi-face interruption
                # can't cause a timeout failure, and discard any partial match,
                # without re-randomizing the target (the same instruction resumes
                # once the extra face leaves).
                self.challenge.start_time = time.time()
                self.challenge.result = None

                self.banner = MULTI_FACE_MESSAGE
                for i, line in enumerate(MULTI_FACE_MESSAGE_LINES):
                    line_size = cv2.getTextSize(line, cv2.FONT_HERSHEY_DUPLEX, 0.7, 2)[0]
                    line_x = (frame_width - line_size[0]) // 2
                    line_y = frame_height - 110 + i * 35
                    cv2.putText(frame, line, (line_x, line_y), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 165, 255), 2)
            else:
                small_frame_mesh = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
                rgb_frame = cv2.cvtColor(small_frame_mesh, cv2.COLOR_BGR2RGB)
                results = self.face_mesh.process(rgb_frame)

                if results.multi_face_landmarks:
                    landmarks = results.multi_face_landmarks[0].landmark
                    ear, blinked, total_blinks = self.blink_detector.update(landmarks, frame_width, frame_height)
                    direction, h_offset, v_offset = get_head_pose(landmarks, frame_width, frame_height)

                    cv2.putText(frame, f"Blinks: {total_blinks}", (30, 40), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 2)

                    raw_status = self.challenge.check(direction)

                    if raw_status == "passed":
                        has_blinked = self.blink_detector.blink_count > self.blink_count_at_challenge_start
                        if has_blinked:
                            status = "passed"
                        else:
                            elapsed = time.time() - self.challenge.start_time
                            if elapsed > self.challenge.duration_seconds:
                                status = "failed"
                            else:
                                status = "waiting"
                                self.challenge.result = None
                    else:
                        status = raw_status

                remaining = self.challenge.time_remaining()
                instruction_text = f"Turn head {self.challenge.target_direction.upper()}  ({remaining:.1f}s)"
                self.banner = instruction_text
                text_size = cv2.getTextSize(instruction_text, cv2.FONT_HERSHEY_DUPLEX, 0.9, 2)[0]
                text_x = (frame_width - text_size[0]) // 2
                cv2.putText(frame, instruction_text, (text_x, frame_height - 80), cv2.FONT_HERSHEY_DUPLEX, 0.9, (255, 255, 255), 2)

                if status == "waiting" and direction != "center" and direction != self.challenge.target_direction:
                    wrong_msg = f"That is {direction.upper()}, please turn {self.challenge.target_direction.upper()}"
                    wrong_size = cv2.getTextSize(wrong_msg, cv2.FONT_HERSHEY_DUPLEX, 0.7, 2)[0]
                    wrong_x = (frame_width - wrong_size[0]) // 2
                    cv2.putText(frame, wrong_msg, (wrong_x, frame_height - 110), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 165, 255), 2)

                if status == "passed":
                    self.check_locked = True
                    self.locked_status = "passed"
                    self.flow_phase = "liveness_success"
                    self.phase_start = time.time()
                    if self.identified_name and self.identified_name != "Unknown":
                        self.confirmed_name = self.identified_name
                    else:
                        self.confirmed_name = None
                elif status == "failed":
                    self.check_locked = True
                    self.locked_status = "failed"
                    self.flow_phase = "liveness_failed"
                    self.confirmed_name = None

        if self.check_locked:
            bottom_msg = None
            bottom_color = (255, 255, 255)
            show_restart_hint = False

            if self.flow_phase == "liveness_success":
                bottom_msg = "LIVENESS DETECTION SUCCESSFUL"
                bottom_color = (0, 255, 0)
                if time.time() - self.phase_start >= LIVENESS_MESSAGE_SECONDS:
                    if self.confirmed_name:
                        self.flow_phase = "confirmed"
                    else:
                        self.flow_phase = "not_recognized"

            elif self.flow_phase == "confirmed":
                bottom_msg = f"ATTENDANCE CONFIRMED: {self.confirmed_name}"
                bottom_color = (0, 255, 0)
                show_restart_hint = True

            elif self.flow_phase == "not_recognized":
                bottom_msg = "LIVENESS DETECTION SUCCESSFUL, BUT FACE NOT RECOGNIZED"
                bottom_color = (0, 165, 255)
                show_restart_hint = True

            elif self.flow_phase == "liveness_failed":
                bottom_msg = "LIVENESS TEST FAILED"
                bottom_color = (0, 0, 255)
                show_restart_hint = True

            elif self.flow_phase == "identity_mismatch":
                bottom_msg = "DIFFERENT PERSON DETECTED, POSSIBLE PROXY ATTEMPT - TEST FAILED"
                bottom_color = (0, 0, 255)
                show_restart_hint = True

            self.banner = bottom_msg

            if not self.outcome_logged and self.flow_phase in ("confirmed", "not_recognized", "liveness_failed", "identity_mismatch"):
                if self.flow_phase == "confirmed":
                    log_result, log_reason = "success", "confirmed"
                elif self.flow_phase == "not_recognized":
                    log_result, log_reason = "failed", "face not recognized"
                elif self.flow_phase == "liveness_failed":
                    log_result, log_reason = "failed", "liveness timeout"
                else:  # identity_mismatch (retained but currently unreachable)
                    log_result, log_reason = "failed", "identity mismatch"

                # Use the reason actually written to the CSV, not log_reason.
                # log_attendance downgrades a duplicate "success"/"confirmed" to
                # "failed"/"duplicate check-in this session"; if we named the
                # snapshot from the pre-downgrade log_reason it would say
                # "confirmed" for an attempt the CSV correctly recorded as a
                # duplicate failure. Naming from the returned reason keeps the
                # snapshot filename consistent with the CSV row for that attempt.
                _, written_reason = log_attendance(
                    self.confirmed_name or "Unknown", log_result, log_reason, self.session_id
                )

                # Save a snapshot for every terminal outcome -- successes
                # included, not just failures -- since a check-in can pass the
                # liveness checks and still be a photo of someone else held up
                # to the camera; the saved image lets a lecturer verify the
                # actual face after the fact. Uses the pre-overlay clean_frame.
                os.makedirs(SNAPSHOT_DIR, exist_ok=True)
                # Name the snapshot with last_known_name (the same bad-frame
                # protected identity used for the on-screen box label), not
                # confirmed_name. confirmed_name is None on any failed outcome,
                # so a registered student who was recognized throughout a
                # *failed* liveness attempt would otherwise be saved as
                # "..._unknown_liveness_timeout_...", contradicting the real
                # name shown on screen the whole time. last_known_name holds the
                # last confidently recognized identity regardless of pass/fail,
                # and is None only if no confident match was ever made this
                # attempt -- in which case we still fall back to "unknown". (The
                # attendance log itself is left keyed on confirmed_name; only
                # the snapshot filename changes here.)
                snapshot_path = os.path.join(
                    SNAPSHOT_DIR,
                    build_snapshot_filename(self.session_id, self.last_known_name or "unknown", written_reason),
                )
                cv2.imwrite(snapshot_path, clean_frame)

                self.outcome_logged = True

            if bottom_msg:
                msg_size = cv2.getTextSize(bottom_msg, cv2.FONT_HERSHEY_DUPLEX, 0.9, 2)[0]
                msg_x = (frame_width - msg_size[0]) // 2
                cv2.putText(frame, bottom_msg, (msg_x, frame_height - 40), cv2.FONT_HERSHEY_DUPLEX, 0.9, bottom_color, 2)

            if show_restart_hint:
                restart_msg = "Press 'n' to run a new check"
                restart_size = cv2.getTextSize(restart_msg, cv2.FONT_HERSHEY_DUPLEX, 0.6, 1)[0]
                restart_x = (frame_width - restart_size[0]) // 2
                cv2.putText(frame, restart_msg, (restart_x, frame_height - 10), cv2.FONT_HERSHEY_DUPLEX, 0.6, (200, 200, 200), 1)

        return frame


if __name__ == "__main__":
    # Generated once per run (not per check-in), so restarting main.py
    # naturally starts a fresh session -- duplicate check-in detection in
    # attendance_logger.py is scoped to this session_id rather than a
    # calendar date, since one room/date can host multiple class sessions.
    #
    # session_id now also carries the selected class subject and week number
    # (not just a timestamp), since one room/date can host several *different*
    # subjects and week-based grouping is more useful to lecturers than a raw
    # timestamp. It stays an opaque string to every other module.
    subject, week_number = prompt_session_setup()
    session_id = build_session_id(subject, week_number)
    print(f"Session: {session_id}")

    known_encodings, known_names = load_known_faces()
    print(f"Loaded {len(known_names)} face encodings for known people")

    cap = cv2.VideoCapture(0)
    # All per-frame recognition/liveness/logging/snapshot logic now lives in
    # CheckinSession (shared with the student web app in checkin_app/). This
    # loop is just the desktop driver: read -> process -> show, plus the
    # 'n' reset and 'q' quit keys the OpenCV window needs.
    session = CheckinSession(session_id, known_encodings, known_names)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        key = cv2.waitKey(1) & 0xFF
        annotated = session.process_frame(frame)
        cv2.imshow("ProxyGuard", annotated)

        if session.can_reset() and key == ord('n'):
            session.reset()

        if key == ord('q'):
            break

    session.close()
    cap.release()
    cv2.destroyAllWindows()