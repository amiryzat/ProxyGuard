# dashboard/test_reviews.py
# ponytail: single runnable self-check for the Phase E1 review data layer
# (build_review_id determinism, upsert, unreviewed default). Points REVIEWS_PATH
# at a temp file so it never touches the real logs/reviews.csv.

import os
import tempfile

import app as dashboard_app

if __name__ == "__main__":
    dashboard_app.REVIEWS_PATH = os.path.join(tempfile.mkdtemp(), "reviews.csv")

    row = dict(session_id="2026-07-09_0900_CSC649_Week3", date="2026-07-09",
               time="09:05:12", name="Amir", result="failed", reason="liveness timeout")

    # Same fields -> same id, every time.
    id_a = dashboard_app.build_review_id(**{k if k != "time" else "time_str": v for k, v in row.items()})
    id_b = dashboard_app.build_review_id(**{k if k != "time" else "time_str": v for k, v in row.items()})
    assert id_a == id_b

    # No review recorded yet -> unreviewed default.
    assert dashboard_app.get_review_for_row(row, {})["review_status"] == "unreviewed"

    # Write + read back.
    review_id = dashboard_app.write_review(review_status="suspicious", review_note="check snapshot", **{
        k if k != "time" else "time_str": v for k, v in row.items()
    })
    assert review_id == id_a
    stored = dashboard_app.get_review_for_row(row, dashboard_app.read_reviews())
    assert stored["review_status"] == "suspicious"
    assert stored["review_note"] == "check snapshot"
    assert stored["reviewed_at"]

    # Upsert overwrites, doesn't duplicate.
    dashboard_app.write_review(review_status="accepted", review_note="", **{
        k if k != "time" else "time_str": v for k, v in row.items()
    })
    reviews = dashboard_app.read_reviews()
    assert len(reviews) == 1
    assert reviews[review_id]["review_status"] == "accepted"

    # Invalid status rejected.
    try:
        dashboard_app.write_review(review_status="bogus", review_note="", **{
            k if k != "time" else "time_str": v for k, v in row.items()
        })
        raise AssertionError("expected ValueError for invalid review_status")
    except ValueError:
        pass

    print("review data layer self-check passed")
