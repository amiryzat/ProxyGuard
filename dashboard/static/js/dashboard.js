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
}

// "Last updated" reflects this page load's own time -- a fresh value
// every auto-refresh cycle, no server timestamp/clock-sync needed.
document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();

// Auto-refresh: the session/reason/tab filters are all plain GET
// query params by this point, so a full reload of the current URL
// re-renders with the latest attendance rows/snapshots/summary while
// landing back on the exact same session, reason, and tab -- no
// partial-DOM-patching or extra endpoint needed. Interval comes from
// the server (REFRESH_SECONDS in app.py, threaded through as a
// data-refresh-seconds attribute on <body> since this is now a static
// file Jinja doesn't render) so the "auto-refresh every Xs" label above
// can never drift out of sync with the real timer.
// Phase D3 bug fix: a reload wipes any open modal out from under the
// lecturer mid-review, which read as "the modal closes itself". Skip this
// tick's reload while the modal is open rather than stopping/restarting the
// interval -- the next tick (still on schedule) reloads normally as soon as
// the modal is closed, so live updates resume with no extra bookkeeping.
var refreshSeconds = parseInt(document.body.dataset.refreshSeconds, 10);
setInterval(function () {
    if (!modal.classList.contains('open')) {
        window.location.reload();
    }
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
