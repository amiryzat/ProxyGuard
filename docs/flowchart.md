# System Flowchart

Visualizes the main ProxyGuard flow end to end: session picking (`checkin_app`), the shared check-in engine (`CheckinSession` in `src/main.py`), and lecturer dashboard monitoring (`dashboard/`). Evaluation Mode is intentionally excluded — see [[architecture]] for that feature if needed.

Two representations of the same flow are given below: a text-based (ASCII) diagram, and Mermaid source. Both are kept in sync with the real routes/states in `checkin_app/app.py`, `src/main.py`, and `dashboard/app.py` — update both if the flow changes. See [[architecture]] for prose detail and [[decisions]] for why each safeguard exists.

## 0. Simple Overview (plain language)

A quick, non-technical version of the same flow — good for a presentation slide or explaining the system to someone who isn't reading the code.

```
[Lecturer picks class + week]
            |
            v
[Student sits in front of the camera]
            |
            v
      More than one
      person in view? -- yes --> [Ask for one person only] --> (wait)
            |
            no
            |
            v
[System checks who the face belongs to]
            |
            v
      Face recognized? -- no --> [Mark as "Not Recognized"]
            |
            yes
            |
            v
[Already checked in today?] -- yes --> [Mark as "Duplicate"]
            |
            no
            |
            v
[Ask the student to blink and turn their head]
            |
            v
      Passed the
      liveness check? -- no --> [Mark as "Liveness Failed"]
            |
            yes
            |
            v
[Mark as "Attendance Confirmed"]
            |
            v
[Save the result + a photo for the lecturer to review later]
            |
            v
[Lecturer opens the dashboard: sees who's present,
 who failed, and can flag anything suspicious]
```

```mermaid
flowchart TD
    A[Lecturer picks class + week] --> B[Student sits in front of camera]
    B --> C{More than one\nperson in view?}
    C -- Yes --> C1[Ask for one person only]
    C1 --> B
    C -- No --> D[System checks who the face belongs to]
    D --> E{Face recognized?}
    E -- No --> E1[Mark as Not Recognized]
    E -- Yes --> F{Already checked in?}
    F -- Yes --> F1[Mark as Duplicate]
    F -- No --> G[Ask student to blink and turn head]
    G --> H{Passed liveness check?}
    H -- No --> H1[Mark as Liveness Failed]
    H -- Yes --> I[Mark as Attendance Confirmed]
    E1 --> J[Save result + photo for review]
    F1 --> J
    H1 --> J
    I --> J
    J --> K[Lecturer views dashboard:\npresent / failed / flagged]
```

## 0.5 Compact Report Diagram (standard shapes, short and wide)

A shorter, single-page version for pasting into the report as a figure — standard flowchart shapes only (stadium = start/end, rectangle = process/action, diamond = decision), one path top to bottom with no side loops.

```mermaid
flowchart TD
    A(["Start"]) --> B["Pick class + week,\nstart check-in"]
    B --> C{"One person\nin frame?"}
    C -- No --> B
    C -- Yes --> D["Recognize face"]
    D --> E{"Recognized?"}
    E -- No --> Z1["Result: Not Recognized"]
    E -- Yes --> F{"Already checked in?"}
    F -- Yes --> Z2["Result: Duplicate"]
    F -- No --> G["Blink + head-turn check"]
    G --> H{"Liveness passed?"}
    H -- No --> Z3["Result: Liveness Failed"]
    H -- Yes --> Z4["Result: Confirmed"]
    Z1 --> I["Save log + snapshot"]
    Z2 --> I
    Z3 --> I
    Z4 --> I
    I --> J["Lecturer reviews on dashboard"]
    J --> K(["End"])
```

## 0.7 Architecture Pipeline Diagram

A single-path, top-to-bottom pipeline view of the same system — one box per major stage, grouped into the three logical layers (session setup, the check-in engine, and post-attempt logging/monitoring). Good for a "how the pieces connect" slide, as opposed to the decision-by-decision flowcharts above.

### Boxed pipeline (text-based)

```
┌───────────────────────────────────────────────────┐
│                   SESSION SETUP                    │
│   Session Picker  (class + week → session_id)      │
└────────────────────────┬────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│                  LIVE CHECK-IN UI                   │
│   MJPEG video stream + skeleton loading state       │
└────────────────────────┬────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│                   FACE DETECTION                    │
│              OpenCV Haar Cascade                    │
└────────────────────────┬────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│               IDENTITY VERIFICATION                 │
│           exactly one face required                 │
└────────────────────────┬────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│         ACTIVE-FACE CONTINUITY GUARD                │
│                  (anti face-swap)                    │
└────────────────────────┬────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│                  DUPLICATE CHECK                     │
│              (runs before liveness)                  │
└────────────────────────┬────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│                LIVENESS CHALLENGE                    │
│            blink  +  head movement                   │
└────────────────────────┬────────────────────────────┘
                          │
                          ▼
                    ◇ ATTENDANCE ◇
                    ◇  DECISION  ◇
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│                 ATTENDANCE LOGGER                     │
│      CSV row  +  verification snapshot (.jpg)         │
└────────────────────────┬────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│           LECTURER DASHBOARD + REVIEW                 │
└────────────────────────┬────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────┐
│                PROXYGUARD ASSISTANT                   │
└───────────────────────────────────────────────────┘
```

### Mermaid version

```mermaid
flowchart TD
    subgraph L1["Session Setup"]
        A(["Session Picker\nclass + week -> session_id"])
    end

    subgraph L2["Check-in Engine (CheckinSession)"]
        direction TB
        B["Live Check-in UI\nMJPEG + skeleton loading"]
        C["Face Detection\nOpenCV Haar Cascade"]
        D["Identity Verification\nexactly one face required"]
        E["Active-Face Continuity Guard\n(anti face-swap)"]
        F["Duplicate Check\n(before liveness)"]
        G["Liveness Challenge\nblink + head movement"]
        H{"Attendance\nDecision"}
        B --> C --> D --> E --> F --> G --> H
    end

    subgraph L3["Logging & Monitoring"]
        direction TB
        I[("Attendance Logger\nCSV + verification snapshot")]
        J["Lecturer Dashboard + Review"]
        K["ProxyGuard Assistant"]
        I --> J --> K
    end

    A --> B
    H --> I
```

## 1. Text-based (ASCII) flow

```
[START]
   |
   v
==================================================================
 CHECKIN_APP: SESSION PICKER  (GET / -> setup.html)
==================================================================
   |
   v
[Lecturer/operator picks class subject + week (1-14)]
   |
   v
[Submit -> client-side skeleton shown immediately
 (shimmer placeholders, "Preparing check-in session...")]
   |
   v
[POST /start]
   |
   v
<subject + week valid against CLASS_SUBJECTS / WEEK_MIN..WEEK_MAX?>
   |
   |-- No --> re-render setup.html with an error --> back to SESSION PICKER
   |
   +-- Yes
         |
         v
       [build_session_id(subject, week) = YYYY-MM-DD_HHMM_<CODE>_Week<N>]
       [Station: open webcam once, construct ONE CheckinSession
        (loads known_faces encodings, opens its own mediapipe FaceMesh)]
         |
         v
       [Redirect -> GET /checkin  (checkin.html)]


==================================================================
 CHECKIN_APP: LIVE CHECK-IN PAGE
==================================================================
   |
   v
[Skeleton shown by default on this page too]
   |
   v
<MJPEG <img> decoded first frame (load event)
 AND /status reports station active?>
   |
   |-- No, within 30s --> keep waiting (poll /status)
   |-- No, after 30s  --> show "Try again" failure state
   |
   +-- Yes --> hide skeleton, show live view
         |
         v
       [GET /video_feed: MJPEG stream, ~20 FPS, 1280x720 JPEG q80]
       [each frame -> CheckinSession.process_frame(frame)]
         |
         v
       (see Section 2 below: CheckinSession per-frame flow --
        this is where recognition/liveness/logging/snapshot all happen)
         |
         v
       [GET /status polled by the page: flow_phase / banner text /
        can_reset -- drives the visible message + button state]
         |
         v
       <Terminal outcome reached AND lecturer/student clicks
        "New check-in" (POST /reset)?>
         |
         |-- Yes --> same CheckinSession.reset() --> fresh attempt
         |            --> back to CheckinSession per-frame flow
         |
         +-- No --> stays on terminal screen
         |
         v
       <"End session" clicked (POST /end_session)?>
         |
         +-- Yes --> release camera + CheckinSession --> back to SESSION PICKER


==================================================================
 SECTION 2: CheckinSession PER-FRAME FLOW (src/main.py)
 -- shared identically by checkin_app/ AND the desktop entry point --
==================================================================
   |
   v
[Face Detection] -- every 3rd frame only (face_recognition, 0.25x scale)
   |
   v
<How many faces?>
   |
   |-- 0 faces ---------------------------------------> loop (next frame)
   |
   |-- more than 1 face
   |     |
   |     v
   |   [PAUSE challenge: freeze countdown, discard partial match]
   |   [Show: "Only one person allowed in frame, please
   |          ensure you are alone during check-in"]
   |     |
   |     +---------------------------------------------> loop (next frame)
   |
   +-- exactly 1 face
         |
         v
       [attempt_started_at set once (first usable single-face frame)]
       [Identity Verification: recognize_face(), tolerance 0.45, margin 0.1]
         |
         v
       <Registered match found?>
         |
         |-- No ("Unknown") --------------------------> loop (next frame)
         |
         +-- Yes
               |
               v
             [Identity-Liveness Continuity Guard]
             [same name as currently bound identity? position within
              35% of frame width of last confirmed position? up to 2
              consecutive mismatches tolerated before clearing]
               |
               v
             <Continuity holds?>
               |
               |-- No (3rd consecutive mismatch)
               |     |
               |     v
               |   [Clear identity, restart challenge from scratch]
               |   [Show: "Face changed or lost, please keep the
               |          same face in frame"]
               |     |
               |     +-------------------------------> loop (next frame)
               |
               +-- Yes
                     |
                     v
                   [identity_decided_at set once; identified_name /
                    last_known_name updated]
                   [Duplicate Check: has_success_this_session(name,
                    session_id) -- reused from attendance_logger.py]
                     |
                     v
                   <Already checked in successfully this session?>
                     |
                     |-- Yes
                     |     |
                     |     v
                     |   [LOCK -> duplicate_checkin]
                     |   [Liveness challenge SKIPPED entirely]
                     |   [Show: "ALREADY CHECKED IN: <name>"]
                     |     |
                     |     v
                     |   go to TERMINAL OUTCOME below
                     |
                     +-- No
                           |
                           v
                         [Liveness Challenge: continuous blink detection
                          (EAR < 0.21, >=2 consecutive frames) + randomized
                          head-turn (left/right/up), 10s window]
                         [challenge_started_at set once landmarks resolve]
                           |
                           v
                         <Blink AND correct head-turn within 10s?>
                           |
                           |-- No (10s elapses)
                           |     |
                           |     v
                           |   [LOCK -> liveness_failed]
                           |   [Show: "LIVENESS TEST FAILED"]
                           |     |
                           |     v
                           |   go to TERMINAL OUTCOME below
                           |
                           +-- Yes
                                 |
                                 v
                               <identified_name set, non-"Unknown", zero
                                current continuity-mismatch streak?>
                                 |
                                 |-- Yes --> confirmed_name := identified_name
                                 +-- No  --> confirmed_name := None
                                 |
                                 v
                               [LOCK -> liveness_success]
                               [Show "LIVENESS DETECTION SUCCESSFUL" for a
                                fixed 2s banner]
                                 |
                                 v (after 2s)
                               <Was confirmed_name set?>
                                 |
                                 |-- Yes --> [LOCK -> confirmed]
                                 |            [Show "ATTENDANCE CONFIRMED: <name>"]
                                 |            go to TERMINAL OUTCOME below
                                 |
                                 +-- No  --> [LOCK -> not_recognized]
                                              [Show "LIVENESS DETECTION
                                               SUCCESSFUL, BUT FACE NOT
                                               RECOGNIZED"]
                                              go to TERMINAL OUTCOME below


==================================================================
 TERMINAL OUTCOME
 -- reached from exactly one of: confirmed | not_recognized |
    liveness_failed | duplicate_checkin --
==================================================================
   |
   v
[terminal_outcome_at set once; recognition/liveness/decision
 duration_seconds finalized (time.monotonic() based)]
   |
   v
[log_attendance(name, result, reason, session_id)
 -> appends one row to logs/attendance.csv
 -> a "success" is downgraded to "failed" / "duplicate check-in this
    session" if a prior success already exists this session]
   |
   v
[Save verification snapshot: logs/snapshots/<session_id>_<name>_
 <reason>_<HHMMSS>.jpg -- pre-overlay frame, for manual lecturer review only]
   |
   v
[can_reset() becomes true -- "New check-in" enabled in checkin_app /
 'n' key on desktop]
   |
   v
back up to CHECKIN_APP: LIVE CHECK-IN PAGE (reset / end_session branch)


==================================================================
 INDEPENDENT, ONGOING: LECTURER DASHBOARD (dashboard/, port 5001)
 -- separate read-only Flask app, polls the same CSVs/snapshots;
    never writes to attendance.csv --
==================================================================
   |
   v
[GET / -- session filter (defaults to most recent session)]
   |
   v
[Present tab: result=success rows]     [Attempts tab: result=failed rows]
   |                                         |
   +------------------+----------------------+
                      |
                      v
       [Quick filters: All/Successful/Failed/Flagged/Unknown/
        Duplicate/Liveness Failed -- client-side chips]
       [Review-status filters: All/Unreviewed/Accepted/Suspicious]
       [Client-side search (persisted in localStorage)]
                      |
                      v
       [Analytics cards: totals, success rate, flagged/duplicate/
        unknown/liveness-failed counts -- session-wide]
       [Reason Breakdown bar chart]
                      |
                      v
       [Flagged-row highlighting -- reuses pattern_flagger.flag_patterns()
        (repeated failures / duplicate attempts / unrecognized clusters);
        no detection logic duplicated in the dashboard]
                      |
                      v
       [Inline snapshot thumbnail per row] --click--> [Snapshot preview
                      |                                modal: full image
                      |                                + row metadata]
                      v
       [Lecturer Review: Accept / Suspicious + note (POST /review)
        -- writes logs/reviews.csv only, never attendance.csv]
        [Review Summary: Unreviewed/Accepted/Suspicious counts]
                      |
                      v
       [ProxyGuard Assistant: rule-based summary (success-rate bar,
        attention level, main concern) + up to 5 prioritized
        recommendation cards, each with "View affected attempts" /
        "Open next unreviewed attempt" -- reuses the same filter chips]
                      |
                      v
       [Smart auto-refresh: GET /status polled; reloads only when a
        content-derived version token changes (row count + latest row
        + reviews.csv size + newest snapshot name); a change mid-
        interaction is deferred until the interaction ends]
                      |
                      v
       [GET /export.csv -- mirrors exactly the current filtered view]
```

## 2. Mermaid source

Renders on GitHub/GitLab or any Mermaid-aware viewer. Three diagrams: (a) the overall app-level flow across `checkin_app` and `dashboard`, (b) `CheckinSession`'s per-frame decision flow as a flowchart, (c) the same engine states as a compact state diagram.

### 2a. App-level flow

```mermaid
flowchart TD
    Start([Start]) --> Picker["checkin_app: Session Picker\nGET / -> setup.html"]
    Picker --> PickForm["Pick class subject + week\nsubmit -> client-side skeleton shown"]
    PickForm --> PostStart["POST /start"]
    PostStart --> Valid{"subject + week valid?"}
    Valid -- No --> PickerErr["Re-render setup.html with error"]
    PickerErr --> Picker
    Valid -- Yes --> BuildId["build_session_id()\nYYYY-MM-DD_HHMM_&lt;CODE&gt;_Week&lt;N&gt;"]
    BuildId --> OpenStation["Open webcam once,\nconstruct one CheckinSession"]
    OpenStation --> CheckinPage["GET /checkin -> checkin.html"]

    CheckinPage --> SkeletonWait{"MJPEG first frame decoded\nAND /status active?"}
    SkeletonWait -- "no, <30s" --> SkeletonWait
    SkeletonWait -- "no, >=30s" --> TryAgain["Show 'Try again'"]
    TryAgain --> CheckinPage
    SkeletonWait -- yes --> LiveView["Live view: GET /video_feed\n(MJPEG, ~20fps, 1280x720 q80)"]

    LiveView --> Engine["CheckinSession.process_frame()\n(see Diagram 2b)"]
    Engine --> Status["GET /status polled\n(flow_phase, banner, can_reset)"]
    Status --> Terminal{"Terminal outcome\n+ user action?"}
    Terminal -- "POST /reset" --> ResetSession["CheckinSession.reset()"]
    ResetSession --> Engine
    Terminal -- "POST /end_session" --> EndSession["Release camera + session"]
    EndSession --> Picker
    Terminal -- "still viewing" --> Status

    Engine --> Log["log_attendance() -> attendance.csv"]
    Log --> Snapshot["Save verification snapshot -> logs/snapshots/"]

    Log -.->|read-only, polled| Dash["dashboard: GET /\nPresent / Attempts tabs"]
    Snapshot -.->|read-only, polled| Dash
    Dash --> Filters["Session filter, quick filters,\nreview filter, search"]
    Filters --> Analytics["Analytics cards + Reason Breakdown"]
    Analytics --> Flagged["Flagged-row highlighting\n(pattern_flagger.flag_patterns)"]
    Flagged --> SnapModal["Snapshot preview modal"]
    SnapModal --> Review["POST /review\n(Accept/Suspicious + note)"]
    Review --> ReviewsCsv[("logs/reviews.csv")]
    Review --> Assistant["ProxyGuard Assistant\n(summary + recommendation cards)"]
    Assistant --> SmartRefresh["Smart refresh: GET /status\n(content-derived version token)"]
    SmartRefresh -.->|change detected, not mid-interaction| Dash
    Analytics --> Export["GET /export.csv\n(mirrors current filtered view)"]
```

### 2b. `CheckinSession` per-frame flowchart

```mermaid
flowchart TD
    Frame["Capture frame\n(~every 3rd frame: face detection)"] --> NumFaces{"How many faces?"}
    NumFaces -- "0" --> Frame
    NumFaces -- ">1" --> Pause["Pause challenge, freeze timer\nShow: 'Only one person allowed...'"]
    Pause --> Frame
    NumFaces -- "1" --> AttemptStart["attempt_started_at set (once)"]
    AttemptStart --> Recognize["recognize_face()\ntolerance 0.45, margin 0.1"]
    Recognize --> Matched{"Registered match?"}
    Matched -- "No (Unknown)" --> Frame
    Matched -- Yes --> Continuity["Identity-Liveness Continuity Guard\n(same name + position within 35% width;\n2-mismatch tolerance)"]
    Continuity --> ContOk{"Continuity holds?"}
    ContOk -- "No (3rd mismatch)" --> ClearId["Clear identity, restart challenge\nShow: 'Face changed or lost...'"]
    ClearId --> Frame
    ContOk -- Yes --> IdDecided["identity_decided_at set (once)"]
    IdDecided --> DupCheck["Duplicate Check:\nhas_success_this_session()"]
    DupCheck --> DupFound{"Already checked in\nthis session?"}
    DupFound -- Yes --> DupLock["LOCK -> duplicate_checkin\n(liveness SKIPPED)\nShow: 'ALREADY CHECKED IN: name'"]
    DupLock --> Terminal
    DupFound -- No --> Liveness["Liveness Challenge:\nblink (EAR&lt;0.21) + head-turn, 10s window"]
    Liveness --> LiveResult{"Blink AND correct\nhead-turn within 10s?"}
    LiveResult -- "No (timeout)" --> FailLock["LOCK -> liveness_failed\nShow: 'LIVENESS TEST FAILED'"]
    FailLock --> Terminal
    LiveResult -- Yes --> IdCheck{"identified_name set,\nnon-Unknown, zero mismatch streak?"}
    IdCheck -- Yes --> ConfirmedName["confirmed_name := identified_name"]
    IdCheck -- No --> NullName["confirmed_name := None"]
    ConfirmedName --> SuccessLock["LOCK -> liveness_success\n(2s banner)"]
    NullName --> SuccessLock
    SuccessLock --> HadName{"Was confirmed_name set?"}
    HadName -- Yes --> Confirmed["LOCK -> confirmed\nShow: 'ATTENDANCE CONFIRMED: name'"]
    HadName -- No --> NotRecognized["LOCK -> not_recognized\nShow: 'FACE NOT RECOGNIZED'"]
    Confirmed --> Terminal
    NotRecognized --> Terminal

    Terminal["TERMINAL OUTCOME\n(confirmed / not_recognized /\nliveness_failed / duplicate_checkin)"] --> Timing["terminal_outcome_at set (once)\nrecognition/liveness/decision\ndurations finalized"]
    Timing --> LogRow["log_attendance()\n-> logs/attendance.csv"]
    LogRow --> SaveSnap["Save verification snapshot\n-> logs/snapshots/"]
    SaveSnap --> ResetGate["can_reset() true\n-> 'New check-in' enabled"]
    ResetGate -- "reset" --> Frame
```

### 2c. Engine state diagram (compact)

```mermaid
stateDiagram-v2
    [*] --> Recognizing
    Recognizing --> Recognizing: 0 faces / >1 faces / no match
    Recognizing --> IdentityLocked: registered match + continuity holds
    IdentityLocked --> Recognizing: continuity broken (3rd mismatch)
    IdentityLocked --> duplicate_checkin: already checked in this session
    IdentityLocked --> LivenessChallenge: not a duplicate
    LivenessChallenge --> liveness_failed: 10s timeout, blink+turn incomplete
    LivenessChallenge --> liveness_success: blink + correct head-turn
    liveness_success --> confirmed: confirmed_name was set
    liveness_success --> not_recognized: confirmed_name is None
    duplicate_checkin --> [*]: log + snapshot, wait for reset
    liveness_failed --> [*]: log + snapshot, wait for reset
    confirmed --> [*]: log + snapshot, wait for reset
    not_recognized --> [*]: log + snapshot, wait for reset
    [*] --> Recognizing: reset() / new attempt
```

## Related Documentation

- [[architecture]] — prose detail behind every box above.
- [[decisions]] — why each safeguard (continuity guard, duplicate-before-liveness, multi-face pause, etc.) was added.
- [[bugs]] — bugs found and fixed in this flow.
- [[report]] — Section 8.7 has an earlier, `CheckinSession`-only version of the ASCII flowchart (Fig. 2) for the IEEE report; this file supersedes it with the full app-level flow including `checkin_app`'s session picker and the dashboard.
