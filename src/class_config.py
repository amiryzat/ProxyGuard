
import re
from datetime import datetime

CLASS_SUBJECTS = [
    "CSC 649 - SPECIAL TOPICS IN COMPUTER SCIENCE",
    "CSC557 - MOBILE PROGRAMMING",
    "ENT 600 - TECHNOLOGY ENTREPRENEURSHIP",
    "CSP 600 - PROJECT FORMULATION",
    "CSC645 - ALGORITHM ANALYSIS AND DESIGN",
    "CSC580 - PARALLEL PROCESSING",
    "TMC501 - INTRODUCTORY MANDARIN (LEVEL III)",
]


WEEK_MIN = 1
WEEK_MAX = 14


def subject_code(subject):


    return re.sub(r"\s+", "", subject.split(" - ", 1)[0])


def build_session_id(subject, week_number, now=None):

    now = now or datetime.now()
    timestamp = now.strftime("%Y-%m-%d_%H%M")
    return f"{timestamp}_{subject_code(subject)}_Week{week_number}"
