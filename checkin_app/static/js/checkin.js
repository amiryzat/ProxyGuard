// checkin_app -- live check-in page behavior.
// Unchanged from the original inline version except for one addition: the
// status card's neutral/success/warning/failure tone, derived client-side
// from the same `phase` field /status already returned (no backend change).

const statusEl = document.getElementById('status');
const statusCard = document.getElementById('status-card');
const newBtn = document.getElementById('newCheck');

// Maps CheckinSession.flow_phase (src/main.py) to a restrained visual tone.
// null/"liveness_success" -> neutral/in-progress; "confirmed" -> success;
// "not_recognized" -> warning (ambiguous, not necessarily wrong);
// "liveness_failed"/"identity_mismatch" -> failure.
function statusClassForPhase(phase) {
    if (phase === 'confirmed') return 'status-success';
    if (phase === 'not_recognized') return 'status-warning';
    if (phase === 'liveness_failed' || phase === 'identity_mismatch') return 'status-failure';
    return ''; // neutral: no active phase yet, or mid-challenge (liveness_success)
}

async function poll() {
    try {
        const r = await fetch('/status', { cache: 'no-store' });
        const s = await r.json();
        if (s.message) statusEl.textContent = s.message;
        statusCard.className = 'card status-card ' + statusClassForPhase(s.phase);
        // Enable "New check-in" only at a terminal outcome, mirroring the
        // desktop's 'n'-only-when-terminal behavior.
        newBtn.disabled = !s.can_reset;
    } catch (e) {
        /* keep the last shown status on a transient polling error */
    }
}

newBtn.addEventListener('click', async () => {
    newBtn.disabled = true;
    await fetch('/reset', { method: 'POST' });
});

setInterval(poll, 500);
poll();
