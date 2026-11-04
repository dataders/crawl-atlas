function rewardRows(events, visible) {
  const known = new Map(visible.map(e => [e.id, e]));
  const boxes = new Map();
  visible.forEach(e => {
    const a = e.acquisition;
    if (a?.boxId) boxes.set(a.boxId, {...boxes.get(a.boxId), ...Object.fromEntries(Object.entries(a).filter(([,v]) => v != null))});
  });
  function ancestors(event, seen = new Set()) {
    const chain = [];
    for (const id of event.acquisition?.parentEventIds ?? []) {
      if (seen.has(id) || !known.has(id)) continue;
      seen.add(id);
      const parent = known.get(id);
      chain.push(...ancestors(parent, seen), parent);
    }
    return chain;
  }
  return events.filter(e => e.acquisition).map(event => {
    const parents = ancestors(event), lineage = [...parents, event];
    const box = lineage.findLast(e => e.acquisition?.boxId)?.acquisition;
    const latestBox = box ? boxes.get(box.boxId) : null;
    return {event, parents, tier: latestBox?.boxTier ?? '', kind: latestBox?.boxKind ?? '',
      search: lineage.map(e => `${e.subject} ${e.name} ${e.summary ?? ''} ${e.acquisition?.reasonDetail ?? ''}`).join(' ').toLowerCase()};
  });
}
function renderRewards(events) {
  const rows = rewardRows(events, visibleEvents());
  for (const field of ['tier', 'kind']) {
    const select = document.querySelector(`#reward-${field}`), previous = select.value;
    const options = [...new Set(rows.map(r => r[field]).filter(Boolean))].sort();
    select.innerHTML = `<option value="">All ${field === 'tier' ? 'tiers' : 'types'}</option>` + options.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
    select.value = options.includes(previous) ? previous : '';
  }
  const search = document.querySelector('#reward-search').value.toLowerCase().trim();
  const stage = document.querySelector('#reward-stage').value;
  const tier = document.querySelector('#reward-tier').value;
  const kind = document.querySelector('#reward-kind').value;
  const matches = rows.filter(r => (!stage || r.event.acquisition.stage === stage) && (!tier || r.tier === tier) && (!kind || r.kind === kind) && (!search || r.search.includes(search))).sort((a,b) => b.event.progress-a.event.progress);
  document.querySelector('#reward-count').textContent = `${matches.length} matching records`;
  document.querySelector('#reward-results').innerHTML = matches.map(({event:e, parents,tier,kind}) => `<tr>
    <td><strong>${esc(e.name)}</strong><span class="cell-subtitle">${esc(e.subject)}${e.acquisition.quantity != null ? ` · ×${e.acquisition.quantity}` : ''}</span></td>
    <td>${esc(e.acquisition.stage)}${e.acquisition.outcomeType ? `<span class="cell-subtitle">${esc(e.acquisition.outcomeType.replaceAll('_',' '))}</span>` : ''}</td>
    <td>${esc(tier || 'Unknown tier')}<span class="cell-subtitle">${esc(kind || 'Unspecified type')}</span></td>
    <td>${parents.length ? parents.map(p => esc(p.name)).join(' → ') : esc(e.acquisition.reasonDetail ?? 'Cause not recorded')}
      <details><summary>${e.acquisition.attribution === 'batch' ? 'Batch attribution · specific box unknown' : 'Evidence'}</summary>
      <p>${esc(e.summary ?? '')}</p><code>${esc(e.source)}</code>
      ${e.acquisition.occurrenceDetail ? `<p>${esc(e.acquisition.occurrenceDetail)}</p>` : ''}
      ${parents.map(p => `<div>${esc(p.name)} · B${p.book} C${p.chapter} · <code>${esc(p.source)}</code></div>`).join('')}</details></td>
    <td>B${e.book} · Ch. ${e.chapter}</td></tr>`).join('') || '<tr><td colspan="5"><div class="empty">No matching reward records at this reading position.</div></td></tr>';
}
for (const id of ['search','stage','tier','kind']) document.querySelector(`#reward-${id}`).addEventListener(id==='search'?'input':'change', () => renderRewards(followedEvents(visibleEvents())));
