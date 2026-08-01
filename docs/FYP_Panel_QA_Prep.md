# Anticipated Panel Questions and Answers
## Vision-Aware Smart Power Management System

This is organised from most likely to catch you off guard to more standard defense questions. The first section targets actual inconsistencies or gaps found in your own report, things a panel member who reads closely could catch. The rest target conceptual weaknesses in the design itself. Read the "why this is dangerous" line for each one honestly, it tells you what the panel member is really probing for.

---

## SECTION A: THINGS IN YOUR OWN REPORT THAT DON'T QUITE LINE UP

These are the ones most likely to actually catch you off guard, because they come from a careful cross-read of your own chapters, not from outside knowledge.

### 1. "Your scope says three occupancy classes. Your methodology describes four profiles. Which is it?"

**Why this is dangerous:** Chapter 1, Section 1.4 explicitly says the vision module is limited to three classes: sitting, sleeping, and absent. But Chapter 3 defines four passive energy profiles: Profile T for transitional (standing or walking), Profile A for active (sitting), Profile B for resting (sleeping), and Profile C for unoccupied (absent). A panel member who flips between chapters will notice the mismatch immediately.

**Best answer:** "That's a fair catch. The scope in Chapter 1 was written around the three core occupancy states that matter most for energy decisions, sitting, sleeping, and absent. During system design, I added a fourth transitional state to handle the moment someone is entering or moving through the room, since treating that the same as 'sitting' would mean the lights come on at full brightness before the person has actually settled anywhere. So the transitional profile is really a refinement of the 'sitting' class rather than a new occupancy class outside the original scope, it's about giving the decision layer a more graceful handoff. I recognise the wording in Chapter 1 should be tightened to reflect that before final submission."

*(If pushed further: this is a genuinely honest gap. Don't over-defend it, acknowledge it as a documentation inconsistency you'll fix, not a design flaw. Panels respect a clean "you're right, I'll correct that" more than a stretched justification.)*

---

### 2. "You claim your system will have higher accuracy than PIR sensors, but you've excluded PIR sensors from your testing. How can you support that claim if you never test against one?"

**Why this is dangerous:** Chapter 1.5, Significance of Study, states the system "will be able to overcome the analytical limitations of conventional passive infrared sensors." But Chapter 1.4, Scope, explicitly excludes PIR sensors from the implementation entirely, specifically to isolate the vision module. That means the comparative claim in Significance is never actually tested against a live PIR baseline in this project. This is a real logical gap between a claim and what the methodology can actually prove.

**Best answer:** "That's an important distinction. The comparison to PIR sensors is a literature-based claim, not something I'll be empirically testing head-to-head in this project. The literature review documents PIR's known failure mode, it can't detect stationary occupants like someone sitting still or sleeping, because it only reacts to motion. My contribution isn't to run a side-by-side PIR versus VLM experiment, it's to demonstrate that a vision-based system can correctly classify those stationary states that PIR is documented to miss. So the claim in Chapter 1 is really about closing a known, published gap, not a claim I'm empirically benchmarking against a PIR unit in this specific study. I'd word that more precisely as 'addresses a documented limitation of PIR-based systems' rather than 'outperforms PIR' to avoid overstating it."

---

### 3. "Chapter 1 talks about evaluating 'energy saving performance,' but your Chapter 3 evaluation uses the term 'Simulated Appliance Activation Reduction.' Why the different terminology, and are they actually measuring the same thing?"

**Why this is dangerous:** This is a real terminology shift between chapters. If a panel member asks you to define either term precisely, you need a clean answer, not a shrug.

**Best answer:** "They refer to the same underlying metric. Chapter 1 uses more general language since it's describing the objective at a high level, but through supervisor feedback during the methodology stage, I refined that into a more precise and honest term, Simulated Appliance Activation Reduction, because this prototype uses LED simulation rather than real appliances, and I don't want to imply I'm measuring actual household energy consumption in watts or kilowatt-hours. What I am measuring is the reduction in total output activation time compared to a fixed-on baseline, which is a proxy for energy savings, not a direct energy measurement. I plan to align the wording in Chapter 1 with that more precise term before final submission."

---

## SECTION B: TECHNICAL DESIGN WEAKNESSES

### 4. "Sleep detection relies on the camera seeing the person. Most people sleep in the dark or with the lights off. How will your VLM classify someone as sleeping if the room is too dark for the camera to see clearly?"

**Why this is dangerous:** This is a genuine, unaddressed weakness. Profile B triggers on the keyword "sleeping," but sleep typically happens in low light, exactly the condition vision models struggle with most.

**Best answer:** "That's a real limitation I haven't fully solved in this proposal, and I want to be upfront about it rather than claim otherwise. The current design assumes reasonable ambient lighting, and low-light performance isn't something I'm scoping into this evaluation. In practice, the hold-state fallback should partially cover this, if the VLM can't confidently describe the scene in poor lighting, the system holds the last known state rather than guessing wrong, which is safer than a false transition. But I'd frame this honestly as a documented limitation and a direction for future work, possibly pairing the VLM with a low-light image enhancement step, or falling back to a simpler motion cue specifically for the sleep transition, rather than something I'm claiming to solve in this project."

---

### 5. "Your passive branch works by keyword matching against the VLM's natural language output. What happens if Moondream2 describes the scene using different words than the ones you're matching for, for example, 'reclining' instead of 'sleeping'?"

**Why this is dangerous:** Keyword matching against free-form natural language output is inherently brittle. This is a legitimate architectural fragility.

**Best answer:** "That's a known limitation of keyword-based matching against a generative model's output, and it's part of why the hold-state fallback exists, if the description doesn't match any of the expected keywords, the system doesn't guess, it just holds the previous state rather than misclassifying. To reduce how often that happens, the prompt to Moondream2 is deliberately constrained, I ask it to classify the activity as one of a fixed set of options rather than describe the scene freely, which narrows the vocabulary it's likely to use. During integration testing, I plan to log any VLM outputs that fail to match, so I can expand the keyword set based on real observed phrasing rather than guessing at it upfront."

---

### 6. "Moondream2 takes one to two seconds per frame. What happens if someone makes a gesture while the system is in the middle of a passive inference cycle? Could the system miss an active mode command because it's still busy processing a passive frame?"

**Why this is dangerous:** This is a real concurrency question. If VLM inference is blocking, a gesture during that window could genuinely be missed, and the report doesn't describe how this race condition is handled.

**Best answer:** "That's a fair concern about the pipeline's concurrency behaviour. The pre-processing layer, MediaPipe hand detection, runs independently of the VLM inference and is lightweight enough to check every incoming frame regardless of what the passive branch is doing. So in principle, a hand appearing mid-inference should still be caught by the next frame's hand-detection check, since that check happens before the frame is routed anywhere. Where it could genuinely cause a problem is if the system is single-threaded and the VLM call blocks the whole loop, in which case a gesture during that one to two second window could be delayed rather than missed outright. I'll be testing this specific scenario directly during integration testing, and if it turns out to be a real bottleneck, the fix would be running the VLM inference in a separate thread so hand detection is never blocked."

---

### 7. "Your literature review cites systems running on a Raspberry Pi for real-time gesture control. Your own system requires a full laptop with a minimum of 16GB of RAM. Isn't that a step backward for edge deployment, compared to the embedded systems you're citing as prior work?"

**Why this is dangerous:** This is a legitimate conceptual tension. True "edge AI" research usually targets resource-constrained embedded hardware. Running a VLM that needs 16GB of RAM is local processing, but it's a much heavier device than the Raspberry Pi-class systems cited in your own literature review.

**Best answer:** "That's a fair distinction, and I'd separate two different things labelled 'edge' in the literature. The Raspberry Pi systems I cite handle gesture classification, which is lightweight, geometric, coordinate-based math, MediaPipe on a Pi 5 is genuinely feasible. What I'm running additionally is a Vision-Language Model for semantic scene understanding, and that workload is significantly heavier than gesture classification alone, current lightweight VLMs still need more memory and compute than a Raspberry Pi can offer. So my definition of 'edge' here is specifically 'local processing without cloud dependency,' not 'runs on minimal embedded hardware.' The privacy and latency benefits of local processing still hold on a laptop-class device, but I agree it's a fair limitation to acknowledge, this prototype trades hardware minimalism for the richer semantic reasoning a VLM provides, and shrinking that further onto genuinely embedded hardware would be a meaningful next step."

---

### 8. "Your architecture assumes one person in the room. What happens if there are two occupants, one sitting and one standing? Which profile does the system choose?"

**Why this is dangerous:** The whole passive branch assumes a single, unambiguous room-level activity state. Multi-occupant scenarios are never addressed in the report.

**Best answer:** "That's outside the current scope, and I should be direct about that rather than improvise an answer that isn't backed by the design. The project scope is deliberately limited to single-room, effectively single-occupant testing, so multi-person scenes weren't part of the evaluation plan. In practice, Moondream2 would likely generate a description of whichever activity is most visually dominant in the frame, but I haven't defined a specific resolution rule for conflicting activities, and I'd flag that as a limitation rather than claim the system handles it gracefully. Extending the profile logic to reason about multiple occupants, perhaps by prioritising the highest-power-need state present in the room, would be a natural next step beyond this project's scope."

---

## SECTION C: EVALUATION AND VALIDITY WEAKNESSES

### 9. "Ten trials per response type, seventy data points total, is that really enough to draw a reliable conclusion about accuracy?"

**Why this is dangerous:** Ten trials per class is a small sample. A statistically literate panel member may ask about confidence intervals or variance, which the current evaluation plan doesn't account for.

**Best answer:** "I'd frame this honestly as the minimum threshold for a demonstrable trend, not a statistically powered study. Given the time constraints of an undergraduate FYP and the fact that this is a controlled tabletop demonstration rather than a longitudinal deployment, ten trials per response type is meant to establish whether the classification behaves consistently rather than to produce a publication-grade confidence interval. If time allows, I'd like to increase the trial count and report per-class precision and recall rather than a single blended accuracy figure, since that would show more clearly whether errors are concentrated in a particular profile, for example transitional versus active, rather than spread evenly."

---

### 10. "You're evaluating this whole system on LEDs, not real appliances. How confident are you that results from blinking LEDs actually generalise to real-world appliance behaviour?"

**Why this is dangerous:** LEDs have none of the switching latency, inrush current, or thermal behaviour of a real TV, light, or air conditioner. The gap between simulated and real load is a legitimate validity concern.

**Best answer:** "I'd be upfront that the LED simulation validates the decision logic and the software-to-hardware signalling path, not the real electrical or mechanical behaviour of actual appliances. What I'm proving is that a given activity classification reliably produces the correct control signal at the correct time, that's the core research contribution. Scaling from an LED to an actual relay controlling a lamp or fan is a hardware substitution, not a logic change, the same single-character serial command would drive a relay module instead of an LED. I'd treat the LED-to-relay transition as future engineering work rather than a gap in the core research claim, but I agree it's important not to imply this project measured real-world energy consumption, because it doesn't."

---

### 11. "What accuracy percentage would you consider a success, and what would count as this project failing?"

**Why this is dangerous:** The report doesn't currently define a target threshold. If you don't have a number ready, this can look like the evaluation criteria were never really pinned down.

**Best answer:** "I haven't fixed a strict numerical pass or fail threshold in the current proposal, since undergraduate FYP evaluation criteria generally focus on demonstrating a working, traceable methodology rather than hitting an industry benchmark. That said, if I had to commit to a number, I'd want to see classification accuracy meaningfully above chance across four passive profiles, which is 25%, so I'd consider anything consistently above roughly 80% across the seven response paths a strong result, with lower accuracy in the transitional profile being more forgivable given its inherent ambiguity between standing and just having sat down."

---

## SECTION D: SCOPE AND GENERALISABILITY

### 12. "MediaPipe's hand detection was trained on specific datasets. Have you considered whether it performs consistently across different skin tones, hand sizes, or clothing, like someone wearing long sleeves or gloves?"

**Why this is dangerous:** This is a fairness and robustness question that a lot of student projects don't think about until asked. MediaPipe's published benchmarks do have known variance across conditions, and your evaluation plan doesn't mention testing across diverse users.

**Best answer:** "That's a legitimate limitation I haven't built into the evaluation plan. MediaPipe Hands is a pre-trained, general-purpose model, and I'm relying on its published robustness rather than validating it myself across a diverse set of users, skin tones, or clothing conditions. Given the single-room, single-evaluator nature of this prototype, that kind of robustness testing is genuinely out of scope for the current project, but I'd flag it as an important limitation to state explicitly in my final report rather than leave it implied. It would be a meaningful area for follow-up work if this were extended beyond a proof-of-concept."

---

### 13. "This entire system is tested in one room, by presumably one person, under conditions you control. What confidence do you actually have that this generalises to a real household?"

**Why this is dangerous:** This is the classic "your n equals one" question. It's broad, but it's the kind of question that's easy to fumble if you try to oversell generalisability.

**Best answer:** "Honestly, limited, and that's intentional given the scope I set. This project is a proof-of-concept, meant to demonstrate that the architecture, passive VLM reasoning combined with active gesture override, is technically feasible and behaves correctly under controlled conditions. It isn't designed to prove generalisation across different rooms, lighting setups, camera placements, or multiple users, that would require a much larger, longer-running study. I'd position this project as establishing feasibility and a testable architecture, with generalisation being the explicit next phase of research rather than something this particular project claims to have solved."

---

### 14. "You emphasise privacy as a major benefit because everything is processed locally. But the camera is still capturing footage of people in private spaces. Doesn't 'local' just move the privacy risk rather than eliminate it?"

**Why this is dangerous:** This is a nuanced ethical question. Local processing does remove the cloud transmission risk, but it doesn't eliminate all privacy exposure, someone could still access the local machine, or simply object to being recorded at all regardless of where the data goes.

**Best answer:** "That's a fair nuance, and I'd narrow my privacy claim to be precise about what it actually addresses. Local processing specifically removes the risk of continuous video being transmitted to and stored on external servers, which is the privacy failure mode most associated with commercial cloud-based smart home cameras, and it's the specific concern raised in my problem statement. It doesn't eliminate every privacy consideration, someone with physical or remote access to the local machine could still view captured frames, and the fact that a camera is active in a private space at all is itself a consideration regardless of where processing happens. I'd describe the benefit as 'removes cloud-transmission privacy risk' rather than 'guarantees privacy,' since the second framing overstates what local processing actually solves."

---

## SECTION E: CURVEBALLS

### 15. "Why use a Vision-Language Model at all? Isn't this over-engineered? A basic PIR sensor plus a simple timer would solve most of this far more cheaply and reliably."

**Why this is dangerous:** This challenges the fundamental premise of the whole project. If you can't articulate why the added complexity is worth it, the panel may see the project as solving a problem that didn't need this much machinery.

**Best answer:** "That's really the core question the whole project is trying to answer, and it comes straight from the problem statement. A PIR sensor plus a timer is cheaper and simpler, but it's exactly the approach that fails on the two cases I'm targeting, distinguishing a stationary but present occupant from an absent one, and reacting to the specific activity rather than just presence or absence. A timer can't tell the difference between someone reading quietly and an empty room, and PIR sensors are documented in the literature to produce false negatives for exactly that reason. The added complexity of a VLM is specifically there to close that gap, richer context in exchange for more compute. Whether that trade-off is actually worth it in practice is precisely what my evaluation is designed to test, if the accuracy and latency don't justify the added complexity, that's a valid and interesting finding too, not just a risk to the project."

---

### 16. "If your hold-state fallback triggers whenever the VLM output is ambiguous, and natural language descriptions are often somewhat ambiguous, couldn't your system end up being less responsive in practice than the PIR sensors you're trying to improve on?"

**Why this is dangerous:** This connects two of your own design choices in a way that could genuinely undercut the core value proposition, if hold-state fires too often, the vision-based system could actually respond slower than what it's replacing.

**Best answer:** "That's a sharp observation, and it's a real risk I want to test for directly rather than assume away. The hold-state mechanism is a deliberate trade-off, I chose stability over responsiveness, because I'd rather the system do nothing on an uncertain frame than confidently switch to the wrong profile. Whether that trade-off tips too far toward passivity is an empirical question I plan to measure during integration testing, specifically by tracking how often hold-state fires across the seven response paths. If it turns out to fire excessively, that would tell me the keyword set needs to be broadened, or that the VLM prompt needs to be more tightly constrained, rather than that the fallback concept itself is wrong."

---

## HOW TO USE THIS LIST

- You will not get all sixteen of these. Skim it once tonight, then focus your actual rehearsal on Section A (the internal inconsistencies), since those are the ones a panel member can catch just by reading your own report closely, and they're the ones most likely to make you look unprepared if you're caught flat-footed.
- Notice the shape of most of these answers: acknowledge the limitation honestly, explain why it's in scope or out of scope, and point to what you'd measure or do next rather than pretend the concern doesn't exist. Panels respond far better to "that's a fair limitation, here's how I'd address it" than to a defensive answer that tries to argue the weakness away.
- If you get a question you genuinely don't have an answer for, it's fine to say "that's a good point I haven't fully worked out, my current thinking is X, but I'd want to test that directly before committing to an answer." That's a stronger response than guessing confidently and being wrong.
