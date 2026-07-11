
# Testing

This document records testing plans, test cases, and results, organized by area. See [[bugs]] for the specific defects each fix addressed and [[decisions]] for the reasoning behind each safeguard.

---

## Recognition Tests

### Test
Face-matching threshold tightening in `src/face_recognizer.py` (distance tolerance 0.45, minimum margin 0.1 between best and second-best candidate), verified two ways: manual check-in retesting, and a quantitative leave-one-out FAR/FRR experiment (`src/experiment_far_frr.py`).

### Purpose
Confirm the tightened thresholds reduce false accepts between visually similar students without an unacceptable increase in legitimate students falling back to `"Unknown"`. See [[decisions]] Decision 5, and [[report]] Section 9 for the full write-up.

### Steps
1. Attempt check-in as each registered student under normal lighting/angle.
2. Attempt check-in as a visually similar registered student (the Izzuddin false-match scenario) under the previous, looser thresholds and again under the tightened ones.
3. **Quantitative:** run `src/experiment_far_frr.py`, a leave-one-out identification experiment over every usable image in `data/known_faces/` (41 of 46; 5 had no detectable face), reusing `face_recognizer.recognize_face()` directly. For each image: a genuine trial (matched against a gallery of every other image) and an impostor trial (matched against a gallery with that subject's own images fully excluded), run once at the tightened thresholds and once at the original ones.

### Expected Result
The previously-accepted false match is rejected (falls to `"Unknown"` rather than being accepted under the wrong identity) after tightening; legitimate students with adequate reference photos still match; the quantitative experiment should show a materially lower FAR at the tightened thresholds, at a small FRR cost.

### Actual Result
Matches expected. Manually, the false-match incident that motivated Decision 5 no longer reproduces after tightening. Quantitatively: **FAR dropped from 31.7% (13/41 impostor trials falsely accepted) to 2.4% (1/41)** — a ~13× reduction — while **FRR rose from 2.5% to 5.0%** (1/40 → 2/40 genuine misses; `shahmizan`'s single image was excluded from the genuine trial as a leave-one-out singleton). The one recurring error at both settings was confusion between two visually similar group members (Adli/Izzuddin), consistent with the original Decision 5 incident report.

### Status
Passed.

---

## Liveness Tests

### Test
Blink detection (EAR-based) and the randomized head-movement challenge, exercised through the live check-in flow (desktop and `checkin_app`).

### Purpose
Confirm a static photo or frozen frame cannot pass the challenge, and that a live person following the on-screen instruction (turn head in the randomized direction, with a genuine blink in the same window) does pass.

### Steps
1. Hold up a printed/static photo of a registered student — attempt the challenge.
2. Check in as a live registered student, following the randomized direction and blinking naturally.
3. Check in as a live registered student who does not move/blink until the challenge window expires.

### Expected Result
A static photo cannot satisfy blink + directional head movement and times out to `liveness_failed`; a live, responsive student passes; a live but unresponsive student also times out to `liveness_failed`.

### Actual Result
Matches expected in manual testing across both entry points.

### Status
Passed.

---

## Duplicate Tests

### Test
`CheckinSession._check_duplicate_checkin()`, both scripted (synthetic identity state, no camera) and live (a second real check-in attempt within the same session).

### Purpose
Confirm a student who already has a successful check-in this session is stopped **before** the liveness challenge completes — entering `duplicate_checkin` directly — rather than running the full challenge and only being downgraded afterward. See [[decisions]] Decision 12.

### Steps
1. Scripted (`src/test_duplicate_checkin.py`, `has_success_this_session` monkeypatched so no real CSV is touched):
   - No `identified_name` set yet → the duplicate helper must not be called and the attempt must not lock.
   - A stable identity with no prior success this session → the helper is called once, the attempt does not lock, `flow_phase` stays `None`.
   - The same identity re-checked next processed frame → the helper is **not** called again (no redundant CSV re-scan).
   - A stable identity that already has a successful check-in this session → the attempt locks immediately into `duplicate_checkin`, `confirmed_name` stays `None`, and `can_reset()` is `True`.
2. Live: check in successfully once, then attempt to check in again as the same student in the same session.

### Expected Result
Scripted assertions all pass; live retry shows "ALREADY CHECKED IN: <name>" without ever showing "LIVENESS DETECTION SUCCESSFUL" or "ATTENDANCE CONFIRMED", and the CSV row is `result=failed`, `reason=duplicate check-in this session` with a matching snapshot filename.

### Actual Result
Scripted run passes (`src/test_duplicate_checkin.py`); live snapshots and CSV rows in `logs/` confirm the `duplicate_checkin` reason and filename match for real repeat attempts.

### Status
Passed.

---

## Replay Attack / Phone Screen Tests

### Test
Manual bypass attempt (reported by the project owner) plus scripted verification of `CheckinSession._update_identity_continuity()` driven with synthetic recognition results (no camera required): recognize a real face, hide it, present an unregistered face or a phone/photo image of a different person at the same on-screen position, and attempt to complete the challenge under the original identity.

### Purpose
Confirm a recognized identity cannot silently transfer to a phone screen, printed photo, or different real face shown at the same position during an active liveness challenge. See [[decisions]] Decision 11, [[bugs]].

### Steps
Same guard, same scripted scenarios as [[testing#Bounding Box Transfer Tests|Bounding Box Transfer Tests]] below, tested here from the phone/replay threat-model angle specifically.

### Expected Result
See [[testing#Bounding Box Transfer Tests|Bounding Box Transfer Tests]] — identical guard, identical expected outcome.

### Actual Result
See [[testing#Bounding Box Transfer Tests|Bounding Box Transfer Tests]] — identical guard, identical result.

### Status
Passed.

---

## Bounding Box Transfer Tests

### Test
Scripted verification of `CheckinSession._update_identity_continuity()` against four scenarios, driven with synthetic recognition results:
1. Real face recognized, then swapped to `"Unknown"` at the same position for 3 consecutive recognition checks.
2. Real face recognized, one single stray `"Unknown"` frame, then the same real face reappears.
3. Real face recognized, then swapped to a *different* registered student's name at the same position.
4. Real face recognized, then the same name reported again but at a face position far across the frame.

### Purpose
Confirm a recognized identity cannot silently transfer to a different or swapped-in face (the project's bounding-box transfer protection), while a single legitimate misdetection is still tolerated (anti-flicker). See [[decisions]] Decision 11, [[bugs]].

### Expected Result
Scenario 1 clears the identity within 3 checks and restarts the challenge; a same-instant "passed" never confirms during the tolerance window. Scenario 2 does *not* reset (single blip tolerated). Scenarios 3 and 4 are both blocked immediately (name mismatch and spatial jump each independently break continuity).

### Actual Result
Matches expected in all four scripted scenarios. A minimal self-check for the underlying geometric threshold lives in `src/test_face_continuity.py`.

### Status
Passed (fix applied 2026-07-08).

---

## Multiple Face Tests

### Test
Manual verification with two people simultaneously in frame during an active check-in attempt (desktop and `checkin_app`).

### Purpose
Confirm the liveness challenge pauses (no progress, no timeout, no lock) while more than one face is detected, and that both entry points show the same warning. See [[decisions]] Decision 10, [[bugs]].

### Steps
1. Start a check-in attempt with one registered student in frame; introduce a second face mid-challenge.
2. Remove the second face and confirm the challenge resumes with the same target direction and full remaining time.

### Expected Result
While two faces are present, the countdown is frozen and "Only one person allowed in frame..." is shown; once back to one face, the same challenge resumes rather than restarting or timing out.

### Actual Result
Matches expected on both the desktop app and `checkin_app`.

### Status
Passed.

---

## Unknown Face Tests

### Test
Check in with an unregistered face, both as a standalone attempt and combined with a liveness pass/fail.

### Purpose
Confirm an unrecognized face is logged as `"Unknown"` (never a registered student's name), and that a *registered* student who fails liveness is still logged under their real name rather than falling back to `"Unknown"`. See [[bugs]].

### Steps
1. Attempt check-in with a face not in `data/known_faces/` — let the liveness challenge pass and separately let it fail.
2. Attempt check-in as a registered student, then deliberately fail the liveness challenge.
3. Inspect the resulting CSV rows and snapshot filenames for both cases.

### Expected Result
The unregistered face logs `name=Unknown` regardless of the liveness outcome; the registered-but-failed attempt logs the student's real name, matching the snapshot filename.

### Actual Result
Confirmed via a temp-CSV simulation of `attendance_logger.log_attendance` with the `log_name = confirmed_name or last_known_name or "Unknown"` logic, and reproduced live against the running `checkin_app`/dashboard.

### Status
Passed (fix applied 2026-07-08).

---

## Dashboard Tests

### Test
Real `logs/attendance.csv` and `logs/snapshots/` matched via `dashboard.app.find_snapshot_for_row()`; smart-refresh behavior verified via a headless-browser session (Playwright) against a running `dashboard/app.py` instance.

### Purpose
Confirm the dashboard displays a matching inline snapshot for every row that has one on disk (including the name-mismatch fallback for older rows), and that smart refresh reliably detects new attendance rows *and* lecturer review changes while never interrupting active interaction.

### Steps
1. Run the strict `session_id + name + reason` prefix match against all real CSV rows; apply the session+reason+timestamp fallback where the strict match misses.
2. Load `GET /?session=...&tab=attempts` in a real Flask instance and confirm the rendered HTML includes the expected snapshot `<img>` src, and `GET /snapshot/<filename>` serves it as `image/jpeg`.
3. Headless-browser checks: `/status` returns `Cache-Control: no-store`; an idle tab picks up a newly-logged attendance row within one poll interval; a tab with the search box focused does **not** reload while a change is pending; blurring the search box applies the pending reload immediately rather than waiting out the rest of the poll interval; a lecturer review action changes `get_attendance_version()` (so other tabs/devices see it) while the tab that made the review does not needlessly reload itself.

### Expected Result
All real rows with an on-disk snapshot match (strict or fallback); smart refresh reloads exactly once per real change, never while busy, and never misses a change due to caching or filesystem-mtime coarseness.

### Actual Result
13/14 real rows matched via snapshot lookup (the remaining miss had no snapshot file on disk at all); headless-browser checks confirmed no-cache headers, idle-tab auto-refresh, busy-tab protection, prompt apply-on-blur, and correct cross-tab review-change detection, all with zero console errors.

### Status
Passed.

---

## Assistant Tests

### Test
`src/../dashboard/test_assistant.py` (self-check over `build_assistant_recommendations()`/`build_assistant_summary()`), plus a headless-browser session exercising the rendered assistant panel.

### Purpose
Confirm the ProxyGuard Assistant's rules fire/resolve correctly (resolution-aware — e.g. the pending-review card disappears once every row is reviewed), stay within the max card count, never use accusatory wording, and that each recommendation's action buttons correctly reuse the existing filter chips and table (no second filtering/preview system).

### Steps
1. Empty session → a single informational card.
2. Clean session (no issues) → a single normal-session card, not padded with filler.
3. A "messy" session (every rule triggering at once) → cards capped at the maximum, sorted High → Medium → Low, no banned wording, correct per-card action buttons (`view_filter` / `open_next_unreviewed`).
4. One real issue → shows alone, no filler cards.
5. Resolving the only unreviewed row removes the pending-review card.
6. Headless-browser: clicking **View affected attempts** switches to the Attempts tab, applies the correct filter, preserves the selected session, and closes the assistant; clicking **Open next unreviewed attempt** activates the Unreviewed filter, scrolls to and briefly highlights the first matching row; the assistant is reachable and shows identical, session-consistent content from both the Present and Attempts tabs.

### Expected Result
All scripted assertions pass; all button actions produce the documented effect with zero console errors.

### Actual Result
Matches expected — self-check passes, and headless-browser verification confirmed every action button's effect end-to-end.

### Status
Passed.

---

## Session Tests

### Test
`checkin_app` session picker → live check-in handoff, verified via a headless-browser session against a running `checkin_app/app.py` instance.

### Purpose
Confirm the session picker's skeleton loading state appears immediately on submit (before the backend session/camera finish preparing), the form's actual data survives the transition, and the live check-in page correctly gates the real content behind the skeleton until the stream and station are genuinely ready.

### Steps
1. Submit the session picker and inspect DOM state immediately afterward: picker hidden, skeleton shown with `aria-busy="true"`, submit button disabled/relabeled, and — critically — the `<select>` values are *not* stripped from the submitted form data.
2. Load `/checkin` and confirm the skeleton is visible and the real content is hidden until the MJPEG `<img>`'s `load` event fires and `/status` reports the station active.

### Expected Result
Skeleton shows synchronously on submit with no lost form data; real content on `/checkin` reveals only once both readiness conditions are met, never on a fixed timeout, never showing a black camera box.

### Actual Result
Confirmed via a deterministic DOM-state check (with `form.submit()` neutralized to avoid a race with real navigation): picker hidden, skeleton visible with correct shimmer placeholders and `aria-busy`, button disabled/relabeled, form data intact. Confirmed end-to-end on `/checkin` with this machine's real camera: skeleton hides and real content reveals promptly once the stream/status are ready, with zero console errors. (One real regression was caught and fixed during this verification: disabling the `<select>` elements on submit had been silently stripping `subject`/`week` from the POST — see [[bugs]].)

### Status
Passed.

---

## Review Workflow Tests

### Test
`POST /review` round-trip (Accept / Suspicious + note) against `logs/reviews.csv`, and the dashboard's in-place UI update after a successful review.

### Purpose
Confirm a review decision persists independently of `logs/attendance.csv`, survives a reload, and updates the row badge, note, review summary, active review filter, and ProxyGuard Assistant panel in place without a full page reload.

### Steps
1. Mark an Attempts row Suspicious with a note; reload the page and confirm the badge/note persisted.
2. Change the same row to Accepted; confirm the review summary counts update and the Assistant's suspicious-attempts card disappears if it was the only one.
3. Confirm `logs/attendance.csv` is byte-for-byte unchanged by any review action.

### Expected Result
Review state persists and updates all dependent UI in place; the raw attendance log is never modified by a review action.

### Actual Result
Matches expected.

### Status
Passed.

---

## UI Tests

### Test
Visual/styling verification of the dashboard's ProxyGuard Assistant action buttons and the `checkin_app` skeleton loading state, via headless-browser computed-style checks.

### Purpose
Confirm both surfaces follow the shared monochromatic design system (`docs/ui-references/DESIGN.md`) — no black-filled action buttons inside the assistant, 18px button radius, a soft shimmer (respecting `prefers-reduced-motion`) on skeleton placeholders sized to match the real layout (no layout jump on reveal).

### Steps
1. Inspect computed `background-color`, `border`, and `border-radius` of the assistant's action buttons.
2. Inspect the skeleton's shimmer animation and confirm `@media (prefers-reduced-motion: reduce)` disables it.

### Expected Result
Action buttons use a light background (white/soft gray) with a hairline border, never a black fill; skeleton placeholders are sized to match their real counterparts (video aspect ratio, button height) so revealing the real content causes no layout shift.

### Actual Result
Confirmed via headless-browser computed-style checks (e.g. primary action button background resolved to `rgb(255, 255, 255)`, not black).

### Status
Passed.

---

## Test Case Template

### Test
-

### Purpose
-

### Steps
-

### Expected Result
-

### Actual Result
-

### Status
-

## Related Documentation

- [[project-overview]]
- [[roadmap]]
- [[decisions]]
- [[bugs]]
- [[report]]
- [[CLAUDE]]

