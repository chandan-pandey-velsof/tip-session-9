from django.http import HttpResponse


def index(request):
    """Patent Lookup page — search any patent by number and view its details."""
    return HttpResponse(_PAGE_HTML, content_type="text/html")


_PAGE_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Patent Lookup — TriangleIP</title>
<link rel='stylesheet' href='/static/tip_design.css'>
<style>
  .tip-search-box {
    display: flex; gap: 10px; align-items: center; flex-wrap: wrap;
  }
  .tip-search-box input {
    flex: 1; min-width: 260px; padding: 10px 14px; border: 1px solid var(--tip-border, #d0d5dd);
    border-radius: 8px; font-size: 15px; font-family: inherit; outline: none;
    transition: border-color .2s;
  }
  .tip-search-box input:focus { border-color: var(--tip-primary); }
  .suggestions-dropdown {
    position: absolute; top: 100%; left: 0; right: 0; z-index: 50;
    background: #fff; border: 1px solid var(--tip-border, #d0d5dd);
    border-radius: 8px; max-height: 260px; overflow-y: auto;
    box-shadow: 0 8px 24px rgba(0,0,0,.12); display: none;
  }
  .suggestions-dropdown.open { display: block; }
  .suggestion-item {
    padding: 10px 14px; cursor: pointer; font-size: 14px;
    border-bottom: 1px solid #f0f0f0;
  }
  .suggestion-item:last-child { border-bottom: none; }
  .suggestion-item:hover { background: #f5f7ff; }
  .suggestion-item .sug-number { font-weight: 600; color: var(--tip-primary); }
  .suggestion-item .sug-title { color: var(--tip-text-secondary, #667085); margin-left: 8px; font-size: 13px; }
  .detail-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
  .detail-label { font-size: 12px; text-transform: uppercase; letter-spacing: .5px; color: var(--tip-text-secondary, #667085); margin-bottom: 4px; }
  .detail-value { font-size: 18px; font-weight: 600; color: var(--tip-text, #101828); word-break: break-word; }
  .spinner { display: inline-block; width: 18px; height: 18px; border: 2px solid #ccc; border-top-color: var(--tip-primary); border-radius: 50%; animation: spin .6s linear infinite; }
  @keyframes spin { to { transform: rotate(360deg); } }
  .fade-in { animation: fadeIn .3s ease; }
  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
  .search-wrapper { position: relative; flex: 1; min-width: 260px; }
  .quota-bar { height: 6px; border-radius: 3px; background: #e4e7ec; overflow: hidden; }
  .quota-bar-fill { height: 100%; border-radius: 3px; background: var(--tip-primary); transition: width .3s; }
</style>
</head>
<body>
<div class="tip-page">

  <nav class="tip-navbar">
    <a class="tip-navbar-brand" href="/">TriangleIP</a>
  </nav>

  <h1 class="tip-page-title">Patent Lookup</h1>
  <p style="color:var(--tip-text-secondary); margin-bottom:24px;">
    Enter a US application, publication, or patent number to retrieve its details from the USPTO.
  </p>

  <!-- Search Card -->
  <div class="tip-card" style="margin-bottom:24px;">
    <div class="tip-search-box">
      <div class="search-wrapper">
        <input type="text" id="searchInput" placeholder="e.g. 16/687,273  |  US8623891  |  EP1514569A1" autocomplete="off">
        <div class="suggestions-dropdown" id="suggestionsDropdown"></div>
      </div>
      <button class="tip-btn tip-btn-primary" id="searchBtn" onclick="doSearch()">Look Up</button>
    </div>
  </div>

  <!-- Error Card (hidden) -->
  <div class="tip-card" id="errorCard" style="display:none; border-left:4px solid #f04438; margin-bottom:24px;">
    <div id="errorContent"></div>
  </div>

  <!-- Results Area -->
  <div id="resultsArea"></div>

  <!-- Diagnostics -->
  <div class="tip-card" style="margin-top:32px;">
    <details>
      <summary style="cursor:pointer; font-weight:600; color:var(--tip-text-secondary);">Diagnostics</summary>
      <div style="margin-top:12px;">
        <div class="tip-table-wrap">
          <table class="tip-table" id="diagTable">
            <thead>
              <tr><th>Item</th><th>Details</th></tr>
            </thead>
            <tbody id="diagBody">
              <tr><td>Request</td><td id="diagRequest">—</td></tr>
              <tr><td>API Calls</td><td id="diagApiCalls">—</td></tr>
              <tr><td>Input Parameters</td><td id="diagInput">—</td></tr>
              <tr><td>Output Parameters</td><td id="diagOutput">—</td></tr>
              <tr><td>Field Mapping</td><td id="diagMapping">—</td></tr>
            </tbody>
          </table>
        </div>
      </div>
    </details>
  </div>

</div>

<script>
const USER_REQUEST = "Let me look up any patent by its number and show me the details \u2014 title, status, filing date, inventor, and examiner.";

/* ── State ── */
let debounceTimer = null;
let lastSearchQuery = '';
let lastSearchType = '';

/* ── Suggestion autocomplete ── */
const searchInput = document.getElementById('searchInput');
const dropdown = document.getElementById('suggestionsDropdown');

searchInput.addEventListener('input', function() {
  const q = this.value.trim();
  if (q.length < 5) { dropdown.classList.remove('open'); dropdown.innerHTML = ''; return; }
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => fetchSuggestions(q), 300);
});

searchInput.addEventListener('keydown', function(e) {
  if (e.key === 'Enter') { e.preventDefault(); dropdown.classList.remove('open'); doSearch(); }
});

function fetchSuggestions(q) {
  fetch('/tip-api/v1/patent-lookup/suggest?q=' + encodeURIComponent(q) + '&limit=8')
    .then(r => r.json())
    .then(resp => {
      if (!resp.status || !resp.data || !resp.data.results || resp.data.results.length === 0) {
        dropdown.classList.remove('open'); dropdown.innerHTML = ''; return;
      }
      dropdown.innerHTML = resp.data.results.map(item =>
        '<div class="suggestion-item" data-id="' + escHtml(item.id) + '" data-display="' + escHtml(item.display) + '">'
        + '<span class="sug-number">' + escHtml(item.display) + '</span>'
        + '<span class="sug-title">' + escHtml(item.title || '') + '</span>'
        + '</div>'
      ).join('');
      dropdown.classList.add('open');
      dropdown.querySelectorAll('.suggestion-item').forEach(el => {
        el.addEventListener('click', () => {
          searchInput.value = el.dataset.display;
          dropdown.classList.remove('open');
          doSearch();
        });
      });
    })
    .catch(() => { dropdown.classList.remove('open'); });
}

document.addEventListener('click', e => {
  if (!e.target.closest('.search-wrapper')) dropdown.classList.remove('open');
});

/* ── Search ── */
function doSearch() {
  const query = searchInput.value.trim();
  if (!query) return;
  lastSearchQuery = query;
  lastSearchType = '';
  hideError();
  document.getElementById('resultsArea').innerHTML =
    '<div class="tip-card" style="text-align:center;padding:32px;"><span class="spinner"></span>&nbsp; Searching&hellip;</div>';
  updateDiagApiCalls('POST /tip-api/v1/patent-lookup/search');
  updateDiagInput('query: ' + query);
  updateDiagOutput('—');
  updateDiagMapping('—');

  fetch('/tip-api/v1/patent-lookup/search', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query: query })
  })
  .then(r => {
    if (!r.ok) return r.text().then(t => { throw new Error('HTTP ' + r.status + ': ' + t); });
    return r.json();
  })
  .then(resp => {
    if (!resp.status) throw new Error(resp.message || 'API returned status=false');
    renderResults(resp);
  })
  .catch(err => {
    showError('Lookup failed: ' + err.message);
    document.getElementById('resultsArea').innerHTML = '';
  });
}

/* ── Render ── */
function renderResults(resp) {
  const d = resp.data;
  const r = d.result;
  const s = r.summary;
  const q = d.quota || {};

  lastSearchType = d.search_type || r.application_number ? 'application_number' : '';

  /* Quota info */
  let quotaHtml = '';
  if (q.limit) {
    const pct = Math.round((q.used / q.limit) * 100);
    quotaHtml = '<div class="tip-card" style="margin-bottom:16px;">'
      + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">'
      + '<span style="font-size:13px;color:var(--tip-text-secondary);">Lookup Quota</span>'
      + '<span style="font-size:13px;font-weight:600;">' + q.used + ' / ' + q.limit + ' used</span></div>'
      + '<div class="quota-bar"><div class="quota-bar-fill" style="width:' + pct + '%;"></div></div></div>';
  }

  /* Status tag colour */
  const statusText = s.status || 'Unknown';
  let statusClass = 'tip-tag-default';
  const sl = statusText.toLowerCase();
  if (sl.includes('patent')) statusClass = 'tip-tag-success';
  else if (sl.includes('pend') || sl.includes('active')) statusClass = 'tip-tag-primary';
  else if (sl.includes('aban')) statusClass = 'tip-tag-error';
  else if (sl.includes('expir')) statusClass = 'tip-tag-warning';

  const html = '<div class="fade-in">'
    + quotaHtml

    /* Header card */
    + '<div class="tip-card" style="margin-bottom:16px;">'
      + '<h2 style="margin:0 0 6px 0;font-size:20px;">' + escHtml(s.title || 'No title') + '</h2>'
      + '<div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:8px;">'
        + '<span class="tip-tag ' + statusClass + '">' + escHtml(statusText) + '</span>'
        + '<span class="tip-tag tip-tag-default">' + escHtml(s.application_type || '') + '</span>'
        + '<span class="tip-tag tip-tag-default">' + escHtml(s.entity_status || '') + '</span>'
      + '</div>'
    + '</div>'

    /* Detail grid */
    + '<div class="detail-grid" style="margin-bottom:16px;">'

      + detailCard('Application Number', fmtAppNum(s.application_number))
      + detailCard('Patent Number', s.patent_number || '—')
      + detailCard('Filing Date', s.filing_date || '—')
      + detailCard('Grant Date', s.grant_date || '—')
      + detailCard('Status Date', s.status_date || '—')
      + detailCard('Examiner', s.examiner_name || '—')
      + detailCard('First Inventor', s.first_inventor_name || '—')
      + detailCard('First Applicant', s.first_applicant_name || '—')
      + detailCard('Group Art Unit', s.group_art_unit || '—')
      + detailCard('Class / Subclass', s.class_subclass || '—')
      + detailCard('Earliest Publication', s.earliest_publication_number ? escHtml(s.earliest_publication_number) + ' (' + escHtml(s.earliest_publication_date || '') + ')' : '—')
      + detailCard('Docket Number', s.docket_number || '—')
      + detailCard('Confirmation #', s.confirmation_number != null ? s.confirmation_number : '—')

    + '</div>'

    /* Summary table */
    + '<div class="tip-card">'
      + '<h3 style="margin:0 0 12px 0;font-size:16px;">Full Summary</h3>'
      + '<div class="tip-table-wrap"><table class="tip-table"><thead><tr><th>Field</th><th>Value</th></tr></thead><tbody>'
      + summaryRow('Application Number', fmtAppNum(s.application_number))
      + summaryRow('Patent Number', s.patent_number)
      + summaryRow('Title', s.title)
      + summaryRow('Status', s.status)
      + summaryRow('Status Date', s.status_date)
      + summaryRow('Filing Date', s.filing_date)
      + summaryRow('Grant Date', s.grant_date)
      + summaryRow('Application Type', s.application_type)
      + summaryRow('Examiner', s.examiner_name)
      + summaryRow('Group Art Unit', s.group_art_unit)
      + summaryRow('Class / Subclass', s.class_subclass)
      + summaryRow('Entity Status', s.entity_status)
      + summaryRow('First Inventor', s.first_inventor_name)
      + summaryRow('First Applicant', s.first_applicant_name)
      + summaryRow('Earliest Publication', s.earliest_publication_number)
      + summaryRow('Earliest Pub. Date', s.earliest_publication_date)
      + summaryRow('Docket Number', s.docket_number)
      + summaryRow('Confirmation Number', s.confirmation_number)
      + '</tbody></table></div>'
    + '</div>'

    + '</div>';

  document.getElementById('resultsArea').innerHTML = html;

  /* Update diagnostics */
  const outputFields = [
    'data.search_type=' + (d.search_type || 'n/a'),
    'data.result.application_number=' + (r.application_number || 'n/a'),
    'data.result.summary.title=' + truncate(s.title, 60),
    'data.result.summary.status=' + (s.status || 'n/a'),
    'data.result.summary.filing_date=' + (s.filing_date || 'n/a'),
    'data.result.summary.examiner_name=' + (s.examiner_name || 'n/a'),
    'data.result.summary.first_inventor_name=' + (s.first_inventor_name || 'n/a'),
    'data.result.summary.patent_number=' + (s.patent_number || 'n/a'),
    'data.result.summary.grant_date=' + (s.grant_date || 'n/a'),
    'data.result.summary.group_art_unit=' + (s.group_art_unit || 'n/a'),
    'data.result.summary.class_subclass=' + (s.class_subclass || 'n/a'),
    'data.result.summary.entity_status=' + (s.entity_status || 'n/a'),
    'data.result.summary.application_type=' + (s.application_type || 'n/a'),
    'data.result.summary.first_applicant_name=' + (s.first_applicant_name || 'n/a'),
    'data.result.summary.earliest_publication_number=' + (s.earliest_publication_number || 'n/a'),
    'data.result.summary.docket_number=' + (s.docket_number || 'n/a'),
    'data.result.summary.confirmation_number=' + (s.confirmation_number != null ? s.confirmation_number : 'n/a'),
    'data.quota.used=' + (q.used != null ? q.used : 'n/a'),
    'data.quota.remaining=' + (q.remaining != null ? q.remaining : 'n/a'),
  ];
  updateDiagOutput(outputFields.join('<br>'));

  const mappingRows = [
    'data.result.summary.title → Header title',
    'data.result.summary.status → Status tag',
    'data.result.summary.application_type → Type tag',
    'data.result.summary.entity_status → Entity tag',
    'data.result.summary.application_number → Application Number card',
    'data.result.summary.patent_number → Patent Number card',
    'data.result.summary.filing_date → Filing Date card',
    'data.result.summary.grant_date → Grant Date card',
    'data.result.summary.status_date → Status Date card',
    'data.result.summary.examiner_name → Examiner card',
    'data.result.summary.first_inventor_name → First Inventor card',
    'data.result.summary.first_applicant_name → First Applicant card',
    'data.result.summary.group_art_unit → Group Art Unit card',
    'data.result.summary.class_subclass → Class / Subclass card',
    'data.result.summary.earliest_publication_number → Earliest Publication card',
    'data.result.summary.docket_number → Docket Number card',
    'data.result.summary.confirmation_number → Confirmation # card',
    'data.quota → Quota bar',
  ];
  updateDiagMapping(mappingRows.join('<br>'));
}

/* ── Helpers ── */
function detailCard(label, value) {
  return '<div class="tip-card"><div class="detail-label">' + escHtml(label) + '</div><div class="detail-value">' + value + '</div></div>';
}

function summaryRow(field, value) {
  return '<tr><td style="font-weight:500;white-space:nowrap;">' + escHtml(field) + '</td><td>' + escHtml(value != null ? String(value) : '—') + '</td></tr>';
}

function fmtAppNum(num) {
  if (!num) return '—';
  const s = String(num);
  if (s.length === 8 && /^\d+$/.test(s)) {
    return s.slice(0,2) + '/' + s.slice(2,6) + ',' + s.slice(6);
  }
  return escHtml(s);
}

function escHtml(str) {
  if (str == null) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function truncate(str, n) {
  if (!str) return 'n/a';
  return str.length > n ? str.slice(0, n) + '…' : str;
}

function showError(msg) {
  document.getElementById('errorCard').style.display = 'block';
  document.getElementById('errorContent').innerHTML = '<strong>Error</strong><br>' + escHtml(msg);
}

function hideError() {
  document.getElementById('errorCard').style.display = 'none';
}

function updateDiagApiCalls(v) { document.getElementById('diagApiCalls').innerHTML = v; }
function updateDiagInput(v) { document.getElementById('diagInput').innerHTML = escHtml(v); }
function updateDiagOutput(v) { document.getElementById('diagOutput').innerHTML = v; }
function updateDiagMapping(v) { document.getElementById('diagMapping').innerHTML = v; }

/* Populate request row on load */
document.getElementById('diagRequest').textContent = USER_REQUEST;
</script>
</body>
</html>
"""
