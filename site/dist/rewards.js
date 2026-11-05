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

function rewardRecord(row) {
  const {event, tier, kind} = row;
  return {reward:event.name, recipient:event.subject, stage:event.acquisition.stage,
    box:[tier || 'Unknown tier', kind].filter(Boolean).join(' · '),
    location:`B${event.book} · Ch ${event.chapter}`};
}
function rewardMatches(row, filters) {
  return (!filters.stage || row.event.acquisition.stage === filters.stage)
    && (!filters.tier || row.tier === filters.tier) && (!filters.kind || row.kind === filters.kind)
    && (!filters.search || row.search.includes(filters.search.trim().toLowerCase()));
}
if (typeof module !== 'undefined') module.exports = {rewardRows, rewardRecord, rewardMatches};
