// dashboard/static/js/evaluation.js -- Report Support Phase R1.
// Self-contained: does NOT load dashboard.js (that file assumes index.html's
// tabs/search/assistant elements exist unconditionally), so this page has its
// own small script covering the trial timer/polling, manual attach/correct,
// and CSV export, all against the /evaluation/* routes in dashboard/app.py.

const sessionSelect = document.getElementById('session');
const scopeAllCheckbox = document.getElementById('scopeAll');
const scopeField = document.getElementById('scopeField');
const scopeForm = document.getElementById('scopeForm');

if (scopeAllCheckbox) {
    scopeAllCheckbox.addEventListener('change', function () {
        scopeField.value = scopeAllCheckbox.checked ? 'all' : 'session';
        scopeForm.submit();
    });
}

function currentScope() {
    return scopeField ? scopeField.value : 'session';
}

const startBtn = document.getElementById('startTrialBtn');
const attachBtn = document.getElementById('attachLatestBtn');
const timerRow = document.getElementById('timerRow');
const timerDisplay = document.getElementById('timerDisplay');
const statusText = document.getElementById('trialStatusText');
const panelTarget = document.getElementById('evaluation-panel-target');

let activeTrialId = null;
let trialStartMs = null;
let tickInterval = null;
let pollInterval = null;
const POLL_MS = 3000;

function refreshPanel() {
    const params = new URLSearchParams();
    if (sessionSelect && sessionSelect.value) params.set('session', sessionSelect.value);
    params.set('scope', currentScope());
    fetch('/evaluation_panel?' + params.toString())
        .then(function (r) { return r.text(); })
        .then(function (html) { panelTarget.innerHTML = html; })
        .catch(function () { /* transient network hiccup -- leave the panel as-is */ });
}

function startTick() {
    tickInterval = setInterval(function () {
        const elapsed = (Date.now() - trialStartMs) / 1000;
        timerDisplay.textContent = elapsed.toFixed(1) + 's';
    }, 100);
}

function stopTrialUI(finalStatusText) {
    clearInterval(tickInterval);
    clearInterval(pollInterval);
    tickInterval = null;
    pollInterval = null;
    activeTrialId = null;
    startBtn.disabled = false;
    attachBtn.disabled = true;
    if (finalStatusText) statusText.textContent = finalStatusText;
}

function describeTrialResult(trial) {
    const verdict = trial.pass_fail === 'pass' ? 'PASS'
        : trial.pass_fail === 'fail' ? 'FAIL'
        : 'needs manual review';
    return 'Attached: ' + (trial.actual_name || 'Unknown') + ' / ' + (trial.actual_result || '?')
        + ' / ' + (trial.actual_reason || '?') + ' -- ' + verdict;
}

function pollForMatch() {
    fetch('/evaluation/check')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.matched && data.trial) {
                stopTrialUI(describeTrialResult(data.trial));
                refreshPanel();
            }
            // data.active === false or matched === false -- just keep polling/waiting
        })
        .catch(function (err) {
            console.warn('evaluation poll failed, will retry:', err);
        });
}

startBtn.addEventListener('click', function () {
    const session_id = sessionSelect ? sessionSelect.value : '';
    const test_scenario = document.getElementById('testScenario').value;
    const expected_outcome = document.getElementById('expectedOutcome').value;
    if (!session_id) {
        alert('Select a session first.');
        return;
    }

    startBtn.disabled = true;
    fetch('/evaluation/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: session_id, test_scenario: test_scenario, expected_outcome: expected_outcome }),
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.error) {
                alert(data.error);
                startBtn.disabled = false;
                return;
            }
            activeTrialId = data.trial.trial_id;
            trialStartMs = Date.now();
            timerRow.hidden = false;
            statusText.textContent = 'Waiting for matching check-in result…';
            attachBtn.disabled = false;
            startTick();
            pollInterval = setInterval(pollForMatch, POLL_MS);
            refreshPanel(); // show the new "pending" row immediately
        })
        .catch(function () {
            alert('Could not start the trial (network error).');
            startBtn.disabled = false;
        });
});

attachBtn.addEventListener('click', function () {
    if (!activeTrialId) return;
    attachBtn.disabled = true;
    fetch('/evaluation/attach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trial_id: activeTrialId }),
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.error) {
                alert(data.error);
                attachBtn.disabled = false;
                return;
            }
            stopTrialUI(describeTrialResult(data.trial));
            refreshPanel();
        })
        .catch(function () {
            alert('Could not attach the latest attempt (network error).');
            attachBtn.disabled = false;
        });
});

// Manual pass/fail correction + notes (requirement 11), delegated since the
// matrix is replaced wholesale by refreshPanel() after every change.
document.addEventListener('click', function (event) {
    const correctBtn = event.target.closest('.eval-correct-btn');
    if (!correctBtn) return;
    const cell = correctBtn.closest('.eval-notes-cell');
    const trialId = cell.dataset.trialId;
    const note = cell.querySelector('.eval-notes-input').value;
    submitCorrection(trialId, correctBtn.dataset.passFail, note);
});

// Saving just the note (Enter key or blur) preserves whatever pass/fail
// badge the row currently shows, rather than requiring a Mark Pass/Fail
// click just to persist a typed note.
document.addEventListener('change', function (event) {
    if (!event.target.classList.contains('eval-notes-input')) return;
    const cell = event.target.closest('.eval-notes-cell');
    const trialId = cell.dataset.trialId;
    const row = cell.closest('tr');
    const badge = row.querySelector('.review-badge');
    const currentVerdict = badge ? badge.textContent.trim().replace(' ', '_') : 'needs_review';
    if (currentVerdict !== 'pass' && currentVerdict !== 'fail') return; // only pass/fail are valid /correct values
    submitCorrection(trialId, currentVerdict, event.target.value);
});

function submitCorrection(trialId, passFail, notes) {
    fetch('/evaluation/correct', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ trial_id: trialId, pass_fail: passFail, notes: notes }),
    })
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (data.error) {
                alert(data.error);
                return;
            }
            refreshPanel();
        })
        .catch(function () { /* transient network hiccup -- the note stays typed in the input */ });
}

document.getElementById('exportTrialsBtn').addEventListener('click', function () {
    const params = new URLSearchParams();
    if (sessionSelect && sessionSelect.value) params.set('session', sessionSelect.value);
    params.set('scope', currentScope());
    window.location.href = '/evaluation/export.csv?' + params.toString();
});

document.getElementById('exportMetricsBtn').addEventListener('click', function () {
    const params = new URLSearchParams();
    if (sessionSelect && sessionSelect.value) params.set('session', sessionSelect.value);
    params.set('scope', currentScope());
    window.location.href = '/evaluation/export_metrics.csv?' + params.toString();
});

// On load: if a trial was left pending (e.g. the page was reloaded mid-trial),
// resume its timer/polling instead of silently losing track of it.
(function resumeIfPending() {
    fetch('/evaluation/check')
        .then(function (r) { return r.json(); })
        .then(function (data) {
            if (!data.active) return;
            activeTrialId = data.trial_id;
            // We don't know the original start time from this endpoint alone,
            // so the timer restarts from 0 on resume -- duration is still
            // computed server-side from the trial's real start_time once
            // attached, this only affects the live-ticking display.
            trialStartMs = Date.now();
            timerRow.hidden = false;
            statusText.textContent = 'Resumed: waiting for matching check-in result…';
            startBtn.disabled = true;
            attachBtn.disabled = false;
            startTick();
            if (data.matched && data.trial) {
                stopTrialUI(describeTrialResult(data.trial));
                refreshPanel();
                return;
            }
            pollInterval = setInterval(pollForMatch, POLL_MS);
        })
        .catch(function () { /* no active trial to resume, or a transient error -- fine either way */ });
})();
