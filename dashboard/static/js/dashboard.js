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
    document.getElementById('active-tab-field').value = name;

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
    if (modal.classList.contains('open')) {
        return true;
    }
    var active = document.activeElement;
    return !!active && (
        active === searchInput ||
        active.id === 'session' ||
        active.closest('.quick-filters') !== null ||
        active.closest('.tabs') !== null
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

// Phase D3: snapshot preview modal. Event delegation on document
// (rather than a per-thumbnail onclick) so it keeps working after
// auto-refresh's full page reload re-renders the table -- the
// listener is attached once per page load, same as everything else
// in this script, and every fresh .snapshot-link in the new DOM is
// covered automatically without re-binding anything.
var modal = document.getElementById('snapshot-modal');

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

function closeSnapshotModal() {
    modal.classList.remove('open');
}

document.addEventListener('click', function (event) {
    var link = event.target.closest('.snapshot-link');
    if (link) {
        event.preventDefault(); // open the modal, not the plain <a href> navigation
        openSnapshotModal(link);
        return;
    }
    if (event.target.closest('.modal-close') || event.target === modal) {
        closeSnapshotModal();
    }
});

document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
        closeSnapshotModal();
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
var searchInput = document.getElementById('table-search');
var quickFilterButtons = document.querySelectorAll('.quick-filter-btn');

function getActiveQuickFilter() {
    var active = document.querySelector('.quick-filter-btn.active');
    return active ? active.dataset.filter : 'all';
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

function applyFilters() {
    var search = searchInput.value.trim().toLowerCase();
    // Quick filters only mean anything on Attempts (every Present row is
    // already a success) -- force "all" whenever that panel isn't the
    // active tab, so a chip left active there can never hide Present rows.
    // The chip's own .active class is left alone, so switching back to
    // Attempts naturally restores whichever filter was last chosen.
    var onAttempts = document.getElementById('tab-panel-attempts').classList.contains('active');
    var filter = onAttempts ? getActiveQuickFilter() : 'all';
    document.querySelectorAll('.attendance-row').forEach(function (row) {
        var matchesSearch = !search || row.dataset.name.toLowerCase().indexOf(search) !== -1;
        row.style.display = (matchesSearch && rowMatchesQuickFilter(row, filter)) ? '' : 'none';
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
quickFilterButtons.forEach(function (button) {
    button.classList.toggle('active', button.dataset.filter === savedQuickFilter);
    button.addEventListener('click', function () {
        quickFilterButtons.forEach(function (b) { b.classList.remove('active'); });
        button.classList.add('active');
        localStorage.setItem(QUICK_FILTER_STORAGE_KEY, button.dataset.filter);
        applyFilters();
    });
});

applyFilters(); // apply restored search/filter immediately on load (incl. after auto-refresh)

// Phase D6: Export CSV. Reads LIVE client state -- not just the URL, since
// tab/search/quick-filter can all change without a page reload -- and hands
// it to /export.csv as query params; the server rebuilds the same filtered
// row set (see matches_quick_filter() in app.py) and returns it as a
// download. Quick filter is only meaningful on Attempts (mirrors
// applyFilters()'s own onAttempts gate), so it's forced to "all" otherwise.
document.getElementById('export-csv-btn').addEventListener('click', function () {
    var params = new URLSearchParams(window.location.search);
    var tab = document.getElementById('active-tab-field').value;
    params.set('tab', tab);
    params.set('search', searchInput.value);
    params.set('quick_filter', tab === 'attempts' ? getActiveQuickFilter() : 'all');
    window.location.href = '/export.csv?' + params.toString();
});
