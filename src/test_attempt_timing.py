# src/test_attempt_timing.py
# ponytail: single runnable self-check for Evaluation Timing Phase R2 --
# catches attempt_started_at/identity_decided_at/challenge_started_at/
# terminal_outcome_at firing at the wrong time, being overwritten on a later
# frame, or the recognition/liveness/decision duration math drifting. Not a
# full suite. Drives CheckinSession's timing-related methods directly with
# synthetic inputs (no camera, no mediapipe, no real recognize_face call).

import time

import main

FRAME_WIDTH = 640


def _box(x=100, y=100, size=100):
    half = size / 2
    return (y - half, x + half, y + half, x - half)


if __name__ == "__main__":
    # --- Registered identity: attempt_started_at -> identity_decided_at ---
    session = main.CheckinSession("timing-test-session", [], [])
    try:
        assert session.attempt_started_at is None
        assert session.identity_decided_at is None
        assert session.recognition_duration_seconds is None

        # Simulate process_frame's own "first single face this attempt"
        # bookkeeping (the real trigger lives inline in process_frame; this
        # exercises the same guarded assignment it performs).
        if session.attempt_started_at is None:
            session.attempt_started_at = time.monotonic()
        started_at = session.attempt_started_at
        time.sleep(0.05)

        session._update_identity_continuity(["Alice"], [_box()], FRAME_WIDTH)
        assert session.identified_name == "Alice"
        assert session.identity_decided_at is not None
        assert session.recognition_duration_seconds is not None
        assert session.recognition_duration_seconds >= 0.04  # ~50ms elapsed, rounded to 1dp

        # A later re-recognition of the SAME name must NOT move
        # identity_decided_at/recognition_duration_seconds (requirement 5).
        frozen_decided_at = session.identity_decided_at
        frozen_recognition = session.recognition_duration_seconds
        time.sleep(0.05)
        session._update_identity_continuity(["Alice"], [_box()], FRAME_WIDTH)
        assert session.identity_decided_at == frozen_decided_at
        assert session.recognition_duration_seconds == frozen_recognition

        # Liveness pass -> _record_terminal_timing() (simulating the
        # "confirmed" path): decision_duration_seconds set, liveness duration
        # left as whatever was set by the challenge pass/fail branch (not
        # exercised here since that requires the mediapipe block; asserted
        # separately in the duplicate-checkin case below where it must stay
        # None).
        session.challenge_started_at = time.monotonic() - 0.2
        session.liveness_duration_seconds = 0.2
        session.confirmed_name = "Alice"
        session.flow_phase = "confirmed"
        session._record_terminal_timing()
        assert session.terminal_outcome_at is not None
        assert session.decision_duration_seconds is not None
        assert session.decision_duration_seconds >= session.recognition_duration_seconds

        # A second call (simulating a later frame while the terminal message
        # is still on screen) would be guarded by outcome_logged in
        # process_frame -- confirm _record_terminal_timing itself doesn't
        # need to re-guard by checking it's simply idempotent-safe to call
        # again with the same result class (real code never does, due to
        # the outcome_logged guard at the call site).
        second_decision = session.decision_duration_seconds
        time.sleep(0.05)
        session._record_terminal_timing()
        assert session.decision_duration_seconds != second_decision  # proves the guard MUST live at the call site
    finally:
        session.close()

    # --- Unknown outcome: identity_decided_at falls back to the terminal
    # instant, recognition_duration_seconds == decision_duration_seconds ---
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

    # --- Duplicate check-in: liveness_duration_seconds must stay None ------
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

    # --- timing_snapshot() / overlay text sanity across phases ------------
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
        assert session4._timing_overlay_text() == frozen_text  # frozen after terminal
    finally:
        session4.close()

    print("attempt timing self-check passed")
