import main

CALLS = []

def _fake_has_success(name, session_id):
    CALLS.append((name, session_id))
    return name == "Already Checked In Student"

if __name__ == "__main__":
    main.has_success_this_session = _fake_has_success

    session = main.CheckinSession("test-session", [], [])
    try:
        session._check_duplicate_checkin()
        assert CALLS == []
        assert session.check_locked is False

        session.identified_name = "New Student"
        session._check_duplicate_checkin()
        assert CALLS == [("New Student", "test-session")]
        assert session.check_locked is False
        assert session.flow_phase is None

        session._check_duplicate_checkin()
        assert CALLS == [("New Student", "test-session")]

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
