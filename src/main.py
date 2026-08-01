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
from attendance_logger import log_attendance, has_success_this_session, DUPLICATE_REASON
from class_config import CLASS_SUBJECTS, WEEK_MIN, WEEK_MAX, build_session_id

random.seed(os.urandom(8))

LIVENESS_MESSAGE_SECONDS = 2

MULTI_FACE_MESSAGE = "Only one person allowed in frame, please ensure you are alone during check-in"
MULTI_FACE_MESSAGE_LINES = [
    "Only one person allowed in frame,",
    "please ensure you are alone during check-in",
]

FACE_JUMP_MAX_FRACTION = 0.35

IDENTITY_HOLD_SECONDS = 4.0

DIFFERENT_NAME_TOLERANCE = 1

CONTINUITY_WARNING_SECONDS = 2
CONTINUITY_BROKEN_MESSAGE = "Face changed or lost, please keep the same face in frame"

def _face_box_close(box_a, box_b, frame_width, max_fraction=FACE_JUMP_MAX_FRACTION):
    if box_a is None or box_b is None:
        return False
    top_a, right_a, bottom_a, left_a = box_a
    top_b, right_b, bottom_b, left_b = box_b
    center_a = ((left_a + right_a) / 2.0, (top_a + bottom_a) / 2.0)
    center_b = ((left_b + right_b) / 2.0, (top_b + bottom_b) / 2.0)
    distance = ((center_a[0] - center_b[0]) ** 2 + (center_a[1] - center_b[1]) ** 2) ** 0.5
    return distance <= max_fraction * frame_width

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOT_DIR = os.path.join(SCRIPT_DIR, "..", "logs", "snapshots")

def build_snapshot_filename(session_id, name, reason):
    def slug(text):
        return "".join(c if c.isalnum() else "_" for c in text).strip("_").lower() or "unknown"

    timestamp = datetime.now().strftime("%H%M%S")
    return f"{session_id}_{slug(name)}_{slug(reason)}_{timestamp}.jpg"

def prompt_session_setup():
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

    def __init__(self, session_id, known_encodings, known_names,
                 restart_hint="Press 'n' to run a new check"):
        self.session_id = session_id
        self.known_encodings = known_encodings
        self.known_names = known_names
        self.restart_hint = restart_hint

        self.face_mesh = mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        self.blink_detector = BlinkDetector()
        self.challenge = HeadMovementChallenge()

        self.frame_count = 0
        self.process_every_n_frames = 3
        self.last_names = []
        self.last_face_locations = []

        self.banner = None

        self._start_attempt()

    def _start_attempt(self):
        self.challenge.start()
        self.blink_count_at_challenge_start = self.blink_detector.blink_count
        self.identified_name = None
        self.last_known_name = None
        self.confirmed_name = None
        self.check_locked = False
        self.locked_status = None

        self.active_face_box = None
        self.last_confirmed_time = None
        self.different_name_streak = 0
        self.pending_reverify = False
        self.continuity_warning_until = None

        self.duplicate_checked_name = None

        self.attempt_started_at = None
        self.identity_decided_at = None
        self.challenge_started_at = None
        self.terminal_outcome_at = None
        self.recognition_duration_seconds = None
        self.liveness_duration_seconds = None
        self.decision_duration_seconds = None

        self.flow_phase = None
        self.phase_start = None
        self.outcome_logged = False

    def reset(self):
        self._start_attempt()

    def can_reset(self):
        return self.check_locked and self.flow_phase in (
            "confirmed", "not_recognized", "liveness_failed", "identity_mismatch", "duplicate_checkin"
        )

    def close(self):
        self.face_mesh.close()

    def _clear_active_identity(self):
        self.identified_name = None
        self.last_known_name = None
        self.active_face_box = None
        self.last_confirmed_time = None
        self.different_name_streak = 0
        self.pending_reverify = False
        self.challenge.start()
        self.continuity_warning_until = time.time() + CONTINUITY_WARNING_SECONDS

    def _update_identity_continuity(self, names, face_locations, frame_width):
        if len(face_locations) > 1:
            self.pending_reverify = True
            return

        if self.identified_name is None:
            if len(face_locations) == 1 and names[0] != "Unknown":
                self.identified_name = names[0]
                self.last_known_name = names[0]
                self.active_face_box = face_locations[0]
                self.last_confirmed_time = time.time()
                self.different_name_streak = 0
                self.pending_reverify = False
                if self.identity_decided_at is None:
                    self.identity_decided_at = time.monotonic()
                    if self.attempt_started_at is not None:
                        self.recognition_duration_seconds = round(
                            self.identity_decided_at - self.attempt_started_at, 1
                        )
            return

        if len(face_locations) == 1:
            name = names[0]
            box = face_locations[0]

            if self.active_face_box is not None and not _face_box_close(self.active_face_box, box, frame_width):
                self._clear_active_identity()
                return

            if self.pending_reverify:
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

            self.active_face_box = box
            self.different_name_streak = 0
            if name == self.identified_name:
                self.last_known_name = name
                self.last_confirmed_time = time.time()

        if time.time() - self.last_confirmed_time > IDENTITY_HOLD_SECONDS:
            self._clear_active_identity()

    def _check_duplicate_checkin(self):
        if not (self.identified_name and self.identified_name != "Unknown"):
            return
        if self.duplicate_checked_name == self.identified_name:
            return
        self.duplicate_checked_name = self.identified_name
        if has_success_this_session(self.identified_name, self.session_id):
            self.check_locked = True
            self.locked_status = "duplicate"
            self.flow_phase = "duplicate_checkin"
            self.confirmed_name = None

    def _timing_overlay_text(self):
        if self.attempt_started_at is None:
            return "Waiting for face"

        if self.terminal_outcome_at is not None:
            elapsed = self.decision_duration_seconds
        else:
            elapsed = time.monotonic() - self.attempt_started_at

        if self.identity_decided_at is not None and self.recognition_duration_seconds is not None:
            return f"Recognized {self.recognition_duration_seconds:.1f}s | Total {elapsed:.1f}s"
        return f"Attempt {elapsed:.1f}s"

    def timing_snapshot(self):
        if self.attempt_started_at is None:
            timing_phase = "waiting"
            attempt_elapsed_seconds = None
        else:
            attempt_elapsed_seconds = round(
                self.decision_duration_seconds if self.terminal_outcome_at is not None
                else time.monotonic() - self.attempt_started_at,
                1,
            )
            if self.terminal_outcome_at is not None:
                timing_phase = "terminal"
            elif self.identity_decided_at is not None:
                timing_phase = "liveness"
            else:
                timing_phase = "recognizing"

        return {
            "timing_phase": timing_phase,
            "attempt_elapsed_seconds": attempt_elapsed_seconds,
            "recognition_duration_seconds": self.recognition_duration_seconds,
            "liveness_duration_seconds": self.liveness_duration_seconds,
            "decision_duration_seconds": self.decision_duration_seconds,
        }

    def _record_terminal_timing(self):
        self.terminal_outcome_at = time.monotonic()
        if self.attempt_started_at is not None:
            self.decision_duration_seconds = round(
                self.terminal_outcome_at - self.attempt_started_at, 1
            )
        if self.identity_decided_at is None:
            self.identity_decided_at = self.terminal_outcome_at
            self.recognition_duration_seconds = self.decision_duration_seconds

    def process_frame(self, frame):
        frame = cv2.flip(frame, 1)
        clean_frame = frame.copy()
        frame_height, frame_width = frame.shape[:2]

        self.frame_count += 1
        if self.frame_count % self.process_every_n_frames == 0:
            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)

            if self.check_locked:
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

            if self.attempt_started_at is None and not self.check_locked and len(scaled_locations) == 1:
                self.attempt_started_at = time.monotonic()

            if not self.check_locked:
                self._update_identity_continuity(self.last_names, self.last_face_locations, frame_width)
                self._check_duplicate_checkin()

        num_faces = len(self.last_face_locations)
        for (top, right, bottom, left), name in zip(self.last_face_locations, self.last_names):
            if not self.check_locked:
                if num_faces > 1:
                    display_name = name
                else:
                    display_name = self.last_known_name or name
            else:
                display_name = name

            box_color = (0, 0, 255) if (not display_name or display_name == "Unknown") else (0, 255, 0)

            cv2.rectangle(frame, (left, top), (right, bottom), box_color, 2)
            if not self.check_locked:
                cv2.putText(frame, display_name, (left, top - 10), cv2.FONT_HERSHEY_DUPLEX, 0.7, box_color, 2)

        direction = "center"
        status = "waiting"

        if not self.check_locked:
            if num_faces > 1:
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

                    if self.challenge_started_at is None:
                        self.challenge_started_at = time.monotonic()
                    if self.attempt_started_at is None and not self.check_locked:
                        self.attempt_started_at = self.challenge_started_at

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
                    if self.challenge_started_at is not None:
                        self.liveness_duration_seconds = round(time.monotonic() - self.challenge_started_at, 1)
                    if self.identified_name and self.identified_name != "Unknown":
                        self.confirmed_name = self.identified_name
                    else:
                        self.confirmed_name = None
                elif status == "failed":
                    self.check_locked = True
                    self.locked_status = "failed"
                    self.flow_phase = "liveness_failed"
                    self.confirmed_name = None
                    if self.challenge_started_at is not None:
                        self.liveness_duration_seconds = round(time.monotonic() - self.challenge_started_at, 1)

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

            elif self.flow_phase == "duplicate_checkin":
                bottom_msg = f"ALREADY CHECKED IN: {self.last_known_name}"
                bottom_color = (0, 165, 255)
                show_restart_hint = True

            self.banner = bottom_msg

            if not self.outcome_logged and self.flow_phase in (
                "confirmed", "not_recognized", "liveness_failed", "identity_mismatch", "duplicate_checkin"
            ):
                self._record_terminal_timing()

                if self.flow_phase == "confirmed":
                    log_result, log_reason = "success", "confirmed"
                elif self.flow_phase == "not_recognized":
                    log_result, log_reason = "failed", "face not recognized"
                elif self.flow_phase == "liveness_failed":
                    log_result, log_reason = "failed", "liveness timeout"
                elif self.flow_phase == "duplicate_checkin":
                    log_result, log_reason = "failed", DUPLICATE_REASON
                else:
                    log_result, log_reason = "failed", "identity mismatch"

                log_name = self.confirmed_name or self.last_known_name or "Unknown"

                _, written_reason = log_attendance(
                    log_name, log_result, log_reason, self.session_id
                )

                os.makedirs(SNAPSHOT_DIR, exist_ok=True)
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

        timer_text = self._timing_overlay_text()
        timer_size = cv2.getTextSize(timer_text, cv2.FONT_HERSHEY_DUPLEX, 0.6, 1)[0]
        timer_x = frame_width - timer_size[0] - 20
        cv2.putText(frame, timer_text, (timer_x, 30), cv2.FONT_HERSHEY_DUPLEX, 0.6, (200, 200, 200), 1)

        return frame

if __name__ == "__main__":
    subject, week_number = prompt_session_setup()
    session_id = build_session_id(subject, week_number)
    print(f"Session: {session_id}")

    known_encodings, known_names = load_known_faces()
    print(f"Loaded {len(known_names)} face encodings for known people")

    cap = cv2.VideoCapture(0)
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