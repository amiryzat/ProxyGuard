# dashboard/test_assistant.py
# ponytail: single runnable self-check for build_assistant_recommendations()/
# build_assistant_summary() (Phase F1/F3 rule-based assistant) -- catches a
# broken rule, a card count above ASSISTANT_MAX_CARDS, resolution-awareness
# regressions, or accusatory wording sneaking into a card, not a full suite.

from app import build_assistant_recommendations, build_assistant_summary, ASSISTANT_MAX_CARDS

BANNED_WORDS = ("cheat", "fraud", "certainty", "certain proxy", "confirmed with certainty")


def _analytics(total=0, successful=0, failed=0, flagged=0, duplicate=0, unknown=0,
                liveness_failures=0, success_rate=0):
    return {
        "total": total, "successful": successful, "failed": failed, "flagged": flagged,
        "duplicate": duplicate, "unknown": unknown, "liveness_failures": liveness_failures,
        "success_rate": success_rate,
    }


def _review(unreviewed=0, accepted=0, suspicious=0):
    return {"unreviewed": unreviewed, "accepted": accepted, "suspicious": suspicious}


def _row(name, reason, flagged=False, review_status="unreviewed", snapshot=None, time="10:00:00"):
    return {
        "cells": {"name": name, "result": "failed", "reason": reason, "time": time, "session_id": "s1", "date": "2026-01-01"},
        "flagged": flagged,
        "review": {"review_status": review_status, "review_note": "", "reviewed_at": ""},
        "snapshot": snapshot,
    }


def _assert_card_shape(cards):
    assert 1 <= len(cards) <= ASSISTANT_MAX_CARDS, len(cards)
    for card in cards:
        assert card["priority"] in ("Low", "Medium", "High")
        assert card["title"] and card["action"]
        assert "count" in card and "triggered_by" in card and "detail" in card and "actions" in card
        text = (card["title"] + card["triggered_by"] + card["action"]).lower()
        for banned in BANNED_WORDS:
            assert banned not in text, (banned, card)


if __name__ == "__main__":
    # Empty session: a single informational card.
    empty_cards = build_assistant_recommendations(_analytics(total=0, success_rate=0), _review(), [])
    assert len(empty_cards) == 1
    assert empty_cards[0]["priority"] == "Low"

    # Clean session (no issues): exactly one normal-session card, not padded
    # with generic filler tips (requirement 7).
    clean = build_assistant_recommendations(
        _analytics(total=10, successful=10, failed=0, success_rate=100.0), _review(), []
    )
    _assert_card_shape(clean)
    assert len(clean) == 1
    assert "normal" in clean[0]["title"].lower()

    # Heavy-issue session: every rule should fire, sorted High -> Medium ->
    # Low, capped at ASSISTANT_MAX_CARDS, each affected row set carrying a
    # "View affected attempts" action.
    messy_rows = (
        [_row("Alice", "duplicate check-in this session") for _ in range(2)]
        + [_row("Bob", "liveness timeout") for _ in range(3)]
        + [_row("Unknown", "face not recognized", snapshot="s1_unknown_face_not_recognized_090000.jpg", time="09:0%d:00" % i) for i in range(4)]
        + [_row("Carol", "liveness timeout", flagged=True) for _ in range(2)]
        + [_row("Dan", "liveness timeout", review_status="suspicious") for _ in range(1)]
        + [_row("Eve", "confirmed") for _ in range(1)]  # unreviewed filler, non-matching reason
    )
    messy = build_assistant_recommendations(
        _analytics(total=20, successful=8, failed=12, flagged=2, duplicate=2,
                   unknown=4, liveness_failures=6, success_rate=40.0),
        _review(unreviewed=6, accepted=1, suspicious=1),
        messy_rows,
    )
    _assert_card_shape(messy)
    assert len(messy) == ASSISTANT_MAX_CARDS
    ranks = {"High": 0, "Medium": 1, "Low": 2}
    priorities = [ranks[c["priority"]] for c in messy]
    assert priorities == sorted(priorities)  # priority-sorted, High first
    assert priorities[0] == 0  # at least one High card made the cut (flagged/duplicate/suspicious all qualify)
    duplicate_card = next(c for c in messy if c["title"] == "Duplicate check-in attempts")
    assert duplicate_card["count"] == 2
    assert "Alice" in duplicate_card["detail"]
    assert any(a["type"] == "view_filter" and a["filter_value"] == "duplicate" for a in duplicate_card["actions"])
    unreviewed_card = next(c for c in messy if c["title"] == "Attempts pending review")
    assert any(a["type"] == "open_next_unreviewed" for a in unreviewed_card["actions"])
    # "Review snapshot" was removed as redundant -- View affected attempts
    # already lands on the matching rows, where each one's own thumbnail
    # opens the same modal directly. No card should ever offer it again.
    assert all(a["type"] != "review_snapshot" for c in messy for a in c["actions"])

    # One real issue (single duplicate, no filler) should still show up alone.
    # review_status="accepted" so this row doesn't also trip the unreviewed
    # rule -- a realistic already-reviewed duplicate.
    one_issue_rows = [_row("Frank", "duplicate check-in this session", review_status="accepted")]
    one_issue = build_assistant_recommendations(
        _analytics(total=5, successful=4, failed=1, duplicate=1, success_rate=80.0), _review(), one_issue_rows
    )
    _assert_card_shape(one_issue)
    assert len(one_issue) == 1
    assert one_issue[0]["title"] == "Duplicate check-in attempts"

    # Resolution-awareness: once the only unreviewed row is reviewed, the
    # pending-review card must disappear (requirement 7).
    unreviewed_row = [_row("Grace", "confirmed")]
    before = build_assistant_recommendations(
        _analytics(total=5, successful=5, failed=0, success_rate=100.0), _review(unreviewed=1), unreviewed_row
    )
    assert any(c["title"] == "Attempts pending review" for c in before)
    reviewed_row = [_row("Grace", "confirmed", review_status="accepted")]
    resolved = build_assistant_recommendations(
        _analytics(total=5, successful=5, failed=0, success_rate=100.0), _review(accepted=1), reviewed_row
    )
    assert not any(c["title"] == "Attempts pending review" for c in resolved)

    # Summary: attention level and main concern track the top-ranked card;
    # success-rate fields pass through from session_analytics unchanged.
    messy_analytics = _analytics(total=20, successful=8, failed=12, flagged=2, duplicate=2,
                                  unknown=4, liveness_failures=6, success_rate=40.0)
    summary = build_assistant_summary(messy, _review(unreviewed=6, accepted=1, suspicious=1), messy_analytics)
    assert summary["attention"] == messy[0]["priority"]
    assert summary["main_concern"] == messy[0]["title"]
    assert summary["needs_review"] == 6
    assert summary["success_rate"] == 40.0
    assert summary["successful"] == 8
    assert summary["total"] == 20

    print("dashboard assistant self-check passed")
