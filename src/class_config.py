# src/class_config.py
# Predefined list of class subjects (and the allowed week range) used when
# setting up an attendance session.
#
# Kept as a standalone, dependency-free config module -- matching the
# project's module-independence convention -- so both the current terminal
# setup in main.py and a planned future web-based setup screen can import the
# same list without pulling in cv2/mediapipe or duplicating the subjects.
#
# Each entry is "<CODE> - <Full subject name>". The code portion (the text
# before " - ") is what gets embedded into session_id, so keep codes short
# and free of spaces. This list is meant to be edited freely to add or remove
# the subjects a lecturer can pick from.

from datetime import datetime

CLASS_SUBJECTS = [
    "CSC649 - Special Topics in Computer Science",
    "CSC648 - Software Engineering",
    "CSC584 - Advanced Database",
]

# Teaching weeks a session can belong to (inclusive). Adjust if the semester
# structure changes.
WEEK_MIN = 1
WEEK_MAX = 14


def subject_code(subject):
    """
    Return the short code portion of a subject entry -- the text before the
    first " - " (e.g. "CSC649" from "CSC649 - Special Topics in Computer
    Science"). This code is what gets embedded into session_id, so it must be
    space-free and filesystem-safe; keeping the split here means the rest of
    the system never has to know how a subject string is laid out.
    """
    return subject.split(" - ", 1)[0].strip()


def build_session_id(subject, week_number, now=None):
    """
    Build the session_id from the timestamp plus class + week context.

    Format: "YYYY-MM-DD_HHMM_<CODE>_Week<N>", e.g.
    "2026-07-07_0900_CSC649_Week3". The pieces are underscore-separated and
    individually parseable, so later parts of the system can read the
    subject/week back out of the id if needed. The subject *code* (not the
    full name) is embedded to keep the id space-free and filesystem-safe,
    since the same id also becomes part of snapshot filenames.

    Lives here (not in main.py) so both main.py's terminal setup and the
    student check-in web app can build session_ids from a single source of
    truth without either duplicating the format or pulling in cv2/mediapipe.
    """
    now = now or datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H%M")
    return f"{timestamp}_{subject_code(subject)}_Week{week_number}"
