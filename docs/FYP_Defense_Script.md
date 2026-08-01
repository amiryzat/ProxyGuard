# FYP Defense Script (10 Minutes, 23 Slides)
## Vision-Aware Smart Power Management System

**This is a proposal defense.** Nothing has been built or tested yet, so the whole script below is written in future or planning tense: "I will," "the system will," "I plan to," "this is designed to." Watch for any slip into "I built" or "this shows," those imply a finished, tested product, which isn't where you are yet.

**Total budget: 10:00. Target: finish by 9:40, leaving a 20 second buffer.**

Speaking pace target: roughly 140 words per minute. If you're a slower speaker, trim the optional lines marked *(cut if short on time)* first.

---

## HOW THE TIME IS SPLIT

| Section | Slides | Time | Why |
|---|---|---|---|
| Opening | 1-2 | 0:35 | Fast, just orient the panel |
| Chapter 1 | 3-7 | 2:10 | Context only, panel already has the report |
| Chapter 2 | 8-12 | 1:50 | Justify your choices, don't re-teach the literature |
| Chapter 3 | 13-20 | 3:15 | This is your planned methodology, most time goes here |
| System Architecture | 21 | 1:30 | The single most important slide, slow down here |
| Closing | 22-23 | 0:40 | Confident, short |

That totals 9:40 with a 20 second cushion.

---

## SLIDE 1: TITLE (0:00-0:20)

Stand still, look at the panel, don't rush the first line.

> "Good morning/afternoon. My name is Mohamad Amir Izzat Bin Rosdi, and I'll be presenting my proposed project, Vision-Aware Smart Power Management System for Room-Level Energy Optimisation Based on Activity Detection, under the supervision of Dr. Zaaba Bin Ahmad. I'll walk through the problem I'm addressing, the literature that shaped my approach, and how I plan to build and evaluate the prototype."

---

## SLIDE 2: AGENDA (0:20-0:35)

> "I'll go through three chapters: the background and objectives behind this project, the literature review that led to my technical decisions, and the methodology I'll be following, which is where most of today's time will go, since that's really the plan for how this gets built."

---

## CHAPTER 1: SLIDES 3-7 (0:35-2:45)

### Slide 3: Project Background (0:35-1:10)

> "Buildings occupied for a large share of global energy use, and most home automation today still runs on fixed timetables that don't reflect how a room is actually being used. What's changed recently is that vision-based activity recognition can now capture far richer context than a simple sensor, and edge computing lets that processing happen locally, which cuts latency and avoids the privacy risk of streaming video to the cloud. So what I'm proposing is to bring those two developments together, using local, vision-based activity recognition to optimise power delivery at the room level."

### Slide 4: Problem Statement (1:10-1:45)

> "There are three specific gaps I'm responding to. First, current smart home systems can't understand the context of what an occupant is actually doing, which leads to wasted energy. Second, standard PIR sensors only pick up motion, so someone sitting still, reading or working at a desk, gets missed entirely. And third, the vision-based commercial systems that do exist are mostly cloud-reliant, which raises real privacy concerns, especially for private spaces like bedrooms. My system is designed to tackle all three of these at once."

### Slide 5: Project Objectives (1:45-2:15)

> "That gives me three objectives. First, to design a context-aware decision logic layer that will map detected activity to power control actions through IoT. Second, to develop an occupant activity detection module using computer vision on a single edge device. And third, to evaluate the accuracy of that activity detection and the performance of the proposed system."

### Slide 6: Project Scope (2:15-2:45)

> "To keep this manageable and testable, I've set three boundaries. Testing will be confined to a single room, running entirely on one local edge device with no cloud dependency. The vision module will be limited to three occupancy classes, sitting, sleeping, and absent, and I'm deliberately excluding PIR sensors so I can isolate and properly evaluate the vision module on its own merit. And the deployment will stay as a single node, not a multi-camera setup or a full IoT network, so I can keep the focus on the core algorithmic logic rather than getting pulled into networking complexity."

### Slide 7: Project Significance (2:45-3:05)

> "If this works as intended, the contribution will be threefold: better contextual accuracy than motion-based detection, more intelligent power decisions instead of binary on-off switching, for example dimming when someone is asleep rather than just cutting power outright, and privacy that's preserved entirely through local, on-device processing." *(cut if short on time: "with no cloud transmission at all")*

---

## CHAPTER 2: SLIDES 8-12 (3:05-4:55)

### Slide 8: Divider (verbal only, no pause)

> "That's the background. Now, briefly, the literature that shaped these technical decisions."

### Slide 9: Conceptual Map (3:05-3:35)

> "My research sits within the Internet of Things, and I've organised the review around three pillars: Human Activity Recognition, Edge AI implementation, and context-aware decision frameworks, all of which feed into the applied domain of Smart Home Energy Systems."

### Slide 10: Research Area, IoT (3:35-4:00)

> "Each of these pillars shows a clear progression in the literature. Activity recognition has moved from simple sensors to computer vision, and now to Vision-Language Models, which is the direction I'll be taking. Edge AI implementation has shifted from cloud processing toward local edge computing, which I've chosen for privacy and latency reasons. And decision frameworks have evolved from fixed schedules to AI forecasting, and now toward real-time VLM-based reasoning, again the approach I'll be implementing."

### Slide 11: Research Domain, SHEMS (4:00-4:25)

> "Within Smart Home Energy Systems specifically, occupancy control still mostly relies on PIR sensors, appliance management still depends heavily on direct user interaction rather than passive intelligence, and commercial platforms like Alexa, Google Home, and HomeKit remain schedule-based, with no context-aware decision engine at all. That's the gap I'm aiming to fill."

### Slide 12: Comparison of Similar Systems (4:25-4:55)

Don't read the whole table. Point at it and summarise.

> "This table compares my proposed system against the three major commercial platforms. The short version: none of them support VLM-based scene understanding, none of them have a context-aware decision engine, and all of them rely on the cloud to some degree. By design, my proposed system will be the only one here that's fully local and reasons about the actual scene instead of following a fixed schedule."

---

## CHAPTER 3: SLIDES 13-20 (4:55-8:10)

### Slide 13: Divider (verbal only)

> "So that brings me to the methodology, which is the plan for how this actually gets built."

### Slide 14: Project Methodology, Waterfall SDLC (4:55-5:25)

> "I'll be following the Waterfall model, because the scope, the hardware, and the requirements are all fixed and known upfront, which suits a linear, sequential process much better than an iterative one for a prototype with a defined timeframe. There are six stages: requirement analysis, system design, implementation, integration and testing, deployment, and maintenance. Maintenance is scoped in the report but won't actually be carried out, since this prototype isn't going into a real household."

### Slide 15: Requirement Analysis (5:25-5:45)

> "In stage one, I'll derive functional and non-functional requirements directly from the gaps identified in my literature review, functional requirements around passive vision classification and active gesture override, and non-functional requirements around strict local processing, low latency, and no cloud dependency."

### Slide 16: System Design (5:45-6:05)

> "Stage two is where the full technical blueprint gets locked in: the five-layer architecture, which I'll walk through in detail shortly, the selection of Moondream2 and MediaPipe Hands as the core models, and the definition of four passive activity profiles and three hand gestures, all decided before any physical building begins."

### Slide 17: Implementation (6:05-6:25)

> "Stage three is where the design gets turned into working code and hardware. I'll build a dual-mode Python runtime combining OpenCV, MediaPipe, and the Ollama library, set up PySerial communication to the Arduino, and assemble the physical breadboard circuit."

### Slide 18: Integration and Testing (6:25-6:45)

> "Stage four connects the software and hardware into a single pipeline. I'll test all seven system response paths, four passive and three active, and specifically stress-test the hold-state fallback mechanism with deliberate edge cases, to confirm the system doesn't flicker between states when a scene is ambiguous."

### Slide 19: Deployment and Evaluation (6:45-7:10)

> "Stage five will be a controlled tabletop demonstration, not a real household deployment, and I'll evaluate it against three metrics: activity classification accuracy across all seven response types, with a minimum of ten trials per response and seventy data points overall, response latency measured separately for active and passive mode, and Simulated Appliance Activation Reduction, comparing adaptive output activation time against a fixed-on baseline."

### Slide 20: Summary, RO Mapping (7:10-7:25)

> "This table just confirms the traceability of the plan: objective one maps to stages one and two, objective two to stages three and four, objective three to stage five. So every objective is accounted for by at least one development stage."

---

## SLIDE 21: SYSTEM ARCHITECTURE (7:25-8:55)

**This is your most important slide. Slow down, use the diagram, point as you talk.**

> "This is the full pipeline as designed. It will run in two modes that share the same camera input and the same actuation output, but take completely different paths through the middle layers, and only one mode will be active per frame.

> Starting at the top, the Perception Layer will capture video through the built-in camera using OpenCV. That feeds into the Pre-Processing Layer, where MediaPipe Hands checks every frame for a hand. If a hand is confidently detected, the system will route to Active Mode. If not, it defaults to Passive Mode.

> In Active Mode, MediaPipe will map twenty-one 3D hand landmarks and classify the gesture geometrically, since this is essentially coordinate math, it should run in real time with almost no delay. In Passive Mode, a frame will be sampled every three seconds and sent to Moondream2, a locally-hosted Vision-Language Model, to generate a scene description, standing, sitting, resting, or absent.

> That output then goes into the Decision Logic Layer, which has two branches. The active branch will map three gestures directly to commands: an open palm toggles the TV, a peace sign toggles the lights, and a closed fist acts as a universal override that shuts everything off. The passive branch will map the VLM's scene description to one of four energy profiles: Profile T for transitional, when someone is standing or walking, Profile A for active, when they're sitting or working, Profile B for resting, when they're sleeping or lying down, and Profile C for unoccupied, when the room is empty.

> If the description turns out to be too ambiguous to confidently classify, the system is designed to hold the last known state rather than switch, so it won't flicker on unclear input.

> Finally, whichever branch fires, the command will travel over PySerial at 9600 baud to an Arduino Uno, which will drive three LEDs simulating room lights, the TV, and the fan or air conditioning."

*(That's roughly 320 words at conversational pace, closer to 2:00-2:10. If you're running over, cut the sentence about hold-state fallback and the LED naming, the panel can see the LEDs labeled in the diagram already.)*

---

## SLIDE 22: CONCLUSION (8:55-9:35)

> "To wrap up, this project sets out to replace context-blind automation with a system that will actually understand what's happening in a room before it acts. The five-layer architecture is designed to let a single local device do that, passive scene understanding for background intelligence, and active gesture recognition for direct manual control, with everything processed on-device, so nothing needs to leave the room. The Waterfall methodology gives me a traceable, verifiable path from requirements through to evaluation, and every research objective is mapped to a concrete deliverable along the way."

---

## SLIDE 23: THANK YOU (9:35-9:40)

> "Thank you. I'm happy to take any questions."

---

## LIKELY QUESTIONS TO BE READY FOR

- **"Why Waterfall and not Agile/Prototyping?"** → Requirements, hardware, and scope are fixed from the start, so there's no need for iterative re-scoping.
- **"Why Moondream2 and not a bigger VLM?"** → It's 1.86B parameters, 4-bit quantized, and should run locally on Apple Silicon in roughly 1-2 seconds per frame. Heavier models like LLaVA-7B would likely be too slow for real-time home automation on commodity hardware.
- **"Why sample every 3 seconds in passive mode?"** → It's meant to balance detection sensitivity against GPU load, so the reasoning cycle can finish before the next frame queues, avoiding memory bottlenecks.
- **"What happens if the VLM output doesn't match any profile?"** → The hold-state fallback is designed to keep the last known state rather than issue a new command, to prevent erratic switching from ambiguous scenes.
- **"Why exclude PIR sensors entirely?"** → To isolate and properly test the vision module's capability on its own, since PIR sensors would miss stationary occupants like someone sleeping or reading.
- **"How will you measure the energy claim?"** → Through Simulated Appliance Activation Reduction, comparing total adaptive output activation time against a fixed-on baseline in an equivalent test session. This will be a simulated LED prototype, not a real household deployment.

---

## DELIVERY NOTES

- Practice this out loud at least twice with a timer before tomorrow. The architecture slide is the one place small overruns compound, so time that section specifically.
- If you're running short on time anywhere in Chapter 1 or 2, cut the *(cut if short)* lines first, never cut time from the Architecture slide.
- For the comparison table (slide 12) and the summary table (slide 20), don't read every cell, gesture at the table and give the one-sentence takeaway.
- Keep your eyes on the panel during the architecture explanation, not the screen, you know this design better than anyone in the room.
- If a panel member slips and asks "how does the system perform," it's fine to gently clarify: "That's part of what this proposal sets up to test, once built, I'll be measuring exactly that against the three metrics on slide 19."
