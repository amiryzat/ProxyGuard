# src/test_duplicate_checkin.py
# ponytail: single runnable self-check for CheckinSession._check_duplicate_checkin()
# -- catches the bypass firing on a not-yet-stable identity, failing to fire for
# a genuine duplicate, or re-scanning attendance.csv for an identity already
# checked once this attempt. Not a full suite. Monkeypatches
# main.has_success_this_session so it never touches the real logs/attendance.csv.

import main

CALLS = []


def _fake_has_success(name, session_id):
    CALLS.append((name, session_id))
    return name == "Already Checked In Student"


if __name__ == "__main__":
    main.has_success_this_session = _fake_has_success

    session = main.CheckinSession("test-session", [], [])
    try:
        # Not yet stable (no identified_name) -- must not call the helper or lock.
        session._check_duplicate_checkin()
        assert CALLS == []
        assert session.check_locked is False

        # Stable identity, but no prior success this session -- challenge continues.
        session.identified_name = "New Student"
        session._check_duplicate_checkin()
        assert CALLS == [("New Student", "test-session")]
        assert session.check_locked is False
        assert session.flow_phase is None

        # Same identity again next processed frame -- must NOT re-scan.
        session._check_duplicate_checkin()
        assert CALLS == [("New Student", "test-session")]  # unchanged

        # A genuine duplicate -- bypass locks straight into duplicate_checkin,
        # skipping liveness_success entirely.
        session2 = main.CheckinSession("test-session", [], [])
        try:
            session2.identified_name = "Already Checked In Student"
            session2._check_duplicate_checkin()
            assert session2.check_locked is True
            assert session2.flow_phase == "duplicate_checkin"
            assert session2.confirmed_name is None
            assert session2.can_reset() is True
        finally:
            session2.close()
    finally:
        session.close()

    print("duplicate check-in self-check passed")
