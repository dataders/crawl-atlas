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
    Object.assign(stats, event.stats ?? {});
    Object.entries(event.stats ?? {}).forEach(([name, value]) => {
      if (event.statScopes?.[name] === "base") baseStats[name] = value;
    });
    Object.entries(event.statsDelta ?? {}).forEach(([name, delta]) => { stats[name] = (stats[name] ?? 0) + delta; });
  });
  const relationship = mine.filter((event) => event.type === "party" && event.relationship).at(-1)?.relationship ?? character.relationship ?? character.role ?? "Known character";
  const profile = Object.assign({}, ...mine.map(event => event.profile ?? {}));
  return { character, relationship, profile, levelEvent: levels.at(-1), level: levels.at(-1)?.level ?? null, levels, stats, baseStats, skills: [...skills.values()].sort((a, b) => (b.level ?? -Infinity) - (a.level ?? -Infinity) || a.name.localeCompare(b.name)), events: mine };
}

function inventoryAt(events) {
  const inventory = new Map();
  events.filter((event) => event.type === "item" && !event.historyOnly).forEach((event) => {
    const key = event.itemId ?? `${event.subject}|${event.name}`.toLowerCase();
    const previous = inventory.get(key) ?? {};
    if (["remove", "consume", "destroy", "lose"].includes(event.action)) {
      const priorQuantity = typeof previous.quantity === "number" ? previous.quantity : null;
      const usedQuantity = typeof event.quantity === "number" ? event.quantity : null;
      const remaining = event.remainingQuantity ?? (priorQuantity !== null && usedQuantity !== null ? priorQuantity - usedQuantity : null);
      if (remaining !== null && remaining > 0) inventory.set(key, { ...previous, quantity: remaining, state: previous.state ?? "carried" });
      else inventory.delete(key);
    } else {
      const quantity = typeof event.quantity === "number" && typeof previous.quantity === "number" && event.action === "add" ? previous.quantity + event.quantity : event.quantity ?? previous.quantity;
      inventory.set(key, { ...previous, ...event, quantity, acquiredProgress: previous.acquiredProgress ?? event.progress, acquiredBook: previous.acquiredBook ?? event.book, acquiredChapter: previous.acquiredChapter ?? event.chapter, state: event.action === "equip" || event.state === "equipped" ? "equipped" : event.action === "unequip" ? "carried" : event.state ?? previous.state ?? "carried" });
    }
  });
  return [...inventory.values()].sort((a, b) => a.subject.localeCompare(b.subject) || a.name.localeCompare(b.name));
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
function inventoryRecord(item) {
  return {item:item.name, owner:item.subject, quantity:String(item.quantity ?? '—'), state:item.state,
    type:item.category ?? 'Item', acquired:`B${item.acquiredBook ?? item.book ?? 1} · Ch ${item.acquiredChapter ?? item.chapter}`};
}
function storyRecord(e) {
  return {event:e.name ?? e.type, character:e.subject ?? 'Story', type:e.type,
    location:`B${e.book} · Ch ${e.chapter} · ${Math.round(e.position * 100)}%`};
}
if (typeof module !== 'undefined') module.exports = {characterState, inventoryAt, dossierTables, inventoryRecord, storyRecord};
