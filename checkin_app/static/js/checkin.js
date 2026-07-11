// checkin_app -- shared behavior for both the setup picker and the live
// check-in page. Guarded by element existence (elements from the OTHER page
// are simply absent from the DOM) so one file can be included on both
// templates without a second near-duplicate copy.

// ---- Setup page: cover the picker with the check-in skeleton on submit ----
// The POST to /start blocks on loading face-recognition data and opening the
// camera (~20s) before it redirects -- see checkin_app/app.py's
// _start_station(). Without this, the picker just sits there looking frozen
// for the whole wait.
(function () {
    const form = document.getElementById('setupForm');
    if (!form) return; // this is the check-in page, not the setup page

    const startBtn = document.getElementById('startBtn');
    const pickerContainer = document.getElementById('picker-container');
    const skeletonWrapper = document.getElementById('checkin-skeleton-wrapper');

    form.addEventListener('submit', function (event) {
        if (!form.checkValidity()) {
            form.reportValidity();
            return; // let the browser show its native validation UI; no skeleton
        }

        event.preventDefault(); // we submit programmatically below, after one paint

        startBtn.disabled = true;
        startBtn.textContent = 'Starting…';
        // Note: deliberately NOT disabling the <select> elements -- a disabled
        // form control is excluded from the submitted form data entirely, which
        // would strip subject/week from the POST and fail server-side
        // validation. Hiding the whole picker container below already makes
        // them non-interactive; disabling the button is safe since its own
        // value isn't read server-side.
        pickerContainer.hidden = true;
        skeletonWrapper.hidden = false;
        skeletonWrapper.setAttribute('aria-busy', 'true');

        // Two deferrals (next animation frame, then a 0ms timeout) guarantee
        // the browser paints the skeleton before the real navigation begins --
        // calling form.submit() synchronously here can otherwise start the
        // POST/navigation before anything new has been painted.
        requestAnimationFrame(function () {
            setTimeout(function () { form.submit(); }, 0);
        });
    });
})();

// ---- Check-in page: live status, skeleton -> real content handoff --------
(function () {
    const statusEl = document.getElementById('status');
    const statusCard = document.getElementById('status-card');
    const newBtn = document.getElementById('newCheck');
    const endBtn = document.getElementById('endSession');
    if (!newBtn) return; // this is the setup page, not the check-in page

    const skeleton = document.getElementById('checkin-skeleton');
    const skeletonStatusText = document.getElementById('skeleton-status-text');
    const skeletonError = document.getElementById('skeleton-error');
    const skeletonRetryBtn = document.getElementById('skeleton-retry-btn');
    const realContent = document.getElementById('real-checkin');
    const videoImg = document.getElementById('videoFeed');

    // Maps CheckinSession.flow_phase (src/main.py) to a restrained visual tone.
    // null/"liveness_success" -> neutral/in-progress; "confirmed" -> success;
    // "not_recognized"/"duplicate_checkin" -> warning (ambiguous or already
    // handled, not a failed identity/liveness check);
    // "liveness_failed"/"identity_mismatch" -> failure.
    function statusClassForPhase(phase) {
        if (phase === 'confirmed') return 'status-success';
        if (phase === 'not_recognized' || phase === 'duplicate_checkin') return 'status-warning';
        if (phase === 'liveness_failed' || phase === 'identity_mismatch') return 'status-failure';
        return ''; // neutral: no active phase yet, or mid-challenge (liveness_success)
    }

    // ---- Reveal the real page only once BOTH are true: the MJPEG stream has
    // decoded a genuine first frame, and /status reports the station active.
    // Never on a fixed timeout for the normal case (requirement 5) -- a
    // timeout only fires the failure path below if readiness never arrives.
    let frameReady = false;
    let stationActive = false;
    let revealed = false;
    let failed = false;

    function tryReveal() {
        if (revealed || failed || !frameReady || !stationActive) return;
        revealed = true;
        skeleton.hidden = true;
        realContent.hidden = false;
    }

    function showSkeletonError(message) {
        if (failed || revealed) return;
        failed = true;
        if (skeletonStatusText) skeletonStatusText.textContent = message;
        if (skeletonError) skeletonError.hidden = false;
    }

    if (videoImg) {
        videoImg.addEventListener('load', function () {
            frameReady = true;
            tryReveal();
        }, { once: true });
        // The stream connection itself failing outright (not just "no frame
        // yet") -- surface it as a failure instead of waiting out the timeout.
        videoImg.addEventListener('error', function () {
            showSkeletonError('Could not start the camera stream.');
        });
    }

    if (skeletonRetryBtn) {
        skeletonRetryBtn.addEventListener('click', function () {
            window.location.reload();
        });
    }

    const READY_TIMEOUT_MS = 30000;
    setTimeout(function () {
        if (!revealed) {
            showSkeletonError('Camera/session startup is taking longer than expected.');
        }
    }, READY_TIMEOUT_MS);

    async function poll() {
        try {
            const r = await fetch('/status', { cache: 'no-store' });
            const s = await r.json();
            if (s.active) {
                stationActive = true;
                tryReveal();
            }
            if (s.message) statusEl.textContent = s.message;
            statusCard.className = 'card status-card ' + statusClassForPhase(s.phase);
            // Enable "New check-in" only at a terminal outcome, mirroring the
            // desktop's 'n'-only-when-terminal behavior.
            newBtn.disabled = !s.can_reset;
        } catch (e) {
            /* keep the last shown status/skeleton on a transient polling error */
        }
    }

    newBtn.addEventListener('click', async () => {
        newBtn.disabled = true;
        await fetch('/reset', { method: 'POST' });
    });

    // Release the camera/session server-side (stops the MJPEG generator,
    // cv2.VideoCapture.release()) before navigating back to setup -- otherwise
    // the backend keeps the webcam open even though the browser has moved on.
    endBtn.addEventListener('click', async () => {
        endBtn.disabled = true;
        try {
            await fetch('/end_session', { method: 'POST' });
        } finally {
            window.location.href = '/';
        }
    });

    setInterval(poll, 500);
    poll();
})();
