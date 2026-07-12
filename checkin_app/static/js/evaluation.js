// checkin_app/static/js/evaluation.js -- Report Support Phase R1 (simplified
// automated evaluation mode) + Evaluation Mode Bug Fix (session sync,
// participant/scenario persistence, safe mid-trial session-change handling).
// Self-contained: does not load checkin.js (that file assumes checkin.html/
// setup.html's own elements), so this page has its own small script against
// the /evaluation/* routes in checkin_app/app.py.

const participantSelect = document.getElementById('participantSelect');
const scenarioSelect = document.getElementById('scenarioSelect');
const trialLabelPreview = document.getElementById('trialLabelPreview');
const startBtn = document.getElementById('startTrialBtn');
const nextTrialBtn = document.getElementById('nextTrialBtn');
const attachFallbackBtn = document.getElementById('attachFallbackBtn');
const timerRow = document.getElementById('timerRow');
const timerDisplay = document.getElementById('timerDisplay');
const statusText = document.getElementById('statusText');
const evalHint = document.getElementById('evalHint');
const panelTarget = document.getElementById('evaluation-panel-target');
const sessionSyncStatus = document.getElementById('sessionSyncStatus');
const setupUrl = document.body.dataset.setupUrl;

const PARTICIPANT_STORAGE_KEY = 'evalParticipant';
const SCENARIO_STORAGE_KEY = 'evalScenario';
const SESSION_POLL_MS = 3000;   // requirement 3: every 2-5s
const TRIAL_POLL_MS = 2500;
const FALLBACK_DELAY_MS = 8000; // only offer the manual fallback if auto-detect hasn't matched by then

let activeTrialId = null;
let activeTrialSessionId = null; // session_id locked in at Start Trial (requirement 8)
let currentSessionId = null;     // kept in sync by pollActiveSession(), never assumed
let trialStartMs = null;
let tickInterval = null;
let pollInterval = null;
let fallbackTimeout = null;

// ---- Requirement 4/5: restore participant/scenario, survive page reloads --
// localStorage (not Flask session) -- purely a client-side UI preference,
// no server round-trip needed, and it survives independently of whatever
// check-in session happens to be active.
(function restoreSelections() {
    const savedParticipant = localStorage.getItem(PARTICIPANT_STORAGE_KEY);
    if (savedParticipant && participantSelect.querySelector('option[value="' + savedParticipant + '"]')) {
        participantSelect.value = savedParticipant;
    }
    const savedScenario = localStorage.getItem(SCENARIO_STORAGE_KEY);
    if (savedScenario && scenarioSelect.querySelector('option[value="' + savedScenario + '"]')) {
        scenarioSelect.value = savedScenario;
    }
})();

function updateLabelPreview() {
    if (!startBtn.disabled || activeTrialId) return; // don't clobber an in-progress trial's label
    trialLabelPreview.textContent = participantSelect.value + ' - ' + scenarioSelect.value;
}
participantSelect.addEventListener('change', function () {
    localStorage.setItem(PARTICIPANT_STORAGE_KEY, participantSelect.value);
    updateLabelPreview();
});
scenarioSelect.addEventListener('change', function () {
    localStorage.setItem(SCENARIO_STORAGE_KEY, scenarioSelect.value);
    updateLabelPreview();
});
updateLabelPreview();

function refreshPanel() {
    fetch('/evaluation_panel')
        .then(function (r) { return r.text(); })
        .then(function (html) { panelTarget.innerHTML = html; })
        .catch(function () { /* transient network hiccup -- leave the panel as-is */ });
}

function startTick() {
    tickInterval = setInterval(function () {
        timerDisplay.textContent = ((Date.now() - trialStartMs) / 1000).toFixed(1) + 's';
    }, 100);
}

function describeResult(trial) {
    const verdict = trial.passed === 'pass' ? 'PASS' : 'FAIL';
    return (trial.actual_identity || 'Unknown') + ' / ' + (trial.actual_result || '?')
        + (trial.actual_reason ? ' / ' + trial.actual_reason : '') + '  ->  ' + verdict;
}

function stopTrialTimers() {
    clearInterval(tickInterval);
    clearInterval(pollInterval);
    clearTimeout(fallbackTimeout);
    tickInterval = null;
    pollInterval = null;
}

function finishTrialUI(trial) {
    stopTrialTimers();
    activeTrialId = null;
    activeTrialSessionId = null;
    statusText.textContent = describeResult(trial);
    attachFallbackBtn.hidden = true;
    nextTrialBtn.hidden = false;
    evalHint.hidden = true;
    refreshPanel();
}

function pollForMatch() {
    fetch('/evaluation/check')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.matched && data.trial) {
                finishTrialUI(data.trial);
            }
        })
        .catch(function (err) { console.warn('evaluation poll failed, will retry:', err); });
}

function resetForNextTrial() {
    timerRow.hidden = true;
    nextTrialBtn.hidden = true;
    attachFallbackBtn.hidden = true;
    evalHint.hidden = false;
    startBtn.hidden = false;
    startBtn.disabled = !currentSessionId;
    updateLabelPreview();
}

startBtn.addEventListener('click', function () {
    startBtn.disabled = true;
    fetch('/evaluation/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            participant_code: participantSelect.value,
            scenario: scenarioSelect.value,
        }),
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.error) {
                alert(data.error);
                startBtn.disabled = !currentSessionId;
                return;
            }
            // Requirement 7/8: start_timestamp and session_id are already
            // locked in server-side (data.trial.session_id/start_timestamp);
            // the client timer below is purely a live display, not the
            // source of truth for duration.
            activeTrialId = data.trial.trial_id;
            activeTrialSessionId = data.trial.session_id;
            trialStartMs = Date.now();
            trialLabelPreview.textContent = data.label;
            timerRow.hidden = false;
            statusText.textContent = 'Perform the check-in attempt now…';
            startBtn.hidden = true;
            startTick();
            pollInterval = setInterval(pollForMatch, TRIAL_POLL_MS);
            // Fallback button only appears if auto-detection hasn't matched
            // within a few seconds -- never required during normal operation.
            fallbackTimeout = setTimeout(function () {
                if (activeTrialId) attachFallbackBtn.hidden = false;
            }, FALLBACK_DELAY_MS);
            refreshPanel(); // show the new "pending" row immediately
        })
        .catch(function () {
            alert('Could not start the trial (network error).');
            startBtn.disabled = !currentSessionId;
        });
});

attachFallbackBtn.addEventListener('click', function () {
    if (!activeTrialId) return;
    attachFallbackBtn.disabled = true;
    fetch('/evaluation/attach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trial_id: activeTrialId }),
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            attachFallbackBtn.disabled = false;
            if (data.error) {
                alert(data.error);
                return;
            }
            finishTrialUI(data.trial);
        })
        .catch(function () {
            attachFallbackBtn.disabled = false;
            alert('Could not attach the latest attempt (network error).');
        });
});

nextTrialBtn.addEventListener('click', resetForNextTrial);

document.getElementById('exportCsvBtn').addEventListener('click', function () {
    window.location.href = '/evaluation/export.csv';
});

// ---- Requirement 2/3/8/9: sync with checkin_app's active session ----------
// Polls a lightweight endpoint (no full-page reload) so an active/inactive
// session change is reflected live. If a trial is currently pending and the
// session it was started under no longer matches, the trial is cancelled
// safely server-side (not silently left to match against a stale session).
function renderSyncStatus(data) {
    if (data.active) {
        sessionSyncStatus.className = 'eval-active-session';
        sessionSyncStatus.innerHTML =
            '<span class="eval-sync-ok">Synced with active check-in session</span>' +
            '<span class="eval-sync-line">Session: <span class="session-badge">' + data.session_id + '</span></span>';
    } else {
        sessionSyncStatus.className = 'error';
        sessionSyncStatus.innerHTML =
            'No active check-in session. <a href="' + setupUrl + '">Start a session from the session picker</a> first.';
    }
}

function pollActiveSession() {
    fetch('/evaluation/current-session')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            const newSessionId = data.active ? data.session_id : null;
            if (newSessionId === currentSessionId) {
                return; // nothing changed -- do NOT touch participant/scenario/timer/trial state
            }

            // A trial is running under the session that just changed/ended --
            // cancel it safely rather than let it silently keep waiting on a
            // now-stale session_id (requirement 8).
            if (activeTrialId && activeTrialSessionId && activeTrialSessionId !== newSessionId) {
                stopTrialTimers();
                fetch('/evaluation/cancel', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ trial_id: activeTrialId }),
                }).finally(function () {
                    activeTrialId = null;
                    activeTrialSessionId = null;
                    statusText.textContent = 'Active check-in session changed. Start a new evaluation trial.';
                    attachFallbackBtn.hidden = true;
                    nextTrialBtn.hidden = false;
                    evalHint.hidden = true;
                    refreshPanel();
                });
            }

            currentSessionId = newSessionId;
            renderSyncStatus(data);
            // Only touch the Start Trial button when idle -- never re-enable/
            // disable out from under a click while a trial is actually running.
            if (!activeTrialId) {
                startBtn.disabled = !newSessionId;
            }
        })
        .catch(function (err) { console.warn('session sync poll failed, will retry:', err); });
}

currentSessionId = (document.querySelector('.session-badge') || {}).textContent || null;
setInterval(pollActiveSession, SESSION_POLL_MS);

// On load: if a trial was left pending (e.g. the page was reloaded
// mid-trial), resume its timer/polling instead of silently losing track of
// it -- participant/scenario are already restored from localStorage above,
// independently of this.
(function resumeIfPending() {
    fetch('/evaluation/check')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.active) return;
            activeTrialId = data.trial_id;
            activeTrialSessionId = data.trial ? data.trial.session_id : currentSessionId;
            trialStartMs = data.trial && data.trial.start_timestamp
                ? new Date(data.trial.start_timestamp.replace(' ', 'T')).getTime()
                : Date.now();
            timerRow.hidden = false;
            statusText.textContent = 'Resumed: waiting for matching check-in result…';
            startBtn.hidden = true;
            startTick();
            if (data.matched && data.trial) {
                finishTrialUI(data.trial);
                return;
            }
            pollInterval = setInterval(pollForMatch, TRIAL_POLL_MS);
            fallbackTimeout = setTimeout(function () {
                if (activeTrialId) attachFallbackBtn.hidden = false;
            }, FALLBACK_DELAY_MS);
        })
        .catch(function () { /* no active trial to resume, or a transient error -- fine either way */ });
})();
