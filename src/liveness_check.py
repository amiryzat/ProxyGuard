# src/liveness_check.py
# Handles liveness detection to confirm a real, present person rather than
# a photo or static image. Combines blink detection (continuous, no prompt
# needed) with a randomized head movement challenge (active, prompted).

import cv2
import mediapipe as mp
import numpy as np
import random
import time
import os

random.seed(os.urandom(8))

mp_face_mesh = mp.solutions.face_mesh

LEFT_EYE = [362, 385, 387, 263, 373, 380]
RIGHT_EYE = [33, 160, 158, 133, 153, 144]

NOSE_TIP = 1
CHIN = 152
LEFT_EYE_CORNER = 33
RIGHT_EYE_CORNER = 263
LEFT_MOUTH_CORNER = 61
RIGHT_MOUTH_CORNER = 291

EAR_THRESHOLD = 0.21
CONSECUTIVE_FRAMES = 2

CHALLENGE_DURATION_SECONDS = 10
CHALLENGE_DIRECTIONS = ["left", "right", "up"]


def calculate_ear(landmarks, eye_indices, frame_width, frame_height):
    points = []
    for idx in eye_indices:
        landmark = landmarks[idx]
        x = int(landmark.x * frame_width)
        y = int(landmark.y * frame_height)
        points.append((x, y))

    points = np.array(points)

    vertical_1 = np.linalg.norm(points[1] - points[5])
    vertical_2 = np.linalg.norm(points[2] - points[4])
    horizontal = np.linalg.norm(points[0] - points[3])

    ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
    return ear


class BlinkDetector:
    def __init__(self):
        self.frame_counter = 0
        self.blink_count = 0

    def update(self, landmarks, frame_width, frame_height):
        left_ear = calculate_ear(landmarks, LEFT_EYE, frame_width, frame_height)
        right_ear = calculate_ear(landmarks, RIGHT_EYE, frame_width, frame_height)
        avg_ear = (left_ear + right_ear) / 2.0

        blinked_this_frame = False

        if avg_ear < EAR_THRESHOLD:
            self.frame_counter += 1
        else:
            if self.frame_counter >= CONSECUTIVE_FRAMES:
                self.blink_count += 1
                blinked_this_frame = True
            self.frame_counter = 0

        return avg_ear, blinked_this_frame, self.blink_count


def get_head_pose(landmarks, frame_width, frame_height):
    def get_point(idx):
        landmark = landmarks[idx]
        return np.array([landmark.x * frame_width, landmark.y * frame_height])

    nose = get_point(NOSE_TIP)
    chin = get_point(CHIN)
    left_eye = get_point(LEFT_EYE_CORNER)
    right_eye = get_point(RIGHT_EYE_CORNER)

    face_center_x = (left_eye[0] + right_eye[0]) / 2.0
    face_width = abs(right_eye[0] - left_eye[0])
    horizontal_offset = (nose[0] - face_center_x) / face_width

    face_center_y = (left_eye[1] + right_eye[1]) / 2.0
    face_height = abs(chin[1] - face_center_y)
    vertical_offset = (nose[1] - face_center_y) / face_height

    direction = "center"
    if horizontal_offset > 0.15:
        direction = "right"
    elif horizontal_offset < -0.15:
        direction = "left"
    elif vertical_offset > 0.65:
        direction = "down"
    elif vertical_offset < 0.20:
        direction = "up"

    return direction, horizontal_offset, vertical_offset


class HeadMovementChallenge:
    """
    Manages a randomized head movement challenge. Call start() to begin a
    new challenge with a random direction and a time limit. Call check()
    each frame with the current detected direction to see if the person
    matched the instruction in time. The challenge either passes, fails,
    or is still waiting, depending on elapsed time and whether a match
    was seen.
    """

    def __init__(self, duration_seconds=CHALLENGE_DURATION_SECONDS):
        self.duration_seconds = duration_seconds
        self.target_direction = None
        self.start_time = None
        self.result = None

    def start(self):
        self.target_direction = random.choice(CHALLENGE_DIRECTIONS)
        self.start_time = time.time()
        self.result = None

    def check(self, current_direction):
        if self.target_direction is None:
            return "not_started"

        if self.result is not None:
            return self.result

        elapsed = time.time() - self.start_time

        if current_direction == self.target_direction:
            self.result = "passed"
            return self.result

        if elapsed > self.duration_seconds:
            self.result = "failed"
            return self.result

        return "waiting"

    def time_remaining(self):
        if self.start_time is None:
            return 0
        remaining = self.duration_seconds - (time.time() - self.start_time)
        return max(0, remaining)


if __name__ == "__main__":
    cap = cv2.VideoCapture(0)
    blink_detector = BlinkDetector()
    challenge = HeadMovementChallenge()
    challenge.start()

    with mp_face_mesh.FaceMesh(
        max_num_faces=1,
        refine_landmarks=False,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    ) as face_mesh:

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.flip(frame, 1)
            key = cv2.waitKey(1) & 0xFF
            frame_height, frame_width = frame.shape[:2]
            small_frame = cv2.resize(frame, (0, 0), fx=0.5, fy=0.5)
            rgb_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            results = face_mesh.process(rgb_frame)

            if results.multi_face_landmarks:
                landmarks = results.multi_face_landmarks[0].landmark

                ear, blinked, total_blinks = blink_detector.update(landmarks, frame_width, frame_height)
                direction, h_offset, v_offset = get_head_pose(landmarks, frame_width, frame_height)

                status = challenge.check(direction)
                remaining = challenge.time_remaining()

                cv2.putText(frame, f"EAR: {ear:.2f}", (30, 40), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Blinks: {total_blinks}", (30, 75), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 255, 0), 2)
                cv2.putText(frame, f"Head: {direction}", (30, 110), cv2.FONT_HERSHEY_DUPLEX, 0.7, (255, 200, 0), 2)

                instruction_text = f"Turn head {challenge.target_direction.upper()}  ({remaining:.1f}s)"
                text_size = cv2.getTextSize(instruction_text, cv2.FONT_HERSHEY_DUPLEX, 0.9, 2)[0]
                text_x = (frame_width - text_size[0]) // 2
                cv2.putText(frame, instruction_text, (text_x, frame_height - 80), cv2.FONT_HERSHEY_DUPLEX, 0.9,
                            (255, 255, 255), 2)

                if status == "waiting" and direction != "center" and direction != challenge.target_direction:
                    wrong_msg = f"That is {direction.upper()}, please turn {challenge.target_direction.upper()}"
                    wrong_size = cv2.getTextSize(wrong_msg, cv2.FONT_HERSHEY_DUPLEX, 0.7, 2)[0]
                    wrong_x = (frame_width - wrong_size[0]) // 2
                    cv2.putText(frame, wrong_msg, (wrong_x, frame_height - 110), cv2.FONT_HERSHEY_DUPLEX, 0.7,
                                (0, 165, 255), 2)

                if status == "passed":
                    msg = "CHALLENGE PASSED"
                    color = (0, 255, 0)
                elif status == "failed":
                    msg = "CHALLENGE FAILED"
                    color = (0, 0, 255)
                else:
                    msg = None

                if msg:
                    msg_size = cv2.getTextSize(msg, cv2.FONT_HERSHEY_DUPLEX, 0.9, 2)[0]
                    msg_x = (frame_width - msg_size[0]) // 2
                    cv2.putText(frame, msg, (msg_x, frame_height - 40), cv2.FONT_HERSHEY_DUPLEX, 0.9, color, 2)

                if status in ("passed", "failed") and key == ord('n'):
                    challenge.start()
            else:
                cv2.putText(frame, "No face detected", (30, 40), cv2.FONT_HERSHEY_DUPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow("ProxyGuard - Liveness Detection Test", frame)

            if key == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()