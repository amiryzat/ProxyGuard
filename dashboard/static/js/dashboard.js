// Simple client-side tab switch -- no page reload, no separate routes.
// The session/reason dropdowns still reload the page (they're real GET
// filters, already in the URL); this only toggles which of the two
// already-rendered panels is visible, keeps the hidden "tab" form field
// in sync (so a subsequent dropdown change reopens the same tab), and
// -- for auto-refresh below -- also writes "tab" into the URL itself
// via replaceState (no navigation), since a client-only tab switch
// otherwise never touches the address bar and a reload would silently
// fall back to whatever tab the page last loaded with.
function showTab(name) {
    var panels = { present: 'tab-panel-present', attempts: 'tab-panel-attempts' };
    var buttons = { present: 'tab-btn-present', attempts: 'tab-btn-attempts' };
    Object.keys(panels).forEach(function (key) {
        document.getElementById(panels[key]).classList.toggle('active', key === name);
        document.getElementById(buttons[key]).classList.toggle('active', key === name);
    });
    // Attempt/Review filter chips live in their own tab-panel (shares a row
    // with search/export instead of sitting inside #tab-panel-attempts) --
    // toggled here too so it only shows while Attempts is active.
    document.getElementById('tab-panel-attempts-filters').classList.toggle('active', name === 'attempts');
    document.getElementById('active-tab-field').value = name;

    // Phase F3 refinement: the assistant button/window are now a sibling of
    // both tab panels (available from Present and Attempts alike), so a
    // plain tab switch no longer needs to force-close them -- an open
    // assistant window simply stays open across Present <-> Attempts.

    var params = new URLSearchParams(window.location.search);
    params.set('tab', name);
    history.replaceState(null, '', '?' + params.toString());

    // Re-run search/quick-filter now that the active tab changed -- Present
    // rows must never be hidden by a quick filter left active on Attempts
    // (applyFilters() forces quick-filter to "all" whenever Attempts isn't
    // the visible tab; see below). applyFilters is a hoisted function
    // declaration further down this file, so it's already callable by the
    // time a real click can trigger showTab().
    applyFilters();
}

document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();

// Phase D5 smart refresh: poll the lightweight /status endpoint instead of
// blindly reloading the whole page every REFRESH_SECONDS. Only reload once
// /status reports a DIFFERENT version than what this page was rendered with
// (attendance.csv's mtime+size -- see get_attendance_version() in app.py) --
// if nothing new was logged, do nothing, so an open Session dropdown or a
// focused search box is never yanked out from under the lecturer.
//
// A version change found while the lecturer is actively using a control
// (search focused, session <select> focused, a quick-filter/tab button just
// clicked -- it keeps focus after a click -- or the snapshot modal open)
// sets pendingReload instead of reloading immediately; the reload happens on
// the first later tick where none of those are true, so it's merely delayed,
// never lost, and the modal in particular can never be closed by a refresh.
var refreshSeconds = parseInt(document.body.dataset.refreshSeconds, 10);
var knownVersion = document.body.dataset.attendanceVersion;
var pendingReload = false;

function isUserBusy() {
    // Phase E4: two independent modal types (snapshot preview, review note)
    // can each be open -- either one blocks a refresh, checked generically
    // rather than by name so a third modal type would need no change here.
    if (document.querySelector('.modal-overlay.open')) {
        return true;
    }
    var active = document.activeElement;
    return !!active && (
        active === searchInput ||
        active.id === 'session' ||
        active.closest('.quick-filters') !== null ||
        active.closest('.tabs') !== null ||
        active.closest('.review-cell') !== null // an Accept/Suspicious/Add-note button still holds focus after being clicked
    );
}

setInterval(function () {
    fetch('/status')
        .then(function (response) { return response.json(); })
        .then(function (data) {
            if (data.version !== knownVersion) {
                pendingReload = true;
            }
            if (pendingReload && !isUserBusy()) {
                window.location.reload();
                return;
            }
            document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
        })
        .catch(function () { /* transient network hiccup -- just try again next tick */ });
}, refreshSeconds * 1000);

// Snapshot preview modal (Phase D3) + review note modal (Phase E4). Event
// delegation on document (rather than per-element onclick) so both keep
// working after auto-refresh's full page reload re-renders the table -- the
// listeners are attached once per page load, and every fresh .snapshot-link/
// .review-note-btn in the new DOM is covered automatically with no re-binding.
// Both modals share the same ".modal-overlay"/".modal-close" markup, so a
// single generic closeModal() handles either one -- see the delegated click
// handler below -- rather than two near-duplicate close functions that could
// drift or accidentally close the wrong modal.
var modal = document.getElementById('snapshot-modal');
var noteModal = document.getElementById('note-modal');
var activeNoteCell = null; // .review-cell currently open in the note modal

// Phase F2: assistant window shares the .modal-overlay class (so backdrop-
// click and Escape already close it via the same generic paths as the other
// two modals) but needs an extra animated step on close -- closeModal()
// below special-cases it rather than an instant classList.remove('open').
var assistantFab = document.getElementById('assistant-fab');
var assistantModal = document.getElementById('assistant-modal');
var assistantWindow = assistantModal.querySelector('.assistant-window');
var ASSISTANT_ANIM_MS = 180; // matches the .assistant-window transition duration in dashboard.css

function closeModal(overlay) {
    if (!overlay) return;
    if (overlay === assistantModal) {
        closeAssistantWindow();
        return;
    }
    overlay.classList.remove('open');
}

function openAssistantWindow() {
    assistantModal.classList.add('open');
    // One frame so the browser paints the initial (scaled-down/transparent)
    // state before .show flips it to the transition's end state -- adding
    // both classes in the same frame would just snap straight to "open"
    // with no visible animation.
    requestAnimationFrame(function () {
        assistantWindow.classList.add('show');
    });
    refreshAssistantPanel(); // pick up anything that changed since page load
}

function closeAssistantWindow() {
    assistantWindow.classList.remove('show');
    setTimeout(function () {
        assistantModal.classList.remove('open');
    }, ASSISTANT_ANIM_MS);
}

assistantFab.addEventListener('click', openAssistantWindow);

function openSnapshotModal(link) {
    document.getElementById('modal-img').src = link.dataset.src;
    document.getElementById('modal-name').textContent = link.dataset.name;
    document.getElementById('modal-date').textContent = link.dataset.date;
    document.getElementById('modal-time').textContent = link.dataset.time;
    document.getElementById('modal-session').textContent = link.dataset.session;
    document.getElementById('modal-result').textContent = link.dataset.result;
    document.getElementById('modal-reason').textContent = link.dataset.reason;
    modal.classList.add('open');
}

function openNoteModal(cell) {
    activeNoteCell = cell;
    var status = cell.closest('tr').dataset.reviewStatus || 'unreviewed';
    document.getElementById('note-modal-name').textContent = cell.dataset.name;
    document.getElementById('note-modal-date').textContent = cell.dataset.date;
    document.getElementById('note-modal-time').textContent = cell.dataset.time;
    document.getElementById('note-modal-session').textContent = cell.dataset.session;
    document.getElementById('note-modal-result').textContent = cell.dataset.result;
    document.getElementById('note-modal-reason').textContent = cell.dataset.reason;
    var statusBadge = document.getElementById('note-modal-status');
    statusBadge.textContent = status;
    statusBadge.className = 'review-badge review-badge-' + status;
    document.getElementById('note-modal-textarea').value = cell.querySelector('.review-note-btn').dataset.note || '';
    noteModal.classList.add('open');
}

// Updates a row's Add/Edit note button label + short preview text in place
// after a save -- avoids a page reload just to reflect the new note.
function updateNoteButton(cell, note) {
    var btn = cell.querySelector('.review-note-btn');
    btn.dataset.note = note;
    btn.textContent = note ? 'Edit note' : 'Add note';
    var preview = cell.querySelector('.review-note-preview');
    if (note) {
        if (!preview) {
            preview = document.createElement('p');
            preview.className = 'review-note-preview';
            cell.appendChild(preview);
        }
        preview.textContent = note.length > 60 ? note.slice(0, 60) + '…' : note;
    } else if (preview) {
        preview.remove();
    }
}

// Phase E2/E3/E4: review status + note, both writing through the same
// Phase E1 POST /review endpoint -- one shared submit function. Accept/
// Suspicious pass the row's already-saved note (preserving it, per
// requirement 8); the note modal's Save passes the current status
// (preserving it) plus the newly-edited note. On success the status badge
// (.status-cell -- Phase E3), the row's own data-review-status, and the note
// button/preview all update in place, then the review summary counts and any
// active review filter re-apply -- no page reload.
function submitReview(cell, status, note) {
    var row = cell.closest('tr');
    var badge = row.querySelector('.status-cell .review-badge');
    return fetch('/review', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            session_id: cell.dataset.session,
            date: cell.dataset.date,
            time: cell.dataset.time,
            name: cell.dataset.name,
            result: cell.dataset.result,
            reason: cell.dataset.reason,
            review_status: status,
            review_note: note,
        }),
    }).then(function (response) {
        if (!response.ok) return;
        badge.textContent = status;
        badge.className = 'review-badge review-badge-' + status;
        row.dataset.reviewStatus = status;
        updateNoteButton(cell, note);
        updateReviewSummaryCounts();
        refreshAssistantPanel(); // suspicious/unreviewed counts feed assistant rules -- keep it in sync
        applyFilters(); // in case an active review filter no longer matches this row's new status
    });
}

function updateReviewSummaryCounts() {
    var counts = { unreviewed: 0, accepted: 0, suspicious: 0 };
    document.querySelectorAll('#tab-panel-attempts .attendance-row[data-review-status]').forEach(function (row) {
        var status = row.dataset.reviewStatus;
        if (status && counts.hasOwnProperty(status)) counts[status]++;
    });
    Object.keys(counts).forEach(function (status) {
        var el = document.getElementById('review-summary-' + status);
        if (el) el.textContent = counts[status];
    });
}

// Phase F1/F2: a review action only writes logs/reviews.csv, never
// attendance.csv, so it never changes get_attendance_version() and never
// triggers smart refresh on its own -- re-fetch just the assistant cards
// (server-rendered, same rules as the full page) for the currently selected
// session instead of duplicating the rule logic here.
function refreshAssistantPanel() {
    var sessionSelect = document.getElementById('session');
    var session = sessionSelect ? sessionSelect.value : '';
    var url = '/assistant_panel' + (session ? '?session=' + encodeURIComponent(session) : '');
    fetch(url)
        .then(function (response) { return response.text(); })
        .then(function (html) {
            var target = document.getElementById('assistant-cards-target');
            target.innerHTML = html;
            updateAssistantBadge(target);
        })
        .catch(function () { /* transient network hiccup -- leave the panel as-is */ });
}

// Small red count on the floating button itself -- counts .priority-high
// CARDS specifically (scoped to .assistant-card, not the whole panel) rather
// than a second server-side count, so it can never drift from what the
// window actually shows. Phase F4 added a compact summary block with its own
// "Attention" priority badge above the cards -- an unscoped query would
// double-count that badge whenever attention is High.
function updateAssistantBadge(cardsTarget) {
    var badge = document.getElementById('assistant-fab-badge');
    var highCount = cardsTarget.querySelectorAll('.assistant-card .priority-high').length;
    badge.textContent = highCount;
    badge.style.display = highCount > 0 ? 'inline-flex' : 'none';
}
updateAssistantBadge(document.getElementById('assistant-cards-target')); // reflect the server-rendered initial cards

// Phase F3: assistant card action buttons ("View affected attempts", "Open
// next unreviewed attempt"). Both reuse the existing filter chips rather
// than a second filtering system -- see _card_actions()/
// build_assistant_recommendations() in app.py
// for how each button's data-* attributes are built.
function activateResultFilter(value) {
    resultFilterButtons.forEach(function (b) { b.classList.toggle('active', b.dataset.filter === value); });
    localStorage.setItem(QUICK_FILTER_STORAGE_KEY, value);
}

function activateReviewFilter(value) {
    reviewFilterButtons.forEach(function (b) { b.classList.toggle('active', b.dataset.reviewFilter === value); });
    localStorage.setItem(REVIEW_FILTER_STORAGE_KEY, value);
}

// Closes/minimizes the assistant window and makes sure Attempts is the
// active tab. Phase F3 refinement: the assistant is now reachable from
// Present too, and showTab() no longer auto-closes it as a side effect
// (see showTab() above), so this always closes it explicitly -- whether or
// not a tab switch is also needed -- rather than relying on that removed
// behavior.
function switchToAttemptsAndCloseAssistant() {
    if (!document.getElementById('tab-panel-attempts').classList.contains('active')) {
        showTab('attempts');
    }
    closeAssistantWindow();
}

function scrollAttemptsTableIntoView() {
    var table = document.querySelector('#tab-panel-attempts .table-card');
    if (table) table.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function findFirstVisibleUnreviewedRow() {
    var rows = document.querySelectorAll('#tab-panel-attempts .attendance-row');
    for (var i = 0; i < rows.length; i++) {
        if (rows[i].style.display !== 'none' && rows[i].dataset.reviewStatus === 'unreviewed') {
            return rows[i];
        }
    }
    return null;
}

function flashRow(row) {
    row.classList.add('assistant-highlight');
    setTimeout(function () { row.classList.remove('assistant-highlight'); }, 1500);
}

function handleAssistantAction(button) {
    var action = button.dataset.action;

    if (action === 'view-filter') {
        switchToAttemptsAndCloseAssistant();
        if (button.dataset.filterType === 'review') {
            activateReviewFilter(button.dataset.filterValue);
            activateResultFilter('all');
        } else {
            activateResultFilter(button.dataset.filterValue);
            activateReviewFilter('all');
        }
        applyFilters();
        scrollAttemptsTableIntoView();
        return;
    }

    if (action === 'open-next-unreviewed') {
        switchToAttemptsAndCloseAssistant();
        activateReviewFilter('unreviewed');
        activateResultFilter('all');
        applyFilters();
        var row = findFirstVisibleUnreviewedRow();
        if (row) {
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });
            flashRow(row);
        }
    }
}

document.addEventListener('click', function (event) {
    var assistantActionBtn = event.target.closest('.assistant-action-btn');
    if (assistantActionBtn) {
        handleAssistantAction(assistantActionBtn);
        return;
    }

    var link = event.target.closest('.snapshot-link');
    if (link) {
        event.preventDefault(); // open the modal, not the plain <a href> navigation
        openSnapshotModal(link);
        return;
    }

    // Generic modal close: works for the snapshot modal AND the note modal
    // (Phase E4) without knowing which one is open -- a .modal-close button
    // closes its own ancestor .modal-overlay, and clicking the dimmed
    // backdrop closes that overlay. Neither modal's handler can ever close
    // the other one by mistake.
    var closeBtn = event.target.closest('.modal-close');
    if (closeBtn) {
        closeModal(closeBtn.closest('.modal-overlay'));
        return;
    }
    if (event.target.classList.contains('modal-overlay')) {
        closeModal(event.target);
        return;
    }

    var reviewBtn = event.target.closest('.review-btn');
    if (reviewBtn) {
        var cell = reviewBtn.closest('.review-cell');
        var currentNote = cell.querySelector('.review-note-btn').dataset.note || '';
        submitReview(cell, reviewBtn.dataset.status, currentNote); // preserve any existing note
        return;
    }

    var noteBtn = event.target.closest('.review-note-btn');
    if (noteBtn) {
        openNoteModal(noteBtn.closest('.review-cell'));
        return;
    }

    if (event.target.id === 'note-modal-save') {
        var status = activeNoteCell.closest('tr').dataset.reviewStatus || 'unreviewed'; // preserve current status
        var note = document.getElementById('note-modal-textarea').value;
        submitReview(activeNoteCell, status, note).then(function () {
            closeModal(noteModal);
        });
    }
});

document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.open').forEach(closeModal);
    }
});

// Phase D4: search + quick filters. Pure client-side, applied to the
// .attendance-row <tr> elements already rendered in BOTH tables (Present and
// Attempts share the same search input / quick-filter buttons, so switching
// tabs keeps the same filter with no extra state-transfer code). Persisted
// in localStorage (not the URL) so a typed search term survives an
// auto-refresh reload without turning every keystroke into a page navigation.
var SEARCH_STORAGE_KEY = 'dashboardSearch';
var QUICK_FILTER_STORAGE_KEY = 'dashboardQuickFilter';
var REVIEW_FILTER_STORAGE_KEY = 'dashboardReviewFilter';
var searchInput = document.getElementById('table-search');
// "result-filter-btn" / "review-filter-btn" are two independent chip groups
// that happen to share the same ".quick-filter-btn" pill styling (Phase E3)
// -- scoping each query to its own class keeps them from clearing each
// other's "active" state.
var resultFilterButtons = document.querySelectorAll('.result-filter-btn');
var reviewFilterButtons = document.querySelectorAll('.review-filter-btn');

function getActiveQuickFilter() {
    var active = document.querySelector('.result-filter-btn.active');
    return active ? active.dataset.filter : 'all';
}

function getActiveReviewFilter() {
    var active = document.querySelector('.review-filter-btn.active');
    return active ? active.dataset.reviewFilter : 'all';
}

function rowMatchesQuickFilter(row, filter) {
    switch (filter) {
        case 'success': return row.dataset.result === 'success';
        case 'failed': return row.dataset.result === 'failed';
        case 'flagged': return row.dataset.flagged === 'true';
        case 'unknown': return row.dataset.unknown === 'true';
        case 'duplicate': return row.dataset.duplicate === 'true';
        case 'liveness': return row.dataset.liveness === 'true';
        default: return true; // "all"
    }
}

function rowMatchesReviewFilter(row, filter) {
    if (filter === 'all') return true;
    return row.dataset.reviewStatus === filter;
}

function applyFilters() {
    var search = searchInput.value.trim().toLowerCase();
    // Quick/review filters only mean anything on Attempts (every Present row
    // is already a success with no review) -- force both to "all" whenever
    // that panel isn't the active tab, so a chip left active there can never
    // hide Present rows. Each chip's own .active class is left alone, so
    // switching back to Attempts naturally restores whichever filters were
    // last chosen.
    var onAttempts = document.getElementById('tab-panel-attempts').classList.contains('active');
    var filter = onAttempts ? getActiveQuickFilter() : 'all';
    var reviewFilter = onAttempts ? getActiveReviewFilter() : 'all';
    document.querySelectorAll('.attendance-row').forEach(function (row) {
        var matchesSearch = !search || row.dataset.name.toLowerCase().indexOf(search) !== -1;
        row.style.display = (matchesSearch && rowMatchesQuickFilter(row, filter) && rowMatchesReviewFilter(row, reviewFilter)) ? '' : 'none';
    });
}

var searchClearBtn = document.getElementById('search-clear-btn');

function updateSearchClearVisibility() {
    searchClearBtn.classList.toggle('visible', searchInput.value.length > 0);
}

searchInput.value = localStorage.getItem(SEARCH_STORAGE_KEY) || '';
updateSearchClearVisibility();
searchInput.addEventListener('input', function () {
    localStorage.setItem(SEARCH_STORAGE_KEY, searchInput.value);
    updateSearchClearVisibility();
    applyFilters();
});

searchClearBtn.addEventListener('click', function () {
    searchInput.value = '';
    localStorage.setItem(SEARCH_STORAGE_KEY, '');
    updateSearchClearVisibility();
    applyFilters();
    searchInput.focus();
});

var savedQuickFilter = localStorage.getItem(QUICK_FILTER_STORAGE_KEY) || 'all';
resultFilterButtons.forEach(function (button) {
    button.classList.toggle('active', button.dataset.filter === savedQuickFilter);
    button.addEventListener('click', function () {
        resultFilterButtons.forEach(function (b) { b.classList.remove('active'); });
        button.classList.add('active');
        localStorage.setItem(QUICK_FILTER_STORAGE_KEY, button.dataset.filter);
        applyFilters();
    });
});

// Phase E3: review-status filter chips -- identical wiring to the result
// filter chips above, just scoped to .review-filter-btn / its own storage
// key, so the two groups' selections persist and restore independently.
var savedReviewFilter = localStorage.getItem(REVIEW_FILTER_STORAGE_KEY) || 'all';
reviewFilterButtons.forEach(function (button) {
    button.classList.toggle('active', button.dataset.reviewFilter === savedReviewFilter);
    button.addEventListener('click', function () {
        reviewFilterButtons.forEach(function (b) { b.classList.remove('active'); });
        button.classList.add('active');
        localStorage.setItem(REVIEW_FILTER_STORAGE_KEY, button.dataset.reviewFilter);
        applyFilters();
    });
});

applyFilters(); // apply restored search/filters immediately on load (incl. after auto-refresh)

// Phase D6/E3: Export CSV. Reads LIVE client state -- not just the URL, since
// tab/search/quick-filter/review-filter can all change without a page reload
// -- and hands it to /export.csv as query params; the server rebuilds the
// same filtered row set (see matches_quick_filter()/matches_review_filter()
// in app.py) and returns it as a download. Both filters are only meaningful
// on Attempts (mirrors applyFilters()'s own onAttempts gate), so both are
// forced to "all" otherwise.
document.getElementById('export-csv-btn').addEventListener('click', function () {
    var params = new URLSearchParams(window.location.search);
    var tab = document.getElementById('active-tab-field').value;
    params.set('tab', tab);
    params.set('search', searchInput.value);
    params.set('quick_filter', tab === 'attempts' ? getActiveQuickFilter() : 'all');
    params.set('review_filter', tab === 'attempts' ? getActiveReviewFilter() : 'all');
    window.location.href = '/export.csv?' + params.toString();
});
