const queryState = { page: 0, results: [] };
const queryFields = ['search', 'character', 'book', 'kind', 'scope', 'change', 'sort'];
function renderExplorer() {
  const visible = state.facts.filter(row => row.progress <= state.progress + 1e-8 && (state.followedCharacters === null || state.followedCharacters.includes(row.character)));
  for (const [field, label] of [['character', 'Everyone'], ['scope', 'All scopes'], ['book', 'All known books']]) {
    const select = $(`#query-${field}`), prior = select.value;
    const values = [...new Set(visible.map(row => String(row[field])))].sort();
    select.innerHTML = `<option value="">${label}</option>` + values.map(value => `<option value="${esc(value)}">${field === 'book' ? 'Book ' : ''}${esc(value)}</option>`).join('');
    select.value = values.includes(prior) ? prior : '';
  }
  const filters = Object.fromEntries(queryFields.map(field => [field, $(`#query-${field}`).value]));
  const terms = filters.search.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const results = visible.filter(row =>
    ['character', 'kind', 'scope'].every(field => !filters[field] || row[field] === filters[field]) &&
    (!filters.book || String(row.book) === filters.book) &&
    (!filters.change || (filters.change === 'increase' ? (row.delta > 0 || row.action === 'increase') : row.previous === null)) &&
    terms.every(term => `${row.character} ${row.metric} ${row.summary} ${row.source}`.toLowerCase().includes(term))
  );
  results.sort((a,b) => filters.sort === 'largest' ? (b.delta ?? -Infinity) - (a.delta ?? -Infinity) || b.progress - a.progress : filters.sort === 'oldest' ? a.progress - b.progress : b.progress - a.progress);
  queryState.results = results;
  const pages = Math.max(1, Math.ceil(results.length / 20));
  queryState.page = Math.min(queryState.page, pages - 1);
  $('#query-count').textContent = `${results.length} matching observations · ${visible.length} available at your position`;
  $('#query-page').textContent = `Page ${queryState.page + 1} of ${pages}`;
  $('#query-prev').disabled = queryState.page === 0;
  $('#query-next').disabled = queryState.page === pages - 1;
  $('#export-results').disabled = !results.length;
  $('#query-results').innerHTML = results.slice(queryState.page * 20, (queryState.page + 1) * 20).map(row => `<tr>
    <td><strong>${esc(row.metric)}</strong><span class="cell-subtitle">${esc(row.character)} · ${esc(row.kind)}</span></td>
    <td class="numeric">${row.previous ?? '—'} <span class="muted">→</span> ${row.value ?? (row.action === 'remove' ? 'Removed' : row.action === 'increase' ? 'Total unknown' : row.action === 'delta' ? 'Unstated' : 'Known')}</td>
    <td><span class="delta ${row.delta > 0 ? 'positive' : ''}">${row.delta === null ? (row.action === 'increase' ? 'Increased' : '—') : `${row.delta > 0 ? '+' : ''}${row.delta}`}</span></td>
    <td><span class="scope-tag">${esc(row.scope)}</span></td>
    <td class="location-cell">Book ${row.book} · Ch. ${row.chapter}<span class="cell-subtitle">${Math.round(row.position * 100)}% through chapter</span></td>
    <td><details><summary>${esc(row.confidence)}</summary><p>${esc(row.summary)}</p><code>${esc(row.source)}</code></details></td>
  </tr>`).join('') || '<tr><td colspan="6"><div class="empty"><strong>No observations here yet.</strong><br>Adjust your reading position or clear the filters. Unrecorded values are never guessed.</div></td></tr>';
}
function resetQuery() {
  queryFields.forEach(field => { $(`#query-${field}`).value = field === 'sort' ? 'newest' : ''; });
  queryState.page = 0;
}
document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click', () => {
  const url = new URL(window.location); url.searchParams.set('view', button.dataset.view); history.replaceState(null, '', url);
  document.querySelectorAll('[data-view]').forEach(tab => tab.setAttribute('aria-pressed', String(tab === button)));
  document.querySelector('.cast-selector').hidden = button.dataset.view === 'progression';
  ['explorer', 'progression', 'character', 'ledger', 'history', 'rewards'].forEach(view => { document.querySelector(`.${view}-section`).hidden = view !== button.dataset.view; });
}));
['explorer', 'character', 'ledger', 'history', 'rewards'].forEach(view => { document.querySelector(`.${view}-section`).hidden = true; });
queryFields.forEach(field => document.querySelector(`#query-${field}`).addEventListener(field === 'search' ? 'input' : 'change', () => { queryState.page = 0; renderExplorer(); }));
document.querySelectorAll('[data-preset]').forEach(button => button.addEventListener('click', () => {
  resetQuery();
  const preset = button.dataset.preset;
  if (preset !== 'all') $('#query-kind').value = preset;
  if (preset === 'level') $('#query-change').value = 'increase';
  if (preset === 'stat') $('#query-scope').value = 'base';
  renderExplorer();
}));
document.querySelector('#query-reset').addEventListener('click', () => { resetQuery(); renderExplorer(); });
document.querySelector('#query-prev').addEventListener('click', () => { queryState.page--; renderExplorer(); });
document.querySelector('#query-next').addEventListener('click', () => { queryState.page++; renderExplorer(); });
document.querySelector('#export-results').addEventListener('click', () => {
  const rows = queryState.results;
  if (!rows.length) return;
  const columns = Object.keys(rows[0]);
  const cell = value => `"${String(value ?? '').replace(/^[=+@-]/, "'$&").replace(/"/g, '""')}"`;
  const csv = [columns.map(cell).join(','), ...rows.map(row => columns.map(key => cell(row[key])).join(','))].join('\r\n');
  const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
  const a = document.createElement('a'); a.href = url; a.download = 'crawl-atlas-filtered.csv'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
