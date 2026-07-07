# src/pattern_flagger.py
# Reads logs/attendance.csv (written by attendance_logger.py) and flags
# suspicious patterns for lecturer review, rather than auto-rejecting
# anything. Three signals are checked: repeated failures for the same
# registered identity, duplicate check-in attempts within a session, and
# clusters of unrecognized-face attempts within a session.

import csv
import os
from collections import defaultdict
from datetime import datetime

# Resolve the log file the same way attendance_logger.py does. Deliberately
# not imported from there, so this module stays independently importable
# per the project's module-independence convention.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_PATH = os.path.join(SCRIPT_DIR, "..", "logs", "attendance.csv")

REPEATED_FAILURE_THRESHOLD = 3
UNRECOGNIZED_CLUSTER_THRESHOLD = 2
UNRECOGNIZED_CLUSTER_WINDOW_MINUTES = 5

DUPLICATE_REASON = "duplicate check-in this session"
NOT_RECOGNIZED_REASON = "face not recognized"


def _load_rows(log_path=DEFAULT_LOG_PATH):
    if not os.path.exists(log_path):
        return []
    with open(log_path, newline="") as f:
        return list(csv.DictReader(f))


def _row_datetime(row):
    return datetime.strptime(f"{row['date']} {row['time']}", "%Y-%m-%d %H:%M:%S")


def find_repeated_failures(rows, threshold=REPEATED_FAILURE_THRESHOLD):
    """
    Flags any registered (non-"Unknown") name with at least `threshold`
    failed rows across the whole log, regardless of session -- repeated
    failure for the same identity is a signal about that person, not
    something scoped to a single class session.
    """
    failure_counts = defaultdict(int)
    for row in rows:
        if row["result"] == "failed" and row["name"] != "Unknown":
            failure_counts[row["name"]] += 1

    return {name: count for name, count in failure_counts.items() if count >= threshold}


def find_duplicate_attempts(rows):
    """
    Groups rows flagged with DUPLICATE_REASON by (name, session_id), so a
    lecturer can see who tried to check in more than once successfully
    within the same session.
    """
    duplicate_counts = defaultdict(int)
    for row in rows:
        if row["reason"] == DUPLICATE_REASON:
            duplicate_counts[(row["name"], row["session_id"])] += 1

    return dict(duplicate_counts)


def find_unrecognized_clusters(rows, threshold=UNRECOGNIZED_CLUSTER_THRESHOLD, window_minutes=UNRECOGNIZED_CLUSTER_WINDOW_MINUTES):
    """
    Flags sessions where "face not recognized" attempts cluster together
    within `window_minutes` of each other at least `threshold` times.
    These rows are always logged under name "Unknown", so clustering is
    grouped by session_id instead of by name -- repeated unrecognized
    attempts in a short window within one session is itself the signal,
    regardless of who it was.
    """
    by_session = defaultdict(list)
    for row in rows:
        if row["reason"] == NOT_RECOGNIZED_REASON:
            by_session[row["session_id"]].append(_row_datetime(row))

    clusters = defaultdict(list)
    for session_id, timestamps in by_session.items():
        timestamps.sort()
        cluster = [timestamps[0]]
        for ts in timestamps[1:]:
            if (ts - cluster[-1]).total_seconds() <= window_minutes * 60:
                cluster.append(ts)
            else:
                if len(cluster) >= threshold:
                    clusters[session_id].append(len(cluster))
                cluster = [ts]
        if len(cluster) >= threshold:
            clusters[session_id].append(len(cluster))

    return dict(clusters)


def flag_patterns(log_path=DEFAULT_LOG_PATH):
    rows = _load_rows(log_path)
    return {
        "repeated_failures": find_repeated_failures(rows),
        "duplicate_attempts": find_duplicate_attempts(rows),
        "unrecognized_clusters": find_unrecognized_clusters(rows),
    }


def print_report(report):
    print("Repeated failures (same identity, whole log):")
    if report["repeated_failures"]:
        for name, count in report["repeated_failures"].items():
            print(f"  - {name}: {count} failed attempts")
    else:
        print("  (none)")

    print("Duplicate check-in attempts (same session):")
    if report["duplicate_attempts"]:
        for (name, session_id), count in report["duplicate_attempts"].items():
            print(f"  - {name} in session {session_id}: {count} duplicate attempt(s)")
    else:
        print("  (none)")

    print("Clustered unrecognized-face attempts (same session, within window):")
    if report["unrecognized_clusters"]:
        for session_id, cluster_sizes in report["unrecognized_clusters"].items():
            for size in cluster_sizes:
                print(f"  - session {session_id}: cluster of {size} unrecognized attempts")
    else:
        print("  (none)")


if __name__ == "__main__":
    # Manual smoke test: builds a small sample CSV (in the system temp
    # dir, not the real attendance log) covering two fake session_ids, so
    # all three flagging checks can be verified without the webcam flow.
    import tempfile

    sample_path = os.path.join(tempfile.gettempdir(), "proxyguard_pattern_flagger_sample.csv")
    session_a = "2026-07-05_1900"
    session_b = "2026-07-05_2030"

    sample_rows = [
        ["Test Student", "2026-07-05", "19:00:00", session_a, "success", "confirmed"],
        ["Test Student", "2026-07-05", "19:01:00", session_a, "failed", DUPLICATE_REASON],
        ["Test Student", "2026-07-05", "19:05:00", session_a, "failed", "liveness timeout"],
        ["Test Student", "2026-07-05", "19:06:00", session_a, "failed", "liveness timeout"],
        ["Test Student", "2026-07-05", "19:07:00", session_a, "failed", "liveness timeout"],
        ["Unknown", "2026-07-05", "19:10:00", session_a, "failed", NOT_RECOGNIZED_REASON],
        ["Unknown", "2026-07-05", "19:11:00", session_a, "failed", NOT_RECOGNIZED_REASON],
        ["Test Student", "2026-07-05", "20:30:00", session_b, "success", "confirmed"],
    ]

    with open(sample_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["name", "date", "time", "session_id", "result", "reason"])
        writer.writerows(sample_rows)

    print(f"Sample log written to {sample_path}\n")
    print_report(flag_patterns(sample_path))
