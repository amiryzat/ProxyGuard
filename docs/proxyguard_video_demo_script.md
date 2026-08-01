# ProxyGuard Video Demo Script

**Target duration:** 8 minutes 30 seconds  
**Style inspiration:** Veritasium, Vox, ML Studios  
**Presenter:** One group member handles the full narration  
**Format:** Presenter footage mixed with screen recordings, close-ups, text overlays, diagrams, and short system clips

---

## Phase 1 — Opening Hook

**Time:** 0:00–0:25

### Script

Imagine someone walks into class with a photo of their friend, holds it in front of an attendance camera… and the system marks that friend as present.

That is the problem we wanted to solve.

So we built ProxyGuard, a face-recognition attendance system that does not only ask, “Who are you?” It also asks, “Are you actually here, right now?”

### Editing Flow

| Time | Visual |
|---|---|
| 0:00–0:04 | Close-up of a phone displaying a face being held toward a webcam |
| 0:04–0:07 | Quick fake attendance confirmation or green-check animation |
| 0:07–0:10 | Presenter says: “That is the problem we wanted to solve.” |
| 0:10–0:15 | Fast shots of camera feed, face box, blink detection, and head movement |
| 0:15–0:21 | On-screen text: **Who are you?** |
| 0:21–0:25 | Text changes to **Are you actually here?** followed by the ProxyGuard title |

### On-Screen Text

- A photo can fool basic face attendance.
- Who are you?
- Are you actually here?
- **PROXYGUARD**
- Liveness-Aware Attendance Verification

### Transition

This leads naturally into why ordinary face recognition is not enough.

---

## Phase 2 — Why Face Recognition Alone Is Not Enough

**Time:** 0:25–1:05

### Script

Face recognition sounds secure because the system can identify a person from their face.

But identification alone does not prove that the real person is standing in front of the camera. A photo can still contain the correct face. A video replay can still blink. And once a system recognizes someone, it may continue trusting that identity even if the real person moves away.

So the real problem is not just recognition.

It is presence.

ProxyGuard combines face recognition with a live challenge, duplicate checking, multiple-face detection, and identity continuity. The goal is simple: accept the real student, reject suspicious attempts, and keep enough evidence for the lecturer to review what happened.

### Editing Flow

| Time | Visual |
|---|---|
| 0:25–0:32 | Presenter: “Face recognition sounds secure…” |
| 0:32–0:38 | Registered face being recognized correctly |
| 0:38–0:44 | Phone photo or replay footage near the camera |
| 0:44–0:49 | Freeze-frame on recognized name while the real person leaves |
| 0:49–0:54 | Large text: **Recognition ≠ Presence** |
| 0:54–1:01 | Montage: blink, head turn, duplicate warning, two-face warning |
| 1:01–1:05 | Dashboard snapshot and review footage |

### On-Screen Text

- Face recognition answers: **Whose face is this?**
- But not: **Is this person really here?**
- **RECOGNITION ≠ PRESENCE**
- Recognize → Verify → Record → Review

### Transition

To understand how ProxyGuard handles this, we first need to look at how the system is structured.

---

## Phase 3 — How ProxyGuard Works

**Time:** 1:05–1:55

### Script

Think of ProxyGuard as a chain of checkpoints. Passing one checkpoint does not automatically mean attendance is approved.

First, the camera captures the live video and looks for a face. OpenCV handles the video stream, while the face-recognition library compares that face with the registered students in the system.

But recognition is only the first gate. The identity has to remain stable for several frames, so one quick or unclear match is not enough.

Once the identity is stable, ProxyGuard checks whether that student has already attended the current session. If they have, the system stops the attempt immediately and records it as a duplicate.

If not, the student moves to the liveness challenge. MediaPipe tracks facial landmarks while the system asks for a blink and a random head movement. At the same time, ProxyGuard watches whether the same physical face remains in control of the challenge.

Finally, the system decides whether to confirm or reject the attempt, then saves the result, timing, reason, and snapshot for the lecturer dashboard.

### Editing Flow

| Time | Visual |
|---|---|
| 1:05–1:10 | Presenter: “Think of ProxyGuard as a chain of checkpoints.” |
| 1:10–1:16 | Camera feed with face box appearing |
| 1:16–1:23 | Live face compared with enrolled face images |
| 1:23–1:29 | Stable-recognition progress animation |
| 1:29–1:35 | Duplicate-check icon or existing attendance row |
| 1:35–1:43 | Blink and randomized head-turn instruction |
| 1:43–1:49 | Phone or second face entering frame; challenge pauses |
| 1:49–1:55 | Result logged, snapshot saved, dashboard updated |

### On-Screen Flow

Camera  
↓  
Face Detection  
↓  
Identity Recognition  
↓  
Stability Check  
↓  
Duplicate Check  
↓  
Liveness Challenge  
↓  
Attendance Decision  
↓  
Dashboard and Evidence

### Strong Labels

- Gate 1 — Who is this?
- Gate 2 — Is the identity stable?
- Gate 3 — Already checked in?
- Gate 4 — Is this a live, continuous face?
- Confirm or Reject

### Transition

And for that recognition stage to work reliably during different head movements, the system needs more than one straight-facing image of each student.

---

## Phase 4 — Face Enrollment Dataset

**Time:** 1:55–2:30

### Script

For face enrollment, we created a small multi-pose dataset for three registered participants.

Each person contributed fifteen images: three facing forward, three looking down, three facing right, three facing left, and three looking up.

That gives us forty-five enrollment images in total.

These images are not used to train a new artificial-intelligence model. Instead, the system converts each face into a numerical encoding and uses those encodings as references during live recognition.

The different head directions matter because the liveness challenge asks users to move naturally. A system trained on only one front-facing image would be much more likely to lose the identity during those movements.

We also used two additional participants as unknown users. Their faces were deliberately excluded from enrollment so we could test whether the system rejects people who are not registered.

### Editing Flow

| Time | Visual |
|---|---|
| 1:55–2:00 | Grid of the five head directions |
| 2:00–2:10 | Animate 3 images per direction for one participant |
| 2:10–2:15 | Counter appears: **15 images per participant** |
| 2:15–2:19 | Counter changes to **45 total enrollment images** |
| 2:19–2:25 | Simple animation of images becoming face encodings |
| 2:25–2:30 | U1 and U2 silhouettes labelled **Not Enrolled** |

### On-Screen Text

- 3 registered participants
- 15 images per participant
- 5 head directions
- 45 enrollment images
- 2 unknown evaluation participants
- Reference encodings, not model training

### Transition

Once the system knows what each registered participant looks like from several angles, it can move on to the harder part: proving that the person is genuinely present.

---

## Phase 5 — Liveness, Continuity, and Security Logic

**Time:** 2:30–3:25

### Script

ProxyGuard uses two main liveness actions: a blink and a randomized head movement.

The random instruction matters because a fixed movement is easy to predict or prepare in advance. One attempt may ask the user to turn left, while another may ask them to turn right.

But liveness alone is not enough.

Imagine the system recognizes a real student, starts the challenge, and then someone replaces that student with a phone image. If the system keeps trusting the original identity, the attack could still succeed.

So ProxyGuard tracks identity continuity. It checks whether the same face remains in roughly the same position and maintains control of the challenge.

If another face enters the frame, the challenge pauses. If the original identity disappears or the face box suddenly transfers to another subject, the system breaks the continuity instead of blindly continuing.

This is also why failed liveness attempts still keep the recognized student’s name. The lecturer can see who was recognized, what failed, and why the attempt was rejected.

### Editing Flow

| Time | Visual |
|---|---|
| 2:30–2:38 | Blink and random left/right instruction |
| 2:38–2:45 | Random selector animation |
| 2:45–2:53 | Real participant recognized, then phone begins replacing them |
| 2:53–3:00 | Bounding box continuity visual |
| 3:00–3:08 | Second face enters; challenge pauses |
| 3:08–3:16 | Identity continuity broken; attempt rejected |
| 3:16–3:25 | Dashboard row retaining registered name with failed-liveness reason |

### On-Screen Text

- Random challenge
- Same identity
- Same physical face
- Multiple faces → Pause
- Identity transfer → Block
- Failed liveness still keeps the recognized name

### Transition

With that technical logic in place, the next question is whether the system actually behaves as expected under controlled tests.

---

## Phase 6 — Evaluation Method

**Time:** 3:25–4:10

### Script

To evaluate the prototype, we used five participants: three registered users and two unknown users.

The registered participants were tested for genuine check-in, deliberate liveness failure, duplicate attendance, and photo-based attacks. The unknown participants were used to test whether the system rejects faces that were never enrolled.

Before each trial, the tester only selects the participant and scenario. Everything else is automatic.

The system starts the timer when a valid face appears, records the recognition time and total decision time, captures the final result, compares it with the expected outcome, and marks the trial as pass or fail.

From these trials, ProxyGuard calculates metrics such as face-recognition accuracy, genuine acceptance rate, false rejection rate, unknown rejection rate, duplicate-detection rate, photo-attack rejection rate, and average decision time.

Because this is a small prototype evaluation, the results should be understood as controlled testing rather than large-scale deployment performance.

### Editing Flow

| Time | Visual |
|---|---|
| 3:25–3:31 | Show participant codes R1, R2, R3, U1, U2 |
| 3:31–3:39 | Scenario selector in Evaluation Mode |
| 3:39–3:46 | Start Trial and in-camera timer |
| 3:46–3:53 | Expected versus actual comparison |
| 3:53–4:02 | PASS/FAIL and metrics cards updating |
| 4:02–4:10 | Small caption: **Controlled prototype evaluation — 5 participants** |

### On-Screen Text

- 3 registered participants
- 2 unknown participants
- Automatic timing
- Expected vs actual
- Automatic PASS/FAIL
- Report-ready metrics

### Transition

Now that the technical design and evaluation method are clear, we can see the system working from start to finish.

---

## Phase 7 — Live Demo: Session Setup and Genuine Check-In

**Time:** 4:10–5:00

### Script

The lecturer begins by selecting a subject and week, then starts the attendance session.

The camera loads the known-face encodings and prepares the recognition engine.

When a registered student enters the frame, ProxyGuard first identifies the face and waits for that identity to become stable.

The student is then asked to blink and complete a randomized head movement.

Once both checks are completed, attendance is confirmed. The system stores the student’s name, session, result, reason, snapshot, and decision time.

### Editing Flow

| Time | Visual |
|---|---|
| 4:10–4:18 | Session picker: choose subject and week |
| 4:18–4:22 | Click **Start Session** |
| 4:22–4:25 | Brief loading clip; cut past long startup |
| 4:25–4:32 | Registered student enters frame |
| 4:32–4:40 | Identity stabilizes |
| 4:40–4:48 | Blink and random head movement |
| 4:48–4:55 | Attendance confirmed |
| 4:55–5:00 | Snapshot and timing data saved |

### On-Screen Text

- Session started
- Identity stable
- Blink detected
- Random movement completed
- Attendance confirmed
- Decision time recorded

### Editing Note

Do not show the full camera startup delay. Show one or two seconds, then cut to the ready camera screen. Add a small caption:

**Startup shortened for presentation**

### Transition

A successful check-in is the expected path. The more interesting part is what happens when the same person tries again.

---

## Phase 8 — Live Demo: Duplicate, Failed Liveness, and Proxy Protection

**Time:** 5:00–6:20

### Script

If the same student tries to check in again during the same session, ProxyGuard recognizes the identity and checks the existing attendance log.

Because that student already has a confirmed record, the system stops the attempt and marks it as a duplicate without requiring another full liveness challenge.

Next, we deliberately fail the liveness test.

The student is still recognized correctly, but because the required movement is not completed within the allowed time, the attempt is rejected as a liveness timeout.

Notice that the system keeps the recognized student’s name instead of changing it to Unknown. That gives the lecturer more useful evidence.

We also test a proxy-style situation by introducing another face or a phone image into the frame.

When multiple faces appear, the challenge pauses. If the active face is replaced, the identity-continuity check prevents the new face from continuing with the original student’s identity.

### Live Video-Call Replay Test

#### Script

To test a more advanced proxy attempt, we used a live video call instead of a static photo.

A registered participant joined the call remotely, while another person held the phone in front of the attendance camera.

Unlike a photo, the person on the screen can react in real time. They can blink, turn their head, and follow the randomized instruction shown by ProxyGuard.

This makes the attack much harder to detect using ordinary liveness checks alone.

During the test, we recorded whether the registered identity was recognized, whether the liveness challenge was completed, and whether attendance was confirmed.

#### Use This Ending if the Attack Succeeds

> In this case, the remote participant passed the system checks and attendance was confirmed. This reproduces a known limitation of the current prototype: randomized blink and head-movement challenges cannot reliably distinguish a live person behind the camera from a live person displayed through a video call.

#### Use This Ending if the Attack Is Rejected

> In this test, the attempt was rejected before attendance was confirmed. However, one rejected trial is not enough to claim that ProxyGuard can reliably detect live video-call replays. Further testing and stronger presentation-attack detection would still be required.

### Editing Flow

| Time | Visual |
|---|---|
| 5:00–5:18 | Same participant attempts again; duplicate detected |
| 5:18–5:23 | Dashboard duplicate row appears |
| 5:23–5:45 | Registered participant intentionally fails liveness |
| 5:45–5:52 | Timeout shown with correct registered name |
| 5:52–6:02 | Phone image or second face enters |
| 6:02–6:10 | Multiple-face warning and challenge pause |
| 6:10–6:20 | Identity continuity blocks transfer; no success |

### On-Screen Text

- Duplicate detected before full liveness
- Recognized identity retained
- Liveness timeout
- Multiple faces → Challenge paused
- Identity transfer blocked

### Transition

Every one of these outcomes is recorded, but the lecturer still needs a practical way to understand and review them.

---

## Phase 9 — Dashboard, Review Workflow, and Assistant

**Time:** 6:20–7:35

### Script

The lecturer dashboard separates confirmed attendance from failed or suspicious attempts.

The Present tab shows students who successfully completed verification, while the Attempts tab contains duplicates, unknown users, liveness failures, and other blocked events.

The dashboard updates automatically when new attendance records appear. The lecturer can filter attempts by reason, search for a student, inspect the snapshot, and view session-level analytics.

ProxyGuard does not automatically accuse a student of proxy attendance.

Instead, suspicious attempts enter a review workflow. The lecturer can inspect the evidence, mark an attempt as accepted or suspicious, and add a note explaining the decision.

A rule-based assistant also summarizes the session and highlights areas that may need attention, such as repeated duplicate attempts, unresolved reviews, or a high number of liveness failures.

### Editing Flow

| Time | Visual |
|---|---|
| 6:20–6:28 | Present and Attempts tabs |
| 6:28–6:38 | New record appears automatically |
| 6:38–6:47 | Search and quick filters |
| 6:47–6:56 | Open snapshot preview |
| 6:56–7:08 | Mark attempt Accepted or Suspicious and add note |
| 7:08–7:18 | Review status updates |
| 7:18–7:28 | Open floating assistant |
| 7:28–7:35 | Assistant recommendation links to affected attempts |

### On-Screen Text

- Present
- Attempts
- Snapshot evidence
- Lecturer review
- Accepted / Suspicious
- Human decision remains final

### Transition

The same system also turns the controlled trials into measurable results for the final evaluation.

---

## Phase 10 — Evaluation Results

**Time:** 7:35–8:10

### Script

The Evaluation Mode collects each trial separately from the operational attendance log.

For every test, it stores the participant code, scenario, expected identity, expected result, actual outcome, reason, recognition time, total decision time, and pass-or-fail status.

The results page then calculates the performance metrics automatically.

For example, recognition accuracy measures whether the correct registered identity was found. Genuine acceptance rate measures how often valid users completed the entire process successfully. False rejection rate captures genuine users who were incorrectly rejected, while unknown rejection rate measures whether unregistered participants were blocked.

Timing is also separated by outcome. This allows us to compare a normal check-in with faster decisions such as duplicate detection or longer outcomes such as a liveness timeout.

### Editing Flow

| Time | Visual |
|---|---|
| 7:35–7:43 | Evaluation setup with participant and scenario |
| 7:43–7:50 | In-camera timer |
| 7:50–7:57 | Expected versus actual result |
| 7:57–8:04 | Metric cards |
| 8:04–8:10 | Results table and CSV export |

### On-Screen Text

- Recognition Accuracy
- Genuine Acceptance Rate
- False Rejection Rate
- Unknown Rejection Rate
- Duplicate Detection Rate
- Photo Attack Rejection Rate
- Mean Decision Time

### Editing Note

Replace generic metric names with the actual final percentages after all participant testing is complete.

### Transition

The results show what the current prototype can do, but they also reveal where the system still has limits.

---

## Phase 11 — Conclusion and Limitations

**Time:** 8:10–8:40

### Script

ProxyGuard shows that attendance verification becomes much stronger when identity recognition is combined with liveness, duplicate detection, identity continuity, evidence logging, and human review.

The prototype can confirm genuine students, reject unknown users, detect repeated attendance, preserve useful evidence for failed liveness attempts, and interrupt suspicious face-transfer situations.

However, it is still a prototype.

The evaluation uses only five participants, and more testing would be needed across different lighting conditions, cameras, distances, and larger student populations.

Live video-call replay also remains an important limitation. Because a real remote person can blink and follow a randomized instruction through a screen, stronger presentation-attack detection would be required in future work.

Even with those limits, ProxyGuard demonstrates a practical direction for making face-based attendance more accountable, explainable, and resistant to simple proxy attempts.

### Editing Flow

| Time | Visual |
|---|---|
| 8:10–8:18 | Fast recap montage of successful and blocked scenarios |
| 8:18–8:25 | Text: **What ProxyGuard adds** |
| 8:25–8:32 | Limitations appear one at a time |
| 8:32–8:37 | Presenter delivers final sentence |
| 8:37–8:40 | ProxyGuard logo/title and group names |

### On-Screen Text

**What ProxyGuard adds**

- Identity verification
- Liveness challenge
- Identity continuity
- Duplicate protection
- Evidence and review

**Current limitations**

- Small evaluation group
- Limited environmental testing
- Live video-call replay
- Prototype-scale CSV storage

### Final Screen

**PROXYGUARD**  
Liveness-Aware Face Recognition for Proxy Attendance Detection

---

# Full Timing Summary

| Phase | Section | Time |
|---|---|---:|
| 1 | Opening Hook | 0:00–0:25 |
| 2 | Why Recognition Is Not Enough | 0:25–1:05 |
| 3 | How ProxyGuard Works | 1:05–1:55 |
| 4 | Face Enrollment Dataset | 1:55–2:30 |
| 5 | Liveness and Identity Continuity | 2:30–3:25 |
| 6 | Evaluation Method | 3:25–4:10 |
| 7 | Session Setup and Genuine Check-In | 4:10–5:00 |
| 8 | Duplicate, Failed Liveness, and Proxy Protection | 5:00–6:20 |
| 9 | Dashboard, Review, and Assistant | 6:20–7:35 |
| 10 | Evaluation Results | 7:35–8:10 |
| 11 | Conclusion and Limitations | 8:10–8:40 |

**Estimated total:** 8 minutes 40 seconds

---

# Presenter Notes

- Do not memorize every line exactly.
- Learn the meaning of each paragraph and speak it naturally.
- Use pauses after important lines.
- Avoid sounding like every sentence has the same rhythm.
- Let visuals carry technical details instead of reading everything aloud.
- Record each phase separately instead of attempting one continuous take.
- Keep mistakes that sound human when they do not affect clarity.
- Speak slightly slower during the architecture and security sections.
- Speak faster during transitions and feature montages.
- Do not claim the system is completely spoof-proof.
- Describe the evaluation honestly as a controlled prototype test with five participants.

# Recording Checklist

- Presenter footage
- Phone-photo attack clip
- Face enrollment image grid
- Session picker clip
- Successful check-in
- Duplicate attempt
- Failed liveness attempt
- Multiple-face or face-transfer test
- Dashboard live update
- Snapshot preview
- Review workflow
- Assistant recommendation
- Evaluation setup
- Evaluation results
- Final metrics
- ProxyGuard title animation
