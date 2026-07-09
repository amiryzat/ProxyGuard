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

# Identity-liveness continuity guard (anti-proxy face swap). A recognized
# identity must stay bound to the SAME physical face for the rest of the
# active challenge -- otherwise a proxy could get recognized once, then swap
# in an unregistered face (or a photo/phone screen) and still pass the
# challenge under the first identity. See CheckinSession._update_identity_continuity.
#
# This prioritizes SPATIAL continuity over per-frame recognition certainty:
# the challenge itself requires head movement, and face_recognition routinely
# returns "Unknown" while genuinely off-angle (mid-turn) -- that must not, by
# itself, break continuity, or the guard would punish the exact motion the
# challenge asks for. Only three things break continuity:
#   1. The face box jumps too far from its last tracked position (below).
#   2. A DIFFERENT real registered name is recognized at that position
#      (tolerated for one stray check, see DIFFERENT_NAME_TOLERANCE).
#   3. No reconfirming match (same name) has occurred for IDENTITY_HOLD_SECONDS
#      -- covers both "no face" and "face present but stuck on Unknown too
#      long" with one timer, rather than a per-frame mismatch count.

# Max allowed face-center shift between recognition checks, as a fraction of
# frame width, before two face boxes are treated as different physical faces.
# Deliberately simple (center-distance, not IoU/real tracking) -- this is an
# academic prototype, not production biometric tracking.
FACE_JUMP_MAX_FRACTION = 0.35

# How long (wall-clock seconds) a spatially-continuous single face can go
# without RE-matching the active identity's name before continuity is
# considered broken. Long enough to cover a deliberate, several-second
# off-angle hold during the 10s head-movement challenge (recognition
# legitimately weakens off-angle); short enough that a face swapped in at the
# same position can't ride the original identity for a whole challenge
# window. Tuned generously toward usability -- see docs/bugs.md for the
# accepted tradeoff.
IDENTITY_HOLD_SECONDS = 4.0

# A different REAL registered name (not "Unknown") appearing at the tracked
# position is a strong, unambiguous signal -- tolerated for only this many
# consecutive checks (one stray misrecognition) before clearing, unlike the
# generous IDENTITY_HOLD_SECONDS given to plain "Unknown".
DIFFERENT_NAME_TOLERANCE = 1

CONTINUITY_WARNING_SECONDS = 2
CONTINUITY_BROKEN_MESSAGE = "Face changed or lost, please keep the same face in frame"


def _face_box_close(box_a, box_b, frame_width, max_fraction=FACE_JUMP_MAX_FRACTION):
    """
    Conservative face-continuity check: are two (top, right, bottom, left)
    face boxes close enough to be considered the same physical face across
    consecutive recognition checks? Compares box centers, normalized by frame
    width so the threshold scales with resolution.
    """
    if box_a is None or box_b is None:
        return False
    top_a, right_a, bottom_a, left_a = box_a
    top_b, right_b, bottom_b, left_b = box_b
    center_a = ((left_a + right_a) / 2.0, (top_a + bottom_a) / 2.0)
    center_b = ((left_b + right_b) / 2.0, (top_b + bottom_b) / 2.0)
    distance = ((center_a[0] - center_b[0]) ** 2 + (center_a[1] - center_b[1]) ** 2) ** 0.5
    return distance <= max_fraction * frame_width

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

    def __init__(self, session_id, known_encodings, known_names,
                 restart_hint="Press 'n' to run a new check"):
        self.session_id = session_id
        self.known_encodings = known_encodings
        self.known_names = known_names
        # On-frame hint shown at a terminal outcome telling the operator how to
        # start the next check. Defaults to the desktop's 'n' key; the web app
        # (checkin_app) passes None because it uses the "New check-in" button
        # instead, so drawing "Press 'n'..." there would be misleading.
        self.restart_hint = restart_hint

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

        # Identity-liveness continuity guard state (see
        # _update_identity_continuity). active_face_box is the last tracked
        # position of the bound face (updated on every spatially-close single
        # face, even a currently-"Unknown" one, so natural head-turn drift
        # doesn't look like a jump later). last_confirmed_time is the wall
        # clock time of the last check where the name actually matched
        # identified_name; different_name_streak counts consecutive checks
        # where a DIFFERENT real name was seen; continuity_warning_until is a
        # short on-screen warning window shown right after continuity breaks.
        # pending_reverify is set on any multi-face frame and forces the next
        # single-face check to be a confident match, bypassing the usual
        # "Unknown" grace period (see _update_identity_continuity).
        self.active_face_box = None
        self.last_confirmed_time = None
        self.different_name_streak = 0
        self.pending_reverify = False
        self.continuity_warning_until = None

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

    def _clear_active_identity(self):
        """
        Continuity broken (spatial jump, a different real identity took over,
        or no reconfirming match for too long) -- clear identity state and
        restart the challenge from scratch (fresh direction + fresh timer),
        so it must be re-earned by a continuously present, matching face
        rather than letting a swapped-in face finish it under the old one.
        """
        self.identified_name = None
        self.last_known_name = None
        self.active_face_box = None
        self.last_confirmed_time = None
        self.different_name_streak = 0
        self.pending_reverify = False
        self.challenge.start()
        self.continuity_warning_until = time.time() + CONTINUITY_WARNING_SECONDS

    def _update_identity_continuity(self, names, face_locations, frame_width):
        """
        Anti-proxy-swap guard, run pre-lock on every recognition check (every
        3rd raw frame). Recognizing a student once is not enough to bind their
        identity to the whole attempt -- but the guard must not punish the
        head movement the challenge itself requires, since recognition
        legitimately weakens (often to "Unknown") while genuinely off-angle.
        See docs/bugs.md.

        Spatial continuity is prioritized over per-frame recognition
        certainty for a genuinely continuous single face: once identified_name
        is set, continuity breaks on --
          1. The single detected face's box jumping too far from where it was
             last seen (see _face_box_close) -> broken immediately.
          2. A DIFFERENT real registered name recognized at that position ->
             tolerated for one stray check (DIFFERENT_NAME_TOLERANCE), then
             broken.
          3. No check RE-matching the active name for more than
             IDENTITY_HOLD_SECONDS (covers both "no face at all" and "face
             present but stuck on Unknown too long") -> broken.
        A plain "Unknown" result on its own does none of these -- it neither
        jumps the box nor introduces a different name -- so a multi-second
        off-angle hold during the head-turn/blink challenge is tolerated as
        long as the face box keeps tracking the same position.

        BUT a box position alone cannot tell a genuine off-angle turn apart
        from a phone/photo held directly in front of (occluding) the same
        spot -- both look like "single face, Unknown, same position". The
        one fact that *does* distinguish them: a real head turn is a single
        face the whole time, while a hand-off/occlusion attack (as reported)
        passes through a multi-face frame first (the phone held beside the
        real face) before the swap. So once a multi-face frame is seen,
        `pending_reverify` is set, and the very next single-face check must
        be a CONFIDENT match to the active identity to keep it -- an "Unknown"
        or different name right after a multi-face moment is treated as the
        swap it almost certainly is, not given the usual grace period.
        """
        if len(face_locations) > 1:
            # Multi-face frames are handled by the separate pause in
            # process_frame (Decision 10) -- don't touch identity/position
            # here, but flag that whatever single face reappears next must be
            # freshly reconfirmed before it can keep using this identity.
            self.pending_reverify = True
            return

        if self.identified_name is None:
            # No identity locked yet this attempt: any confident single-face
            # match starts tracking it (same as the original behavior).
            if len(face_locations) == 1 and names[0] != "Unknown":
                self.identified_name = names[0]
                self.last_known_name = names[0]
                self.active_face_box = face_locations[0]
                self.last_confirmed_time = time.time()
                self.different_name_streak = 0
                self.pending_reverify = False
            return

        if len(face_locations) == 1:
            name = names[0]
            box = face_locations[0]

            if self.active_face_box is not None and not _face_box_close(self.active_face_box, box, frame_width):
                self._clear_active_identity()
                return

            if self.pending_reverify:
                # Coming straight out of a multi-face frame: only a confident
                # match to the SAME identity re-earns trust. "Unknown" or a
                # different name here is exactly the occlusion/hand-off
                # pattern of the reported bypass -- clear immediately, no
                # grace period, even though the box position didn't jump.
                if name == self.identified_name:
                    self.pending_reverify = False
                else:
                    self._clear_active_identity()
                    return

            if name != "Unknown" and name != self.identified_name:
                self.different_name_streak += 1
                if self.different_name_streak > DIFFERENT_NAME_TOLERANCE:
                    self._clear_active_identity()
                return

            # Same name, or "Unknown" (expected while genuinely off-angle
            # mid-turn, and not immediately following a multi-face moment):
            # keep tracking position so gradual head movement doesn't itself
            # look like a jump on a later check.
            self.active_face_box = box
            self.different_name_streak = 0
            if name == self.identified_name:
                self.last_known_name = name
                self.last_confirmed_time = time.time()
            # else "Unknown": don't refresh last_confirmed_time -- the
            # hold-timeout below still applies if this drags on too long.

        # 0 faces (person fully out of frame) also doesn't refresh
        # last_confirmed_time, so this timeout covers both "disappeared" and
        # "present but unrecognized too long" with one grace window.
        if time.time() - self.last_confirmed_time > IDENTITY_HOLD_SECONDS:
            self._clear_active_identity()

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

            if not self.check_locked:
                # Identity-liveness continuity guard (anti-proxy face swap):
                # identified_name/last_known_name only keep counting for the
                # SAME confidently recognized face, not just any non-"Unknown"
                # name seen at any point this attempt. See
                # _update_identity_continuity and docs/bugs.md.
                self._update_identity_continuity(self.last_names, self.last_face_locations, frame_width)
            # Once locked, last_known_name is deliberately left as-is (its
            # anti-flicker/snapshot-naming role, see docs/bugs.md Bug 1/2) --
            # only the pre-lock continuity guard above can change it.

        num_faces = len(self.last_face_locations)
        for (top, right, bottom, left), name in zip(self.last_face_locations, self.last_names):
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
            else:
                # Once check_locked is true (liveness_success through the terminal
                # states, which wait for a reset), draw NO name label -- only the
                # tracking rectangle. locate_faces keeps the box following whoever
                # is in frame, but that may no longer be the student who just
                # checked in (they can step away and someone else sits down before
                # 'n' / "New check-in" is pressed). last_known_name is deliberately
                # left uncleared for its anti-flicker role and for the snapshot
                # filename, so we gate the *display* on check_locked here rather
                # than clearing the variable. See docs/bugs.md (Bug 3). The box
                # color still reflects this box's tracked identity.
                display_name = name

            # Red box (and matching label) for an unrecognized face, green for a
            # recognized one, so an "Unknown" stands out at a glance. BGR tuples.
            box_color = (0, 0, 255) if (not display_name or display_name == "Unknown") else (0, 255, 0)

            cv2.rectangle(frame, (left, top), (right, bottom), box_color, 2)
            if not self.check_locked:
                cv2.putText(frame, display_name, (left, top - 10), cv2.FONT_HERSHEY_DUPLEX, 0.7, box_color, 2)

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

                # Brief on-frame/status warning right after the continuity
                # guard clears an identity (see _update_identity_continuity).
                # Purely cosmetic -- the challenge was already reset the
                # moment continuity broke; this just tells the operator why.
                if self.continuity_warning_until and time.time() < self.continuity_warning_until:
                    self.banner = CONTINUITY_BROKEN_MESSAGE
                    warn_size = cv2.getTextSize(CONTINUITY_BROKEN_MESSAGE, cv2.FONT_HERSHEY_DUPLEX, 0.7, 2)[0]
                    warn_x = (frame_width - warn_size[0]) // 2
                    cv2.putText(frame, CONTINUITY_BROKEN_MESSAGE, (warn_x, frame_height - 140), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2)

                if status == "passed":
                    self.check_locked = True
                    self.locked_status = "passed"
                    self.flow_phase = "liveness_success"
                    self.phase_start = time.time()
                    # identified_name is only ever set/kept by
                    # _update_identity_continuity, which clears it immediately
                    # on a spatial jump or a different real identity, and
                    # within IDENTITY_HOLD_SECONDS of no reconfirming match --
                    # so if it's still set here, continuity holds by
                    # construction; no extra check needed. See
                    # _update_identity_continuity / docs/bugs.md.
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

                # Log identity: confirmed_name on a pass, but confirmed_name is
                # always None on a FAILED outcome (see the "passed"/"failed"
                # branches above), even when the person was confidently
                # recognized earlier in the same attempt -- e.g. a registered
                # student who fails the liveness challenge. Falling back to
                # last_known_name (the same bad-frame-protected identity used
                # for the on-screen label and the snapshot filename below)
                # recovers that identity for the CSV row instead of logging
                # "Unknown". last_known_name is None only when no confident
                # match was ever made this attempt, so a genuinely unrecognized
                # face still logs "Unknown" -- confirmed_name and
                # last_known_name are always set from the same identified_name
                # at the same moment (see _start_attempt/process_frame), so
                # this never changes what gets logged on a successful pass.
                log_name = self.confirmed_name or self.last_known_name or "Unknown"

                # Use the reason actually written to the CSV, not log_reason.
                # log_attendance downgrades a duplicate "success"/"confirmed" to
                # "failed"/"duplicate check-in this session"; if we named the
                # snapshot from the pre-downgrade log_reason it would say
                # "confirmed" for an attempt the CSV correctly recorded as a
                # duplicate failure. Naming from the returned reason keeps the
                # snapshot filename consistent with the CSV row for that attempt.
                _, written_reason = log_attendance(
                    log_name, log_result, log_reason, self.session_id
                )

                # Save a snapshot for every terminal outcome -- successes
                # included, not just failures -- since a check-in can pass the
                # liveness checks and still be a photo of someone else held up
                # to the camera; the saved image lets a lecturer verify the
                # actual face after the fact. Uses the pre-overlay clean_frame.
                os.makedirs(SNAPSHOT_DIR, exist_ok=True)
                # Name the snapshot with last_known_name, the same
                # bad-frame-protected identity as log_name above (log_name is
                # this same value whenever confirmed_name is None), so the
                # snapshot filename and the just-written CSV row agree on the
                # identity for this attempt.
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

            if show_restart_hint and self.restart_hint:
                restart_size = cv2.getTextSize(self.restart_hint, cv2.FONT_HERSHEY_DUPLEX, 0.6, 1)[0]
                restart_x = (frame_width - restart_size[0]) // 2
                cv2.putText(frame, self.restart_hint, (restart_x, frame_height - 10), cv2.FONT_HERSHEY_DUPLEX, 0.6, (200, 200, 200), 1)

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