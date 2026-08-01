import time

import main

FRAME_WIDTH = 640

def _box(x=100, y=100, size=100):
    half = size / 2
    return (y - half, x + half, y + half, x - half)

if __name__ == "__main__":
    session = main.CheckinSession("timing-test-session", [], [])
    try:
        assert session.attempt_started_at is None
        assert session.identity_decided_at is None
        assert session.recognition_duration_seconds is None

        if session.attempt_started_at is None:
            session.attempt_started_at = time.monotonic()
        started_at = session.attempt_started_at
        time.sleep(0.05)

        session._update_identity_continuity(["Alice"], [_box()], FRAME_WIDTH)
        assert session.identified_name == "Alice"
        assert session.identity_decided_at is not None
        assert session.recognition_duration_seconds is not None
        assert session.recognition_duration_seconds >= 0.04

        frozen_decided_at = session.identity_decided_at
        frozen_recognition = session.recognition_duration_seconds
        time.sleep(0.05)
        session._update_identity_continuity(["Alice"], [_box()], FRAME_WIDTH)
        assert session.identity_decided_at == frozen_decided_at
        assert session.recognition_duration_seconds == frozen_recognition

        session.challenge_started_at = time.monotonic() - 0.2
        session.liveness_duration_seconds = 0.2
        session.confirmed_name = "Alice"
        session.flow_phase = "confirmed"
        session._record_terminal_timing()
        assert session.terminal_outcome_at is not None
        assert session.decision_duration_seconds is not None
        assert session.decision_duration_seconds >= session.recognition_duration_seconds

        second_decision = session.decision_duration_seconds
        time.sleep(0.05)
        session._record_terminal_timing()
        assert session.decision_duration_seconds != second_decision
    finally:
        session.close()

    session2 = main.CheckinSession("timing-test-session", [], [])
    try:
        session2.attempt_started_at = time.monotonic() - 0.3
        assert session2.identity_decided_at is None
        session2.flow_phase = "not_recognized"
        session2._record_terminal_timing()
        assert session2.identity_decided_at == session2.terminal_outcome_at
        assert session2.recognition_duration_seconds == session2.decision_duration_seconds
    finally:
        session2.close()

    session3 = main.CheckinSession("timing-test-session", [], [])
    try:
        session3.attempt_started_at = time.monotonic() - 0.1
        session3.identity_decided_at = time.monotonic()
        session3.recognition_duration_seconds = 0.1
        session3.flow_phase = "duplicate_checkin"
        session3._record_terminal_timing()
        assert session3.liveness_duration_seconds is None
        assert session3.decision_duration_seconds is not None
    finally:
        session3.close()

    session4 = main.CheckinSession("timing-test-session", [], [])
    try:
        assert session4.timing_snapshot()["timing_phase"] == "waiting"
        assert session4._timing_overlay_text() == "Waiting for face"

        session4.attempt_started_at = time.monotonic()
        assert session4.timing_snapshot()["timing_phase"] == "recognizing"
        assert session4._timing_overlay_text().startswith("Attempt ")

        session4.identity_decided_at = time.monotonic()
        session4.recognition_duration_seconds = 0.5
        assert session4.timing_snapshot()["timing_phase"] == "liveness"
        assert "Recognized 0.5s" in session4._timing_overlay_text()

        session4.flow_phase = "confirmed"
        session4._record_terminal_timing()
        assert session4.timing_snapshot()["timing_phase"] == "terminal"
        frozen_text = session4._timing_overlay_text()
        time.sleep(0.05)
        assert session4._timing_overlay_text() == frozen_text
    finally:
        session4.close()

    print("attempt timing self-check passed")
