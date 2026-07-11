# src/experiment_far_frr.py
# Leave-one-out FAR/FRR experiment over the real data/known_faces/ reference
# images, reusing face_recognizer.recognize_face() directly (no duplicated
# matching logic) so the measured numbers reflect exactly what the live
# system does. Written for docs/report.md Section 9 -- see the "Recognition
# Tests"/"Experimental Results" methodology there.
#
# Method (standard leave-one-out identification protocol, since no live-camera
# trials are available in this environment):
#   For each reference image i (the "probe"):
#     - GENUINE trial: gallery = every OTHER image (all subjects, including
#       the probe's own subject's remaining photos). Expected: matched to the
#       probe's true identity. A miss (Unknown or wrong name) is a false
#       reject.
#     - IMPOSTOR trial: gallery = every image EXCEPT ALL of the probe's own
#       subject's photos (simulating the probe as an unregistered/impostor
#       person). Expected: rejected as "Unknown". Any non-"Unknown" result is
#       a false accept.
#
# recognize_face() is called on the probe's own loaded image each time (full
# detection + encoding + matching), not on a pre-computed encoding, so this
# exercises the identical code path a live webcam frame would.

import os
import re
import sys
import time
import json

import face_recognition

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from face_recognizer import (
    DEFAULT_KNOWN_FACES_DIR,
    load_image_with_correct_orientation,
    load_known_faces,
    recognize_face,
)


def _load_gallery_with_filenames(known_faces_dir):
    """
    Mirrors load_known_faces()'s own per-file logic (same EXIF-corrected
    load, same face_recognition.face_encodings() call, same trailing-index
    name-stripping regex) but keeps the filename aligned with each encoding,
    which load_known_faces() itself doesn't expose. Kept as a small, separate
    duplication here rather than changing face_recognizer.py's return
    signature for an experiment script's sake. Files with no detectable face
    are skipped and recorded, exactly as load_known_faces() does (with its
    own printed warning) -- not silently dropped.
    """
    filenames, images, encodings, names, no_face = [], [], [], [], []
    for filename in sorted(os.listdir(known_faces_dir)):
        if not filename.lower().endswith((".jpg", ".jpeg", ".png")):
            continue
        path = os.path.join(known_faces_dir, filename)
        image = load_image_with_correct_orientation(path)
        found = face_recognition.face_encodings(image)
        if not found:
            no_face.append(filename)
            continue
        name = re.sub(r"[\s_-]*\d+$", "", os.path.splitext(filename)[0])
        filenames.append(filename)
        images.append(image)
        encodings.append(found[0])
        names.append(name)
    return filenames, images, encodings, names, no_face


def run_experiment(tolerance, min_margin, known_faces_dir=DEFAULT_KNOWN_FACES_DIR):
    filenames, images, all_encodings, all_names, no_face_files = _load_gallery_with_filenames(known_faces_dir)

    subject_image_counts = {}
    for n in all_names:
        subject_image_counts[n] = subject_image_counts.get(n, 0) + 1

    genuine_total = 0
    genuine_correct = 0
    genuine_misses = []  # (filename, true_name, got_name)
    genuine_skipped_singletons = []  # subjects with only 1 image -- leave-one-out
    # would leave zero gallery images of them, which isn't a fair genuine test

    impostor_total = 0
    impostor_rejected = 0
    impostor_false_accepts = []  # (filename, true_name, got_name)

    for i, (filename, true_name) in enumerate(zip(filenames, all_names)):
        probe_image = images[i]

        # --- Genuine trial: leave this one image out, keep everyone else ---
        if subject_image_counts[true_name] > 1:
            genuine_gallery_enc = all_encodings[:i] + all_encodings[i + 1:]
            genuine_gallery_names = all_names[:i] + all_names[i + 1:]
            names, _ = recognize_face(probe_image, genuine_gallery_enc, genuine_gallery_names,
                                       tolerance=tolerance, min_margin=min_margin)
            genuine_total += 1
            got = names[0] if names else "NO_FACE_DETECTED"
            if got == true_name:
                genuine_correct += 1
            else:
                genuine_misses.append((filename, true_name, got))
        else:
            genuine_skipped_singletons.append(filename)

        # --- Impostor trial: exclude every image of this probe's own subject ---
        impostor_gallery_enc = [e for e, n in zip(all_encodings, all_names) if n != true_name]
        impostor_gallery_names = [n for n in all_names if n != true_name]
        names, _ = recognize_face(probe_image, impostor_gallery_enc, impostor_gallery_names,
                                   tolerance=tolerance, min_margin=min_margin)
        impostor_total += 1
        got = names[0] if names else "NO_FACE_DETECTED"
        if got == "Unknown" or got == "NO_FACE_DETECTED":
            impostor_rejected += 1
        else:
            impostor_false_accepts.append((filename, true_name, got))

    frr = (genuine_total - genuine_correct) / genuine_total
    far = len(impostor_false_accepts) / impostor_total

    return {
        "tolerance": tolerance,
        "min_margin": min_margin,
        "n_images_usable": len(filenames),
        "n_images_no_face_detected": len(no_face_files),
        "no_face_files": no_face_files,
        "subject_image_counts": subject_image_counts,
        "genuine_trials": genuine_total,
        "genuine_correct": genuine_correct,
        "genuine_skipped_singletons": genuine_skipped_singletons,
        "frr": frr,
        "genuine_misses": genuine_misses,
        "impostor_trials": impostor_total,
        "impostor_rejected": impostor_rejected,
        "far": far,
        "impostor_false_accepts": impostor_false_accepts,
    }


def measure_streaming_perf(n_frames=60):
    """
    Real per-frame processing-time benchmark for CheckinSession.process_frame,
    using the actual live webcam if available (falls back to a static image
    tiled as synthetic frames if no camera is present, clearly labeled as such
    -- never fabricated numbers, just a documented substitute input source).
    """
    import cv2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from main import CheckinSession

    encodings, names = load_known_faces()
    session = CheckinSession("far-frr-experiment-session", encodings, names, restart_hint=None)

    cap = cv2.VideoCapture(0)
    ok, frame = cap.read()
    source = "live webcam"
    if not ok or frame is None:
        cap.release()
        cap = None
        # Fall back to a real reference image tiled to a plausible frame size,
        # so the timing loop still exercises the same code path even with no
        # camera attached -- explicitly not a live-camera measurement.
        sample_path = os.path.join(DEFAULT_KNOWN_FACES_DIR, sorted(os.listdir(DEFAULT_KNOWN_FACES_DIR))[0])
        frame = load_image_with_correct_orientation(sample_path)
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        source = f"static fallback image ({os.path.basename(sample_path)}, no camera detected)"

    durations = []
    for _ in range(n_frames):
        if cap is not None:
            ok, live_frame = cap.read()
            if not ok:
                break
            input_frame = live_frame
        else:
            input_frame = frame

        t0 = time.perf_counter()
        session.process_frame(input_frame)
        durations.append(time.perf_counter() - t0)

    if cap is not None:
        cap.release()
    session.close()

    avg = sum(durations) / len(durations)
    return {
        "source": source,
        "frames_measured": len(durations),
        "avg_ms_per_frame": avg * 1000,
        "estimated_fps": 1.0 / avg if avg > 0 else None,
    }


if __name__ == "__main__":
    print("=== FAR/FRR leave-one-out experiment: current tightened thresholds (tolerance=0.45, margin=0.1) ===")
    tightened = run_experiment(tolerance=0.45, min_margin=0.1)
    _summary_skip = ("genuine_misses", "impostor_false_accepts", "genuine_skipped_singletons")
    print(json.dumps({k: v for k, v in tightened.items() if k not in _summary_skip}, indent=2))
    print("Genuine misses:", tightened["genuine_misses"])
    print("Impostor false accepts:", tightened["impostor_false_accepts"])

    print("\n=== Same experiment: original looser thresholds (tolerance=0.5, margin=0.05) for comparison ===")
    original = run_experiment(tolerance=0.5, min_margin=0.05)
    print(json.dumps({k: v for k, v in original.items() if k not in _summary_skip}, indent=2))
    print("Genuine misses:", original["genuine_misses"])
    print("Impostor false accepts:", original["impostor_false_accepts"])

    print("\n=== Streaming / processing-time benchmark ===")
    perf = measure_streaming_perf()
    print(json.dumps(perf, indent=2))
