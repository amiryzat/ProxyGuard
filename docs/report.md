# ProxyGuard — Final Project Report (IEEE Conference Paper — Content Draft)

> **How to use this file:** This is the content source of truth for the final report, organized in the exact order given in the CSC649 report brief. Before submission, port this content into the official **IEEE Conference Paper template** (two-column, Times New Roman, per the brief's format requirement) in Word/LaTeX and export to PDF — this markdown file itself is not the submission format. Items marked **`[TODO]`** need input the group must supply (course section, lecturer name, measured results, screenshots) or a decision the group must make (final title, which figures to include) before the report is complete. Nothing marked `[TODO]` has been fabricated — see [[testing]] and [[bugs]] for what has actually been verified so far.
>
> Page-limit note: Cover Page, References, Appendices, and CD/Google Drive submission materials are **not** counted toward the 10-page limit — keep that in mind when trimming Sections 7–11 to fit.

---

## 1. Cover Page

- **Project Title:** ProxyGuard: A Liveness-Aware Face Recognition Attendance System for Proxy Detection `[TODO: confirm final title wording with the group/lecturer]`
- **Group Members:**
  | Name | Student ID |
  |---|---|
  | Muhammad Amir Izzat bin Rosdi | 2025394889 |
  | Muhammad Adli Fadhlan bin Azame | 2025180775 |
  | Muhammad Izzuddin bin Izad Emi | 2025181293 |
- **Course & Section:** CSC649 — Special Topics in Computer Science, Section `[TODO]`
- **Lecturer:** `[TODO]`

---

## 2. Abstract

Conventional face-recognition attendance systems can be defeated by a proxy — one student checking in on behalf of an absent classmate using a photo, video, or another person's stored face data. This project presents **ProxyGuard**, a liveness-aware attendance system that combines face recognition with multiple real-time liveness checks to confirm that the person checking in is physically present and actively responding, not a static image or a swapped-in face. The system layers continuous blink detection and a randomized head-movement challenge on top of face recognition (via pretrained face-embedding and facial-landmark models), and adds two safeguards found necessary during live testing: an **active face-continuity guard**, which prevents a recognized identity from silently transferring to a swapped-in face or a phone screen mid-challenge, and a **duplicate check-in bypass**, which detects an already-checked-in student before the liveness challenge runs to completion rather than after. A leave-one-out recognition experiment over the reference dataset measured a **2.4% false-accept rate at a 5.0% false-reject rate** under the system's tightened matching thresholds, versus **31.7% false accepts** at the original, looser thresholds — a roughly 13× reduction validating that design decision quantitatively. The system is delivered as two Flask web applications sharing one detection/liveness engine — a student-facing check-in kiosk and a lecturer-facing review dashboard with session analytics, a review workflow, and a rule-based recommendation assistant. `[TODO: extend with the liveness-challenge/continuity-bypass/duplicate-detection trial results once Table VI (Section 9) is populated from a live-trial session.]`

*(Target length: 150–250 words for the final IEEE abstract — trim once results are added.)*

---

## 3. Table of Contents

*(Generate automatically from headings once ported into Word/LaTeX. Section order:)*

1. Cover Page
2. Abstract
3. Table of Contents
4. List of Figures
5. List of Tables
6. List of Abbreviations
7. Introduction
8. Model Design & Development
9. Results
10. Discussion
11. Conclusion & Recommendations
12. References
13. Appendices
14. Submission Folder

---

## 4. List of Figures

`[TODO: insert as actual image figures once captured/drawn; list is a placeholder until then]`

- **Fig. 1.** ProxyGuard end-to-end check-in pipeline (Session Picker → ... → ProxyGuard Assistant) — see [[architecture]] "Check-in Pipeline".
- **Fig. 2.** `CheckinSession` flow-phase state machine (recognition → continuity → duplicate check → liveness → terminal outcome).
- **Fig. 3.** Student check-in kiosk — live MJPEG check-in page with the head-movement challenge in progress.
- **Fig. 4.** Student check-in kiosk — skeleton loading state during session startup.
- **Fig. 5.** Lecturer dashboard — Attempts tab with analytics cards and Reason Breakdown.
- **Fig. 6.** Lecturer dashboard — ProxyGuard Assistant recommendation panel.
- **Fig. 7.** Snapshot preview modal showing a verification snapshot for a flagged attempt.

---

## 5. List of Tables

- **Table I.** Face-recognition and liveness detection parameters/thresholds.
- **Table II.** Terminal check-in outcomes, their trigger condition, and the logged `result`/`reason`.
- **Table III.** Reference-image dataset composition (`data/known_faces/`).
- **Table IV.** Recognition FAR/FRR, tightened vs. original thresholds (measured — Section 9.2).
- **Table V.** Streaming / processing-time benchmark (measured — Section 9.2).
- **Table VI.** Liveness/continuity/duplicate-detection live-trial metrics. `[TODO — PENDING A LIVE-TRIAL SESSION, see Section 9.2]`

---

## 6. List of Abbreviations

| Abbreviation | Meaning |
|---|---|
| API | Application Programming Interface |
| CNN | Convolutional Neural Network |
| CSV | Comma-Separated Values |
| EAR | Eye Aspect Ratio |
| FAR | False Accept Rate |
| FPS | Frames Per Second |
| FRR | False Reject Rate |
| JPEG | Joint Photographic Experts Group (image format) |
| MJPEG | Motion JPEG (video streaming format) |
| ML | Machine Learning |
| UI | User Interface |
| UiTM | Universiti Teknologi MARA |

---

## 7. Introduction

### 7.1 Problem Statement
Conventional face-recognition attendance systems verify identity from a single static frame, which makes them vulnerable to **proxy attendance**: a registered student can be marked present by having a classmate hold up a printed photo, play back a video, or otherwise present stored face data to the camera on their behalf. Face recognition alone cannot distinguish a live, present person from a convincing static or replayed representation of one.

### 7.2 Project Objectives
- Recognize registered students from stored frontal reference images.
- Verify liveness through continuous blink detection and a randomized head-movement challenge, so a static image or frozen frame cannot pass.
- Ensure the recognized identity remains bound to the same physical, continuously-present face for the whole challenge, closing the loophole where a face could be swapped mid-attempt.
- Detect an already-completed check-in for the current session as early as possible, avoiding a wasted challenge and an inconsistent "confirmed" message for a duplicate attempt.
- Log every outcome (success, failure, duplicate) with a correctly attributed identity and a reviewable snapshot.
- Give a lecturer a fast, actionable way to review suspicious or ambiguous attendance records without any automated accept/reject decision.

### 7.3 Project Scope
The system covers a single-webcam check-in kiosk (student-facing web app) and a companion lecturer review dashboard (a separate, read-only web app), both built on a shared detection/liveness engine. It is scoped to **one active check-in station per camera** and to **within-session** duplicate detection (a student can legitimately check in again in a different class session). It does not cover multi-camera deployments, and does not (yet) defend against a live video call of the real student being held up to the camera — see Section 10.2 (Limitations).

### 7.4 Project Significance
Attendance integrity directly affects academic records, and manual attendance-taking does not scale in large classes. A face-recognition system without liveness verification can be defeated trivially with a photo, undermining the very integrity it is meant to provide. ProxyGuard demonstrates that meaningful anti-proxy protection — including two safeguards (face-continuity binding and pre-liveness duplicate detection) motivated directly by bypass attempts found during this project's own live testing, not just textbook threats — can be built with freely available, pretrained perception models and classical decision rules, without requiring custom model training or specialized hardware.

---

## 8. Model Design & Development

### 8.1 System Architecture
ProxyGuard is built as independent Python modules under `src/` (face detection, face recognition, liveness detection, attendance logging, pattern flagging), combined through a single shared check-in engine, `CheckinSession` (`src/main.py`). Two standalone Flask web applications sit on top of it:

- **`checkin_app/`** — the student-facing kiosk: a session picker (select class + week) followed by a live check-in page that streams the webcam (captured and processed server-side) into the browser as MJPEG.
- **`dashboard/`** — the lecturer-facing, read-only review app: attendance filtering, analytics, a snapshot review workflow, and a rule-based recommendation assistant.

Both entry points construct a `CheckinSession` and feed it frames, so every detection/liveness/logging fix applies to both automatically. See [[architecture]] for the full module and data-flow breakdown.

The end-to-end pipeline (Fig. 1):
```
Session Picker → Check-in UI → Face Detection → Identity Verification
    → Active Face Continuity → Duplicate Check → Liveness Challenge
    → Attendance Decision → Attendance Logger → Dashboard
    → Lecturer Review → ProxyGuard Assistant
```

### 8.2 Machine Learning / AI Algorithm
ProxyGuard does **not** train a custom classifier; it composes **pretrained perception models** with **classical geometric/statistical decision rules**, which keeps the system reproducible without a training pipeline or labeled training run of its own:

- **Face representation** — the `face_recognition` library (built on **dlib**), which encodes each detected face into a 128-dimensional embedding using a pretrained convolutional network in the FaceNet lineage (a deep CNN trained to map face images into a Euclidean embedding space where distance corresponds to face similarity) [1]–[3].
- **Facial landmark / mesh estimation** — **MediaPipe Face Mesh**, a pretrained CNN-based facial-landmark model, used for eye-landmark extraction (blink detection) and head-pose estimation [4].
- **Face detection (standalone module, `face_detector.py`)** — OpenCV's Haar Cascade classifier, a classical boosted-cascade detector [5].
- **Decision layer** — identity matching is **not** a trained classifier but a **nearest-neighbor distance threshold with a margin check**: a detected face's embedding is compared against every registered student's stored embedding(s) by Euclidean distance; the closest match is accepted only if it is within a fixed tolerance *and* separated from the second-closest candidate by a minimum margin (Table I). Liveness is decided by classical rules over the landmark output (Eye Aspect Ratio thresholding for blinks; normalized landmark-offset geometry for head-turn direction) — see [6] for the anti-spoofing literature this design follows.

### 8.3 Computational Method
- **Identity matching:** Euclidean distance between the live face's embedding and each stored reference embedding; accept the nearest match if `distance ≤ tolerance` **and** `(second-nearest distance − nearest distance) ≥ margin`; otherwise the face is `"Unknown"`.
- **Blink detection:** Eye Aspect Ratio (EAR), the ratio of vertical to horizontal eye-landmark distances [6]; a blink is counted when EAR drops below a threshold for at least *N* consecutive frames and then recovers.
- **Head-pose / direction:** normalized horizontal/vertical offset of the nose-tip landmark from the face center (derived from eye-corner and chin landmarks), thresholded into `left`/`right`/`up`/`down`/`center`.
- **Active face continuity:** a simple center-distance check between consecutive detected face boxes (not full object tracking) — a recognized identity is only kept bound to the same physical face while its box stays within a distance threshold of the last confirmed position and no different real identity is confirmed at that position.
- **Duplicate check-in:** a lookup (`has_success_this_session()`) against the session's own attendance rows, run once the recognized identity is confirmed stable by the continuity check above, before the liveness challenge is allowed to complete.

### 8.4 Features / Parameters
**Table I — Face-recognition and liveness parameters**

| Parameter | Value | Purpose |
|---|---|---|
| Face-match distance tolerance | 0.45 | Maximum embedding distance accepted as a match (tightened from an initial 0.5) |
| Minimum match margin | 0.1 | Minimum distance gap between best and second-best candidate (tightened from an initial 0.05) |
| EAR blink threshold | 0.21 | EAR value below which an eye is considered closed |
| Consecutive frames for a blink | 2 | Minimum consecutive low-EAR frames counted as one blink |
| Head-movement challenge duration | 10 s | Time window to complete the randomized directional challenge |
| Challenge directions | left, right, up | Randomized per attempt |
| Face-continuity jump threshold | 35% of frame width | Maximum face-center displacement tolerated as "the same face" |
| Consecutive-mismatch tolerance (continuity) | 2 checks | Stray misdetections tolerated before continuity is considered broken |
| Identity hold time (continuity) | 4.0 s | Maximum time without a re-confirming match before continuity is considered broken |
| Recognition sampling rate | every 3rd frame | Frame downsampling for the (comparatively) expensive recognition step |
| Recognition working resolution | 0.25× frame | Downscale factor for the recognition pass |
| Landmark (Face Mesh) working resolution | 0.5× frame | Downscale factor for the mediapipe pass |

### 8.5 Dataset
The registered-student reference set (`data/known_faces/`) contains **46 frontal images across 4 individuals**: 15 images each for the three group members and 1 image for one additional registered individual (Table III). Images are loaded through PIL with EXIF-based orientation correction (phone photos frequently store rotation as metadata rather than rotating the pixels) before being encoded. Running every image through `face_recognition.face_encodings()` (Section 9.1) found that **5 of the 46 images (10.9%) have no detectable face** and are silently skipped by `load_known_faces()` at load time (with a printed warning) — three of Amir's photos and two of Adli's — leaving **41 usable images** for both the live system and the Section 9 experiment. This is a real, measured data-quality finding, not a hypothetical one, and is noted as a limitation in Section 10.2. There is **no separate held-out test set of "attacker" images** (photos/phone-screen replays used to attempt a bypass) formally curated at this stage — testing against those threat models has so far been manual/ad hoc (see [[testing]] "Replay Attack / Phone Screen Tests"). `[TODO: this is a known gap — see Section 10.2; if time allows before submission, curate a small labeled test set of (a) genuine live check-in attempts per registered student, and (b) spoof attempts per threat type, so Table VI's metrics are computed from a fixed, reproducible set rather than ad hoc trials.]`

**Table III — Reference-image dataset composition**

| Subject | Images (total) | Usable (face detected) |
|---|---|---|
| Muhammad Amir Izzat bin Rosdi | 15 | 13 |
| Muhammad Adli Fadhlan bin Azame | 15 | 12 |
| Muhammad Izzuddin bin Izad Emi | 15 | 15 |
| (fourth registered individual) | 1 | 1 |
| **Total** | **46** | **41** |

### 8.6 Target / Labels
The recognition "label" for each detected face is the registered student's name, derived directly from the reference-image filename (a trailing `_N` suffix distinguishing multiple photos of the same person is stripped). An unmatched face is labeled `"Unknown"`. At the attendance-log level, each check-in attempt is labeled with a `result` (`success`/`failed`) and a `reason` (`confirmed`, `face not recognized`, `liveness timeout`, `duplicate check-in this session`, or the currently-unreachable `identity mismatch`) — see Table II.

**Table II — Terminal check-in outcomes**

| `flow_phase`                                  | Trigger                                            | Logged `result` | Logged `reason`                 |
| --------------------------------------------- | -------------------------------------------------- | --------------- | ------------------------------- |
| `confirmed`                                   | Recognized + liveness passed + continuity intact   | success         | confirmed                       |
| `not_recognized`                              | Liveness passed, face not recognized               | failed          | face not recognized             |
| `liveness_failed`                             | Challenge timed out                                | failed          | liveness timeout                |
| `duplicate_checkin`                           | Stable identity already has a success this session | failed          | duplicate check-in this session |
| `identity_mismatch` *(currently unreachable)* | Reserved for a removed voice-verification phase    | failed          | identity mismatch               |

### 8.7 Flowchart

**Fig. 2 — `CheckinSession` per-frame decision flow** (text-based; source content mirrors `src/main.py` and [[architecture]] exactly — port to a drawn flowchart image for final submission, keeping every decision/box below). Loop-backs and shared exit points are written as labeled references (e.g. "→ back to CAPTURE FRAME") rather than long connecting lines, since those don't stay aligned reliably in plain text.

```
[START]
   |
   v
[Session Picker: lecturer selects class + week]
   |
   v
[build session_id = YYYY-MM-DD_HHMM_<CODE>_Week<N>]
   |
   v
[Start check-in station: load face encodings, open webcam]
   |
   v
==================================================================
 LOOP: CAPTURE FRAME  (~20 frames/sec while streaming)
==================================================================
   |
   v
[Face Detection]  -- runs every 3rd frame only
   |
   v
<How many faces detected?>
   |
   |-- 0 faces ------------------------------> go to LOOP: CAPTURE FRAME
   |
   |-- more than 1 face
   |     |
   |     v
   |   [PAUSE challenge: freeze countdown timer]
   |   [Show: "Only one person allowed in frame,
   |          please ensure you are alone during check-in"]
   |     |
   |     +--------------------------------------> go to LOOP: CAPTURE FRAME
   |       (resumes with same target direction and full time
   |        once back down to exactly 1 face)
   |
   +-- exactly 1 face
         |
         v
       [Identity Verification: recognize_face()]
       [tolerance = 0.45, min_margin = 0.1]
         |
         v
       <Registered match found?>
         |
         |-- No (name = "Unknown") -----------> go to LOOP: CAPTURE FRAME
         |
         +-- Yes
               |
               v
             [Active Face Continuity Guard]
             [ - same name as the currently bound identity?      ]
             [ - face box within 35% of frame width of last       ]
             [   confirmed position?                              ]
             [ - if a multi-face frame just occurred: does this    ]
             [   frame CONFIDENTLY reconfirm the same identity?    ]
               |
               v
             <Continuity holds?>
               |
               |-- No
               |     |
               |     v
               |   [Clear identity; restart challenge from scratch]
               |   [Show: "Face changed or lost, please keep the
               |          same face in frame"]
               |     |
               |     +----------------------------> go to LOOP: CAPTURE FRAME
               |
               +-- Yes
                     |
                     v
                   [Duplicate Check]
                   [has_success_this_session(name, session_id)]
                   [-- reused from attendance_logger.py, not re-scanned here --]
                     |
                     v
                   <Already has a successful check-in
                    this session?>
                     |
                     |-- Yes
                     |     |
                     |     v
                     |   [LOCK -> duplicate_checkin]
                     |   [Liveness challenge is SKIPPED entirely]
                     |   [Show: "ALREADY CHECKED IN: <name>"]
                     |     |
                     |     v
                     |   go to TERMINAL OUTCOME (A) below
                     |
                     +-- No
                           |
                           v
                         [Liveness Challenge]
                         [ - continuous blink detection            ]
                         [   (EAR < 0.21 for >= 2 consecutive       ]
                         [    frames counts as one blink)           ]
                         [ - randomized head-turn direction         ]
                         [   (left / right / up), 10s window        ]
                           |
                           v
                         <Blink AND correct head-turn
                          completed within 10s?>
                           |
                           |-- No (10s elapses without both)
                           |     |
                           |     v
                           |   [LOCK -> liveness_failed]
                           |   [Show: "LIVENESS TEST FAILED"]
                           |     |
                           |     v
                           |   go to TERMINAL OUTCOME (A) below
                           |
                           +-- Yes
                                 |
                                 v
                               <At THIS instant: is identified_name set,
                                non-"Unknown", and continuity intact?>
                                 |
                                 |-- Yes --> confirmed_name := identified_name
                                 +-- No  --> confirmed_name := None
                                 |
                                 v
                               [LOCK -> liveness_success]
                               [Show: "LIVENESS DETECTION SUCCESSFUL" for a
                                       fixed 2-second banner -- confirmed_name
                                       is NOT re-evaluated during this wait]
                                 |
                                 v (after the fixed 2 seconds)
                               <Was confirmed_name set above?>
                                 |
                                 |-- Yes
                                 |     |
                                 |     v
                                 |   [LOCK -> confirmed]
                                 |   [Show: "ATTENDANCE CONFIRMED: <name>"]
                                 |     |
                                 |     v
                                 |   go to TERMINAL OUTCOME (A) below
                                 |
                                 +-- No
                                       |
                                       v
                                     [LOCK -> not_recognized]
                                     [Show: "LIVENESS DETECTION SUCCESSFUL,
                                             BUT FACE NOT RECOGNIZED"]
                                       |
                                       v
                                     go to TERMINAL OUTCOME (A) below


==================================================================
 TERMINAL OUTCOME (A)
 -- reached from exactly one of: confirmed | not_recognized |
    liveness_failed | duplicate_checkin --
==================================================================
   |
   v
[log_attendance(name, result, reason, session_id)]
[  -> appends one row to logs/attendance.csv          ]
[  -> a "success" is downgraded to "failed" /           ]
[     "duplicate check-in this session" if a prior      ]
[     success already exists for this session (belt-    ]
[     and-suspenders alongside the Duplicate Check       ]
[     above, which already stops most duplicates earlier)]
   |
   v
[Save verification snapshot (pre-overlay frame)]
[  -> logs/snapshots/<session_id>_<name>_<reason>_<HHMMSS>.jpg ]
   |
   v
[Show restart hint / enable "New check-in" button]
   |
   v
<Lecturer/student triggers "New check-in" (reset)?>
   |
   +-- Yes --> fresh attempt --> go to LOOP: CAPTURE FRAME
   |
   +-- (not yet) --> stays on terminal screen, still polled by
                     the dashboard's smart refresh in the background


==================================================================
 INDEPENDENT, ONGOING: LECTURER DASHBOARD
 (separate read-only Flask app; not part of the loop above)
==================================================================
   |
   v
[Poll attendance.csv / reviews.csv / snapshots -- smart refresh]
   |
   v
[Present / Attempts tabs, session + quick + review filters,
 search, analytics cards, Reason Breakdown]
   |
   v
[Snapshot preview modal]  <---------------------+
   |                                            |
   v                                            |
[Lecturer Review: Accept / Suspicious + note]---+  (updates
   |                                               logs/reviews.csv,
   v                                               never attendance.csv)
[ProxyGuard Assistant: rule-based recommendation
 cards over the same session data -- "View affected
 attempts" / "Open next unreviewed attempt"]
```

`[TODO: port this text flowchart into a drawn diagram (e.g. draw.io/Lucidchart/PowerPoint shapes) for the final IEEE figure — the box/decision/arrow content above is the exact source to redraw from, cross-checked against src/main.py.]`

---

## 9. Results

Recognition FAR/FRR and streaming throughput below are **measured**, not estimated (methodology in 9.1; raw output preserved in `src/experiment_far_frr.py`, runnable directly with `python3 src/experiment_far_frr.py`). Liveness-challenge, continuity, and duplicate-detection *trial-count* statistics still require a live person at the camera performing real blinks/head turns and are marked `[TODO]` in 9.2 — see [[testing]] for the qualitative (pass/fail, not trial-count) verification already done for those.

### 9.1 Experimental Results

**Recognition FAR/FRR (leave-one-out over the real reference dataset).** Since no live-camera trials were available in this environment, identity-matching performance was measured with a standard **leave-one-out identification protocol** run directly against `data/known_faces/` (41 usable images across 4 subjects, after 5 images with no detectable face were excluded — see Section 8.5), reusing `face_recognizer.recognize_face()` unmodified so the numbers reflect the exact production code path:
- **Genuine trial** (one per usable image, except a subject's only image where leave-one-out can't leave a fair gallery — this excluded 1 of `shahmizan`'s images, giving 40 genuine trials): the probe image is matched against a gallery of every *other* image, including the same subject's remaining photos. A miss is a **false reject**.
- **Impostor trial** (one per usable image, 41 total): the probe image is matched against a gallery with **every** image of that subject's own identity removed, simulating an unregistered person. Any non-`"Unknown"` result is a **false accept**.

This was run twice: once at the system's current thresholds (tolerance 0.45, margin 0.1), and once at the original, looser thresholds from before Decision 5's tightening (tolerance 0.5, margin 0.05), to directly quantify what that decision bought.

**Streaming performance.** `CheckinSession.process_frame()` was timed over 60 consecutive live-webcam frames (`src/experiment_far_frr.py::measure_streaming_perf`), exercising the exact recognition/mediapipe/drawing code path `checkin_app` streams from.

**Not yet measured (requires a live person at the camera):** liveness challenge pass rate under genuine vs. spoofed (photo/replay) conditions, live continuity-guard bypass trials (the four scenarios in `src/test_face_continuity.py` have only been verified with synthetic recognition results, not live video — see [[testing]]), and duplicate-detection latency as an actual measured wall-clock time. `[TODO]`

### 9.2 Performance Metrics

**Table IV — Recognition FAR/FRR, tightened vs. original thresholds**

| Threshold setting | Genuine trials | FRR | Impostor trials | FAR |
|---|---|---|---|---|
| **Current (tolerance 0.45, margin 0.1)** | 40 | **5.0%** (2/40 missed) | 41 | **2.4%** (1/41 false-accepted) |
| Original (tolerance 0.5, margin 0.05) | 40 | 2.5% (1/40 missed) | 41 | 31.7% (13/41 false-accepted) |

Tightening the thresholds (Decision 5) cut FAR by roughly **13×** (31.7% → 2.4%) at the cost of raising FRR by only 2.5 percentage points (2.5% → 5.0%) — a large, measured security gain for a small usability cost, directly confirming the reasoning recorded in [[decisions]] Decision 5. The recurring confusion in both runs was between the two visually-similar group members (Adli and Izzuddin): at the original thresholds this pair alone accounted for 12 of the 13 false accepts; at the tightened thresholds only one of these (`MUHAMMAD ADLI FADHLAN BIN AZAME_6.JPG`, misread as Izzuddin) survived, appearing as both the one genuine miss for Adli *and* the one impostor false-accept.

**Table V — Streaming / processing-time benchmark**

| Metric | Value |
|---|---|
| Frames measured | 60 (live webcam) |
| Average processing time per frame | 18.8 ms |
| Estimated throughput | ~53 FPS |

This is the raw `process_frame()` cost (recognition every 3rd frame + mediapipe + drawing), not gated by `checkin_app`'s own ~20 FPS stream cap ([[architecture]] "Frame handling / streaming") — the ~53 FPS figure shows the engine runs comfortably under that cap on this hardware, with headroom rather than being the bottleneck.

**Table VI — Liveness / continuity / duplicate-detection metrics** `[TODO — pending a live-trial session]`

| Metric | Value | Trials (N) |
|---|---|---|
| Liveness pass rate (genuine) | — | — |
| Liveness pass rate (spoof) | — | — |
| Duplicate-detection latency (measured) | — | — |

### 9.3 Screenshots / Graphs / Tables
`[TODO: insert]` — recommended captures: the live check-in page mid-challenge; the skeleton loading state; the dashboard's Attempts tab with a flagged row and its snapshot preview open; the ProxyGuard Assistant panel; a bar chart of Table IV.

---

## 10. Discussion

### 10.1 Analysis of Results
The measured leave-one-out results (Table IV) confirm the reasoning behind Decision 5's threshold tightening was correct, and quantify it for the first time: at the original thresholds (tolerance 0.5, margin 0.05), **31.7% of impostor trials were falsely accepted** — an unacceptable false-accept rate for an attendance-integrity system, dominated almost entirely by confusion between two visually similar group members. Tightening to the current thresholds (0.45/0.1) cut that to **2.4%**, a roughly 13× reduction, while false rejections rose only from 2.5% to 5.0%. For an attendance system the asymmetry is the right one to accept: a false reject just means a legitimate student retries the challenge, while a false accept is a proxy slipping through undetected — exactly the tradeoff [[decisions]] Decision 5 argues for, now backed by a measured number instead of a single anecdotal incident. The one remaining recurring error at the tightened setting (Adli ↔ Izzuddin) suggests the residual risk is concentrated in a specific pair of visually similar individuals rather than spread evenly across the dataset, which points toward adding more/better reference photos for that pair specifically rather than tightening thresholds further (which would only push FRR higher project-wide for a problem localized to two people). The streaming benchmark (Table V, ~53 FPS raw throughput vs. a ~20 FPS stream cap) confirms the performance tuning in [[bugs]] Bug 6/Bug 7 left comfortable headroom rather than the engine being the bottleneck. `[TODO: extend once Table VI's live liveness/continuity/duplicate-detection trials are run.]`

### 10.2 Strengths & Limitations
**Strengths**
- Two anti-proxy safeguards (active face continuity, pre-liveness duplicate detection) were added directly in response to real bypasses found during live testing, not just anticipated on paper — see [[bugs]] (Bug 9, Bug 12) and [[decisions]] (Decision 11, Decision 12).
- The Decision 5 threshold tightening is now backed by a measured result (Section 9.2), not just a single incident report: a ~13× FAR reduction for a 2.5-point FRR cost.
- Every terminal outcome (success, failure, or duplicate) is logged with a correctly attributed identity and a matching verification snapshot, giving a lecturer a manual audit trail even when automated checks are uncertain.
- The lecturer dashboard's review workflow and rule-based Assistant give actionable oversight without any automated accept/reject authority — every flag is decision support, never a verdict.

**Limitations**
- **Live video-call replay is not addressed.** A live video call of the real, registered student held up to the camera can genuinely blink and turn its head on command, so it passes both the continuity guard (same face, same position) and the liveness challenge. This is a distinct threat from the swapped-photo/face-swap loophole the continuity guard closes.
- **Small, single-source reference dataset with a measured data-quality gap.** All current reference images are self-collected by the group; 5 of 46 (10.9%) had no detectable face at all (Section 8.5), and the residual recognition error is concentrated in one visually-similar pair of individuals — recognition performance under more varied real-world lighting/camera conditions, or a larger subject pool, is not yet characterized.
- **No formal held-out attack dataset yet** (Section 8.5) for the liveness/continuity/duplicate-detection layers specifically — Table IV/V's recognition and throughput numbers are real and measured, but Table VI (liveness pass rate, live continuity-bypass trials, duplicate-detection latency) still needs a live-trial session with a person at the camera.
- Attendance storage is CSV-based, which is adequate at current scale but would need to move to a database for larger deployments (see [[decisions]] Decision 2).

### 10.3 Comparison
The threshold comparison in Table IV (current tightened thresholds vs. the original, looser Decision-5-era thresholds) is a real, measured comparison and is analyzed in 10.1 above. A second, still-outstanding comparison — bypass success rate with **liveness checks enabled** vs. a **face-recognition-only baseline** (liveness/continuity/duplicate checks disabled) against the same spoof attempts — would directly quantify the marginal protection the liveness layer adds over a conventional face-recognition-only attendance system. `[TODO: run once a live-trial session is available; the baseline condition can be produced by temporarily short-circuiting `CheckinSession`'s liveness/continuity checks, not a separate system.]`

### 10.4 Findings
- Face-embedding distance thresholding, tuned with a real measured trade-off (Section 9.2/10.1), is sufficient to keep impostor acceptance low (2.4% measured) without an unreasonable legitimate-user cost (5.0% measured FRR) on the current reference set.
- The dataset's own quality varies enough to matter: measurable face-detection failures (10.9% of images) and subject-pair confusability are both real, quantifiable properties of *this* dataset, not just recognition-algorithm behavior in the abstract.
- The streaming pipeline has real throughput headroom (~53 FPS raw vs. ~20 FPS target), so future feature additions to `process_frame()` have room before the stream cap itself becomes the limiting factor.
- `[TODO: add liveness/continuity/duplicate-detection findings once Table VI is populated.]`

---

## 11. Conclusion & Recommendations

### 11.1 Project Conclusion
ProxyGuard demonstrates that a proxy-resistant attendance system can be built from pretrained face-embedding and facial-landmark models combined with classical liveness and continuity rules, without training a custom model. Beyond the originally planned blink-and-head-movement liveness challenge, live testing surfaced two real bypass patterns — identity transfer to a swapped-in face, and a duplicate check-in running a full (and misleading) liveness challenge before being downgraded — both of which were closed with dedicated, tested safeguards (active face continuity and a pre-liveness duplicate check). A measured leave-one-out experiment confirms the project's face-matching threshold decision was correct: false accepts fell roughly 13× (31.7% → 2.4%) for a 2.5-point false-reject cost, and the shared processing engine runs with comfortable throughput headroom (~53 FPS raw vs. a ~20 FPS streaming target). The system is delivered end-to-end: a student-facing check-in kiosk and a lecturer-facing review dashboard, sharing one detection engine so every fix applies identically to both. `[TODO: extend once Table VI's live liveness/continuity/duplicate-detection trial results are available.]`

### 11.2 Future Improvements / Future Work
- **Screen/replay detection** (e.g., moiré-pattern or screen-reflection detection) to address the live-video-call replay limitation (Section 10.2).
- **Move attendance storage from CSV to a database** (e.g., SQLite) if querying needs grow beyond what CSV comfortably supports.
- **Reintegrate the voice challenge** (`src/voice_challenge.py`, built but currently unused) as an additional active liveness factor if flow-reliability concerns are resolved.
- **Expand the reference dataset and curate a labeled attack test set** to support a larger-scale, reproducible performance evaluation than Section 9's initial measurements.

See [[roadmap]] for the full, currently-tracked list.

---

## 12. References

Use IEEE citation style (numbered, in order of first appearance in the text). Core methodology references:

[1] P. Viola and M. Jones, "Rapid object detection using a boosted cascade of simple features," in *Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR)*, Kauai, HI, USA, 2001, pp. 511–518, doi: 10.1109/CVPR.2001.990517.

[2] D. E. King, "Dlib-ml: A machine learning toolkit," *J. Mach. Learn. Res.*, vol. 10, pp. 1755–1758, 2009.

[3] F. Schroff, D. Kalenichenko, and J. Philbin, "FaceNet: A unified embedding for face recognition and clustering," in *Proc. IEEE Conf. Comput. Vis. Pattern Recognit. (CVPR)*, Boston, MA, USA, 2015, pp. 815–823, doi: 10.1109/CVPR.2015.7298682.

[4] C. Lugaresi et al., "MediaPipe: A framework for building perception pipelines," *arXiv preprint*, arXiv:1906.08172, 2019.

[5] T. Soukupová and J. Čech, "Real-time eye blink detection using facial landmarks," in *Proc. 21st Comput. Vis. Winter Workshop (CVWW)*, 2016.

[6] J. Galbally, S. Marcel, and J. Fierrez, "Biometric antispoofing methods: A survey in face recognition," *IEEE Access*, vol. 2, pp. 1530–1552, 2014, doi: 10.1109/ACCESS.2014.2381273.

`[TODO: add any further literature the group cites in the final prose (e.g., specific attendance-system or proxy-detection papers found during the literature review), keeping IEEE numbered order.]`

---

## 13. Appendices

`[TODO, if applicable]` — candidates: full parameter list beyond Table I, additional dashboard/kiosk screenshots, full test-case listing (can reference [[testing]] directly instead of duplicating it).

---

## 14. Submission Folder (CD / Google Drive)

Checklist — none of these are page-limited, but all are required in the submission folder:

- [ ] **Dataset** — `data/known_faces/` (see Section 8.5/Table III).
- [ ] **Experimental Data** — `src/experiment_far_frr.py` (rerunnable: `python3 src/experiment_far_frr.py`) plus its saved console output for Table IV/V; once Table VI's live trials are run, add the raw `logs/attendance.csv` from that trial session alongside any manually-recorded trial sheet.
- [ ] **Survey Form** *(if applicable)* — `[TODO: not currently part of this project; omit if not required]`.
- [ ] **Source Code** — this repository (`src/`, `checkin_app/`, `dashboard/`).
- [ ] **Final Report** — PDF and Word versions, ported from this file into the IEEE template.
- [ ] **Video Presentation** — `[TODO: record and link once the report content above is finalized]`.

---

## Related Documentation

- [[project-overview]]
- [[architecture]]
- [[roadmap]]
- [[decisions]]
- [[testing]]
- [[bugs]]
- [[CLAUDE]]
