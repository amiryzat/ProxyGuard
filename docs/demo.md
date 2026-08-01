# Demo Video Plan

Shot list, script, and run-of-show for the ProxyGuard project demo video. Target length: **≤ 10 minutes**. Written for three presenters/operators (matches [[project-overview]] group members) but works with one person narrating over screen capture if needed.

See [[flowchart]] for the diagrams to screen-capture in Scene 2, and [[report]] for the exact evaluation numbers quoted in Scene 5.

## 0. Goal, audience, tone

- **Goal**: convince a lecturer/grader in under 10 minutes that (a) proxy attendance is a real gap in ordinary face-recognition check-in, (b) ProxyGuard closes it with layered, explainable checks, and (c) it actually works, live, on a real webcam — not just in theory.
- **Audience**: course lecturer/evaluator grading a CSC649 proposal demo. Assume they know what face recognition is; don't assume they know what "liveness detection" or "EAR" means.
- **Tone**: confident and brisk, not a sales pitch. Show failures on purpose (liveness fail, duplicate, unknown rejection) — a system that only ever shows success looks staged.

## 1. Run-of-show (timestamps)

| # | Scene | Target time | Cumulative |
|---|-------|-------------|------------|
| 1 | Hook + problem statement | 0:45 | 0:45 |
| 2 | Objectives + architecture overview | 1:30 | 2:15 |
| 3 | Live demo — session setup | 0:30 | 2:45 |
| 4 | Live demo — genuine check-in (success) | 1:00 | 3:45 |
| 5 | Live demo — deliberate failure cases | 2:00 | 5:45 |
| 6 | Lecturer dashboard walkthrough | 1:45 | 7:30 |
| 7 | Evaluation results | 1:15 | 8:45 |
| 8 | Limitations + closing | 1:00 | 9:45 |

Buffer: ~15s slack before the 10:00 hard cap. If running long, cut from Scene 6 (dashboard) first — it's the most visual/self-explanatory scene and needs the least narration.

## 2. Scene-by-scene script

Each scene: **[On screen]** what the viewer sees, **"Narration"** what's said (a draft — say it naturally, don't read it word for word), **Direction** camera/editing notes.

---

### Scene 1 — Hook + problem statement (0:45)

**[On screen]** Title card: "ProxyGuard — Liveness-Aware Face Recognition for Proxy Attendance Detection", then group members. Cut to a short staged clip: someone holding up a phone with a classmate's photo to a webcam running a plain face-recognition demo, which accepts it.

**"Narration"**
> "Face recognition attendance is everywhere now, but most systems check identity once and move on. That's exactly the gap a proxy check-in exploits — one student holds up a photo, a video, or gets a friend to check in for them, and the system can't tell the difference. That's the problem ProxyGuard is built to solve."

**Direction**: Keep the "attack" clip under 10 seconds — it's a hook, not a case study. If you don't want to stage a real bypass on camera, describe it verbally over a still photo instead; don't fake a system accepting something it wouldn't actually accept.

---

### Scene 2 — Objectives + architecture overview (1:30)

**[On screen]** Bullet-point objectives (reuse [[project-overview]]'s 3 objectives), then cut to the Section 0.7 architecture pipeline diagram from [[flowchart]] (the boxed pipeline image), then the Section 0 simple-overview diagram.

**"Narration"**
> "We had three objectives: recognize registered students from a live camera feed, add multi-factor liveness detection so the system knows a real person is present — not a photo or recording — and flag suspicious patterns for the lecturer to review afterward.
>
> Here's the pipeline. A lecturer picks the class and week, which builds a session ID. Every check-in goes through face detection, identity verification, and then two safeguards most systems skip: a continuity guard that stops someone swapping in a different face mid-attempt, and a duplicate check that runs before the liveness challenge, so someone who's already checked in isn't even given a chance to retry. Only then does the liveness challenge run — a blink plus a randomized head-turn direction. The result gets logged with a photo snapshot, and everything surfaces on a lecturer dashboard."

**Direction**: This is the densest talking scene — practice it so it doesn't run long. Use on-screen callout boxes/highlights synced to each sentence (continuity guard, duplicate check, liveness) rather than one static diagram sitting still for 90 seconds.

---

### Scene 3 — Live demo: session setup (0:30)

**[On screen]** Screen recording of `checkin_app`'s setup page (`http://localhost:5002/`): pick a class subject and week number, click Start, skeleton loading screen, then the live check-in page appears.

**"Narration"**
> "This is the student-facing check-in app. The lecturer — or in a real deployment, whoever runs the station — picks the class and week, and that's it. Everything downstream is tied to this one session."

**Direction**: Let the skeleton-loading shimmer actually play for a second or two on camera — it's a real UX detail worth showing, not dead air to cut.

---

### Scene 4 — Live demo: genuine check-in (1:00)

**[On screen]** A registered group member sits in frame, gets recognized (green box + name), completes the head-turn + blink challenge, sees "LIVENESS DETECTION SUCCESSFUL" then "ATTENDANCE CONFIRMED: <name>".

**"Narration"**
> "Here's a normal, successful check-in. The system detects and recognizes the face, then prompts a random direction — this time it's [left/right/up] — and it needs a blink during the same window, not before or after. Random per attempt, so it can't be pre-recorded. Pass both, and attendance is confirmed."

**Direction**: This is the one scene where you can't control timing — the 10-second challenge window is real. **Do not pad the final video with the full wait**: either speed up 2x through the countdown in post, or narrate over it live so the "dead" seconds carry commentary instead of silence.

---

### Scene 5 — Live demo: deliberate failure cases (2:00)

**[On screen]** Four short back-to-back clips, ~25–30s each:
1. **Unknown person** — someone not in `data/known_faces/` sits in frame; box is red, "Unknown"; runs to `not_recognized`.
2. **Deliberate liveness failure** — a registered student sits still, doesn't blink/turn head, challenge times out to "LIVENESS TEST FAILED".
3. **Duplicate check-in** — the same student from Scene 4 sits back down; system immediately shows "ALREADY CHECKED IN: <name>" without re-running the challenge.
4. **Multi-face pause** — two people in frame at once; system shows "Only one person allowed in frame..." and the challenge visibly pauses/freezes.

**"Narration"**
> "It's just as important to show what the system rejects. An unrecognized face gets logged as Unknown. A registered student who doesn't complete the liveness challenge fails, not passes by default. Someone who already checked in this session is stopped immediately — the liveness challenge doesn't even run a second time, so there's no retry loophole. And if a second person steps into frame mid-challenge, everything pauses until it's back to one person — so you can't have someone else complete the challenge next to the registered face."

**Direction**: Cut hard between these four — no need for the full outcome screen to sit for more than 2–3 seconds each. This scene is where the anti-proxy pitch actually lands, so don't rush the narration even though the clips are short.

---

### Scene 6 — Lecturer dashboard walkthrough (1:45)

**[On screen]** Screen recording of `dashboard/` (`http://localhost:5001/`): Present tab, switch to Attempts tab, apply a quick filter (e.g. "Liveness Failed"), click a row's snapshot thumbnail to open the preview modal, mark one attempt Accepted/Suspicious with a note, then open the ProxyGuard Assistant panel and click one of its recommendation buttons.

**"Narration"**
> "Everything from that demo just landed here. Present and Attempts tabs split successful check-ins from failures. Every row has a verification snapshot the lecturer can open full-size — this is the photo saved at the moment of the outcome, so a pass or fail can be double-checked against what was actually captured. A lecturer can mark any attempt Accepted or Suspicious with a note, and the ProxyGuard Assistant on the side turns all of this into a short prioritized list — what needs attention first — instead of making the lecturer read every row."

**Direction**: This scene is the most self-explanatory visually — let the UI do the talking, keep narration tight, don't describe every filter chip by name.

---

### Scene 7 — Evaluation results (1:15)

**[On screen]** The two saved chart images: `docs/recognition_metrics_charts.png` (FAR/FRR line graph + FTE pie) and `docs/liveness_metrics_charts.png` (TAR/FRR bar + outcome pie + latency). Overlay the key numbers as text as they're mentioned.

**"Narration"**
> "We backed this up with real measurements, not just a working demo. On face recognition, tightening the match threshold cut the false-accept rate from nearly 32% down to about 2.4%, at the cost of a slightly higher false-reject rate — about 5% instead of 2.5%. That's a deliberate tradeoff: we'd rather ask a genuine student to retry than let an impostor through. On liveness, genuine attempts passed the blink-and-head-turn challenge about 80% of the time, with the rest timing out — mostly from missing the window, not a system flaw. And the average successful check-in took about 6.6 seconds end to end, which is fast enough for real classroom use."

**Direction**: Don't read every number in the report — three headline figures (FAR drop, TAR, average latency) are enough for a 75-second scene. Full tables belong in the written report, not narrated here.

---

### Scene 8 — Limitations + closing (1:00)

**[On screen]** Title card or bullet list: "Known limitation: a live video call of the real student can genuinely blink and turn on command — this isn't yet distinguishable from a real webcam capture." Then a closing card with group member names and "Thank you".

**"Narration"**
> "One limitation we're upfront about: our current checks can't yet tell a real webcam from a webcam pointed at a live video call of the actual student — that would need something like screen or moiré-pattern detection, which is out of scope for this proposal stage. Everything else you've seen — recognition, liveness, the anti-proxy guards, and the dashboard — works end to end today. Thanks for watching."

**Direction**: End on the limitation, not hide it — a proposal defense that names its own gap reads as more credible than one that claims a solved problem.

## 3. Pre-recording checklist

- [ ] Decide who is on-camera for genuine/duplicate/liveness-fail clips (must be someone in `data/known_faces/`) and who plays the "unknown person" (must NOT be registered).
- [ ] Back up `logs/attendance.csv`, `logs/reviews.csv`, and `logs/snapshots/` before recording, then start from a clean state so the dashboard demo (Scene 6) shows a small, readable session rather than months of accumulated rows.
- [ ] Start both apps ahead of time and confirm both load: `python3 checkin_app/app.py` (port 5002), `python3 dashboard/app.py` (port 5001).
- [ ] Pick one class subject + week for the whole recording session so every clip in Scenes 4–6 lands in the same `session_id` and tells one coherent story on the dashboard.
- [ ] Test lighting/webcam framing once before recording — blink detection and head-pose both degrade in poor lighting or if the face is too close/far from frame.
- [ ] Have the two chart PNGs (`docs/recognition_metrics_charts.png`, `docs/liveness_metrics_charts.png`) already generated and ready to screen-capture for Scene 7 — regenerate via `python3 src/visualize_recognition_metrics.py` / `python3 src/visualize_liveness_metrics.py` if the numbers in [[report]] have changed since they were last rendered.
- [ ] Rehearse Scene 2's narration out loud at least once — it's the only scene with no visual payoff to fall back on if the talking runs long.

## 4. Post-production notes

- Speed up (2x–4x) any real-time wait longer than ~3 seconds (the 10s liveness countdown, camera startup) rather than cutting it to zero — viewers should still register that time passed.
- Add on-screen text callouts for the outcome banners ("ATTENDANCE CONFIRMED", "LIVENESS TEST FAILED", etc.) in Scenes 4–5 in case the in-frame text is hard to read at video resolution.
- Add lower-third captions for the two chart scenes (Scene 7) restating the headline number (e.g. "FAR: 31.7% → 2.4%") since numbers spoken once are easy to miss.
- Keep total runtime under 10:00 — cut Scene 6 (dashboard) narration first if over time; it's the most self-evident scene visually.

## Related Documentation

- [[flowchart]] — diagrams to screen-capture for Scene 2.
- [[report]] — full evaluation methodology and numbers behind Scene 7.
- [[project-overview]] — objectives reused verbatim in Scene 2.
- [[architecture]] — prose detail if narration needs to go deeper than the script above.
