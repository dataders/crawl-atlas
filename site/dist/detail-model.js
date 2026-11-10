function characterState(character, events) {
  const mine = events.filter((event) => event.subject === character.name || (character.name === "Princess Donut" && event.subject === "Donut"));
  const levels = mine.filter((event) => event.type === "level");
  const statEvents = mine.filter((event) => event.type === "stat" && (event.stats || event.statsDelta));
  const skills = new Map();
  mine.filter((event) => event.type === "skill").forEach((event) => {
    const key = `${event.skillId ?? event.name.toLowerCase()}|${event.skillScope ?? "reported"}`;
    if (event.action === "remove") skills.delete(key);
    else skills.set(key, { name: event.name, scope: event.skillScope ?? "reported", level: event.level ?? skills.get(key)?.level ?? null, book: event.book ?? 1, chapter: event.chapter, detail: event.detail, source: event.source });
  });
  const stats = {};
  const baseStats = {};
  statEvents.forEach((event) => {
    Object.entries(event.stats ?? {}).forEach(([name, value]) => {
      const scope = event.statScopes?.[name];
      if (scope === "estimate" || scope === "lower-bound") return;
      stats[name] = value;
      if (scope === "base") baseStats[name] = value;
    });
    Object.keys(event.statsDelta ?? {}).forEach((name) => {
      const scope = event.statScopes?.[name];
      if (scope === "estimate" || scope === "lower-bound") return;
      // An allocation or equipment bonus does not establish a total. The last
      // observation may be stale or use a different scope, so never add to it.
      // Preserve a total explicitly supplied in this same observation.
      if (!Object.hasOwn(event.stats ?? {}, name)) stats[name] = null;
    });
  });
  const relationship = mine.filter((event) => event.type === "party" && event.relationship).at(-1)?.relationship ?? character.relationship ?? character.role ?? "Known character";
  const profile = Object.assign({}, ...mine.map(event => event.profile ?? {}));
  // Callers supply only revealed events, in reading order. Missing death data
  // is not evidence of survival, and a presumption is not a confirmed death.
  const lifeStatusEvent = mine.filter(event => !event.historyOnly && ["dead", "presumed-dead", "alive"].includes(event.lifeStatus)).at(-1);
  const lifeStatus = lifeStatusEvent?.lifeStatus ?? "unknown";
  return { character, relationship, profile, lifeStatus, lifeStatusEvent, levelEvent: levels.at(-1), level: levels.at(-1)?.level ?? null, levels, stats, baseStats, skills: [...skills.values()].sort((a, b) => (b.level ?? -Infinity) - (a.level ?? -Infinity) || a.name.localeCompare(b.name)), events: mine };
}

function inventoryKeys(events) {
  const names = new Map(events.filter(e => e.type === 'item' && e.itemId && !e.historyOnly)
    .map(e => [`${e.subject}|${e.name}`.toLowerCase(), `${e.subject}|id:${e.itemId}`.toLowerCase()]));
  return event => event.itemId ? `${event.subject}|id:${event.itemId}`.toLowerCase()
    : names.get(`${event.subject}|${event.name}`.toLowerCase()) ?? `${event.subject}|${event.name}`.toLowerCase();
}
function inventoryAt(events) {
  const inventory = new Map();
  const itemKey = inventoryKeys(events);
  const currentFloor = Math.max(0, ...events.filter(e => !e.historyOnly && e.mode === 'physical').map(e => e.floor ?? 0));
  events.filter((event) => event.type === "item" && !event.historyOnly).forEach((event) => {
    const key = itemKey(event);
    const previous = inventory.get(key) ?? {};
    if (["remove", "consume", "destroy", "lose"].includes(event.action)) {
      const priorQuantity = typeof previous.quantity === "number" ? previous.quantity : null;
      const usedQuantity = typeof event.quantity === "number" ? event.quantity : null;
      const remaining = event.remainingQuantity ?? (priorQuantity !== null && usedQuantity !== null ? priorQuantity - usedQuantity : null);
      if (remaining !== null && remaining > 0) inventory.set(key, { ...previous, quantity: remaining, state: previous.state ?? "carried" });
      else inventory.delete(key);
    } else {
      const quantity = typeof event.quantity === "number" && typeof previous.quantity === "number" && event.action === "add" ? previous.quantity + event.quantity : event.quantity ?? previous.quantity;
      inventory.set(key, { ...previous, ...event, quantity, acquiredProgress: previous.acquiredProgress ?? event.progress, acquiredBook: previous.acquiredBook ?? event.book, acquiredChapter: previous.acquiredChapter ?? event.chapter, state: event.action === "unequip" ? "carried" : event.action === "equip" || event.state === "equipped" ? "equipped" : event.state ?? previous.state ?? "carried" });
    }
  });
  return [...inventory.values()].filter(e => e.expiresAfterFloor == null || currentFloor <= e.expiresAfterFloor).sort((a, b) => a.subject.localeCompare(b.subject) || a.name.localeCompare(b.name));
}

// These records are both the dbt Charts input and the keys for its rendered rows.
function dossierTables(person) {
  return {
    stats: [...new Set([...Object.keys(person.baseStats), ...Object.keys(person.stats)])].map(stat =>
      ({stat, base: String(person.baseStats[stat] ?? '—'), reported: String(person.stats[stat] === person.baseStats[stat] ? '—' : person.stats[stat] ?? '—')})),
    skills: person.skills.map(s => ({skill:s.name, level:String(s.level ?? 'Known'), scope:s.scope, observed:`B${s.book} · Ch ${s.chapter}`})),
    history: person.levels.map(l => ({level:String(l.level ?? 'Total unknown'), observed:`B${l.book} · Ch ${l.chapter}`}))
  };
}
function itemStatBoost(item) {
  if (!item.statBoosts?.length) return '—';
  return item.statBoosts.map(boost => {
    const stat = boost.stat === 'ALL' ? 'All stats' : boost.stat;
    const amount = `${boost.value > 0 ? '+' : ''}${boost.value}${boost.unit === 'percent' ? '%' : ''}`;
    return `${stat} ${amount}${boost.condition ? ` (${boost.condition})` : ''}`;
  }).join(' · ');
}
function inventoryRecord(item) {
  return {item:item.name, owner:item.subject, stat_boost:itemStatBoost(item), quantity:String(item.quantity ?? '—'), state:item.state,
    type:item.category ?? 'Item', acquired:`B${item.acquiredBook ?? item.book ?? 1} · Ch ${item.acquiredChapter ?? item.chapter}`};
}
function progressionChange(fact) {
  if (fact.scope === 'estimate') return `${fact.metric} ≈${fact.value}`;
  if (fact.scope === 'lower-bound') return `${fact.metric} >${fact.value}`;
  if (fact.action === 'remove') return `${fact.metric} removed`;
  if (fact.action === 'delta' && fact.delta != null) {
    return `${fact.metric} ${fact.delta > 0 ? '+' : ''}${fact.delta} (${fact.scope})`;
  }
  if (fact.value == null) {
    if (fact.action === 'increase') return `${fact.metric} increased (total unknown)`;
    return `${fact.metric} observed`;
  }
  const value = fact.previous == null || fact.previous === fact.value
    ? fact.value : `${fact.previous} → ${fact.value}`;
  return `${fact.metric} ${value}`;
}

function eventChange(event) {
  const name = event.name ?? event.type;
  if (event.type === 'item') {
    const actions = {equip:'Equipped', add:'Acquired', remove:'Removed', note:'Observed'};
    return `${actions[event.action] ?? 'Observed'} ${name}`;
  }
  if (event.type === 'party' || event.type === 'story') return event.summary || name;
  return name;
}

// A single stat readout may contain several facts. Replace its generic story
// row with the individual observations rather than listing the event twice.
function storyEntries(events, facts, cutoff) {
  const byEvent = new Map();
  for (const fact of facts) {
    if (fact.progress > cutoff) continue;
    if (!byEvent.has(fact.event_id)) byEvent.set(fact.event_id, []);
    byEvent.get(fact.event_id).push(fact);
  }
  return events.filter(event => event.progress <= cutoff).toSorted((a,b) => b.progress - a.progress)
    .flatMap(event => {
      const where = `B${event.book} · Ch ${event.chapter} · ${Math.round(event.position * 100)}%`;
      const entry = (change, note) => ({
        type:event.type, row:{where, who:event.subject ?? 'Story', what_changed:change}, note
      });
      const observations = byEvent.get(event.id);
      if (!observations) return [entry(eventChange(event), [event.summary, event.detail, event.confidence, event.source].filter(Boolean).join(' · '))];
      return observations.map(fact => entry(progressionChange(fact),
        [fact.summary, fact.scope, fact.confidence, fact.source].filter(Boolean).join(' · ')));
    });
}
if (typeof module !== 'undefined') module.exports = {characterState, inventoryAt, inventoryKeys, dossierTables, inventoryRecord, itemStatBoost, storyEntries};
