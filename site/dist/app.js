const SERIES = { Carl: "#d8ff3e", "Princess Donut": "#4dd9d2", Donut: "#4dd9d2", Mongo: "#ff6441" };
const EVENT_COLORS = { level: "#d8ff3e", skill: "#4dd9d2", item: "#ff6441", party: "#ad8cff", stat: "#f5ca5c", story: "#8e9ba5" };
const state = { data: null, progress: 0.135, selectedCharacter: null, inventoryOwner: "All", inventorySearch: "", historyFilter: "All" };
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));
const slug = (value) => String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

function eventProgress(event, chapterCount) {
  if (Number.isFinite(event.progress)) return event.progress;
  return Math.min(1, Math.max(0, ((event.chapter - 1) + (event.position ?? 0)) / chapterCount));
}

function normalizeData(raw) {
  if (Array.isArray(raw.events)) {
    raw.events.forEach((event) => { event.progress = eventProgress(event, raw.book.chapterCount); });
    raw.events.sort((a, b) => a.progress - b.progress);
    return raw;
  }

  const characters = {};
  const events = [];
  const seen = new Set();
  const add = (event) => {
    const key = event.dedupe ?? [event.type, event.subject, event.name, event.level, event.chapter, event.action].join("|");
    if (seen.has(key)) return;
    seen.add(key);
    events.push({ id: event.id ?? slug(key), confidence: event.confidence ?? "verified", ...event, progress: eventProgress(event, raw.book.chapterCount) });
  };

  raw.checkpoints.forEach((checkpoint) => {
    checkpoint.party.forEach((member) => {
      const name = member.name === "Donut" ? "Princess Donut" : member.name;
      characters[name] ??= { id: slug(name), name, role: member.role, color: SERIES[name] ?? "#f5ca5c" };
      add({ type: "party", action: "join", subject: name, name, summary: `${name} is present with the party.`, chapter: checkpoint.chapter, position: checkpoint.position, source: checkpoint.source, dedupe: `party|${name}` });
      if (member.level !== null) add({ type: "level", action: "set", subject: name, name: "Character level", level: member.level, summary: `${name} reaches level ${member.level}.`, chapter: checkpoint.chapter, position: checkpoint.position, source: checkpoint.source, confidence: member.confidence, dedupe: `level|${name}|${member.level}` });
      if (member.stats?.length) add({ type: "stat", action: "set", subject: name, name: "Character stats", stats: Object.fromEntries(member.stats.map((stat) => [stat.name, stat.value])), summary: `${name}'s stats are displayed.`, chapter: checkpoint.chapter, position: checkpoint.position, source: checkpoint.source, dedupe: `stats|${name}|${JSON.stringify(member.stats)}` });
    });
    checkpoint.skills.forEach((skill) => add({ type: "skill", action: "set", subject: skill.owner === "Donut" ? "Princess Donut" : skill.owner, name: skill.name, level: skill.level, summary: `${skill.owner}'s ${skill.name}${skill.level ? ` reaches level ${skill.level}` : " is confirmed"}.`, chapter: checkpoint.chapter, position: checkpoint.position, source: checkpoint.source, confidence: skill.confidence, dedupe: `skill|${skill.owner}|${skill.name}|${skill.level}` }));
    checkpoint.inventory.forEach((item) => add({ type: "item", action: item.kind === "Consumed" ? "consume" : "add", subject: item.owner === "Donut" ? "Princess Donut" : item.owner, name: item.name, category: item.kind, state: item.kind === "Equipped" ? "equipped" : item.kind === "Consumed" ? "consumed" : "carried", detail: item.detail, summary: `${item.owner}: ${item.name} (${item.kind.toLowerCase()}).`, chapter: checkpoint.chapter, position: checkpoint.position, source: checkpoint.source, confidence: item.confidence, dedupe: `item|${item.owner}|${item.name}` }));
    checkpoint.changes.forEach((summary, index) => add({ type: "story", action: "note", subject: "Party", name: checkpoint.label, summary, chapter: checkpoint.chapter, position: Math.min(.999, checkpoint.position + index / 1000), source: checkpoint.source, dedupe: `story|${checkpoint.id}|${index}` }));
  });
  return { book: raw.book, characters: Object.values(characters), events: events.sort((a, b) => a.progress - b.progress) };
}

function currentLocation() {
  const count = state.data.book.chapterCount;
  const scaled = Math.min(count - Number.EPSILON, state.progress * count);
  return { chapter: Math.floor(scaled) + 1, position: scaled - Math.floor(scaled) };
}

function visibleEvents() { return state.data.events.filter((event) => event.progress <= state.progress + 1e-8); }

function partyAt(events) {
  const membership = new Map();
  events.filter((event) => event.type === "party" && ["join", "leave"].includes(event.action)).forEach((event) => membership.set(event.subject, event.action !== "leave"));
  return state.data.characters.filter((character) => membership.get(character.name));
}

function characterState(character, events) {
  const mine = events.filter((event) => event.subject === character.name || (character.name === "Princess Donut" && event.subject === "Donut"));
  const levels = mine.filter((event) => event.type === "level" && Number.isFinite(event.level));
  const statEvents = mine.filter((event) => event.type === "stat" && (event.stats || event.statsDelta));
  const skills = new Map();
  mine.filter((event) => event.type === "skill").forEach((event) => {
    const key = event.name.toLowerCase();
    if (event.action === "remove") skills.delete(key);
    else skills.set(key, { name: event.name, level: event.level ?? skills.get(key)?.level ?? null, chapter: event.chapter, detail: event.detail, source: event.source });
  });
  const stats = {};
  statEvents.forEach((event) => {
    Object.assign(stats, event.stats ?? {});
    Object.entries(event.statsDelta ?? {}).forEach(([name, delta]) => { stats[name] = (stats[name] ?? 0) + delta; });
  });
  return { character, level: levels.at(-1)?.level ?? null, levels, stats, skills: [...skills.values()].sort((a, b) => a.name.localeCompare(b.name)), events: mine };
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
      inventory.set(key, { ...previous, ...event, quantity, acquiredChapter: previous.acquiredChapter ?? event.chapter, state: event.action === "equip" || event.state === "equipped" ? "equipped" : event.action === "unequip" ? "carried" : event.state ?? previous.state ?? "carried" });
    }
  });
  return [...inventory.values()].sort((a, b) => a.subject.localeCompare(b.subject) || a.name.localeCompare(b.name));
}

function renderPosition() {
  const location = currentLocation();
  $("#location-chapter").textContent = `Chapter ${location.chapter}`;
  $("#location-percent").textContent = `${Math.round(location.position * 100)}% through chapter`;
  $("#overall-progress").textContent = `${Math.round(state.progress * 100)}% of book`;
  $("#book-range").value = Math.round(state.progress * 10000);
  $("#book-range").style.setProperty("--range-fill", `${state.progress * 100}%`);
  $("#chapter-ruler").style.setProperty("--range-fill", `${state.progress * 100}%`);
}

function renderChart(events, party) {
  const svg = $("#progress-chart");
  const width = 1200, height = 330, left = 54, right = 24, top = 25, bottom = 48;
  const maxKnown = Math.max(15, ...events.filter((e) => e.type === "level" && Number.isFinite(e.level)).map((e) => e.level));
  const x = (progress) => left + progress * (width - left - right);
  const y = (level) => top + (maxKnown - level) / maxKnown * (height - top - bottom);
  const parts = [];
  for (let level = 0; level <= maxKnown; level += maxKnown > 20 ? 5 : 3) {
    parts.push(`<line class="chart-grid" x1="${left}" y1="${y(level)}" x2="${width-right}" y2="${y(level)}"/><text class="chart-axis" x="9" y="${y(level)+4}">LVL ${level}</text>`);
  }
  for (let chapter = 1; chapter <= state.data.book.chapterCount; chapter += 5) parts.push(`<text class="chart-axis" x="${x((chapter-1)/state.data.book.chapterCount)}" y="${height-12}">C${chapter}</text>`);
  const chartCharacters = state.data.characters.filter((character) => events.some((event) => event.type === "level" && event.subject === character.name));
  chartCharacters.forEach((character) => {
    const levels = events.filter((event) => event.type === "level" && event.subject === character.name && Number.isFinite(event.level));
    if (!levels.length) return;
    const color = character.color ?? SERIES[character.name] ?? "#f5ca5c";
    let path = `M ${x(levels[0].progress)} ${y(levels[0].level)}`;
    levels.slice(1).forEach((event) => { path += ` H ${x(event.progress)} V ${y(event.level)}`; });
    path += ` H ${x(state.progress)}`;
    parts.push(`<path class="level-path" style="--series-color:${color}" d="${path}"/>`);
    levels.forEach((event) => parts.push(`<circle class="level-dot chart-event" style="--series-color:${color}" cx="${x(event.progress)}" cy="${y(event.level)}" r="5" data-event="${esc(event.id)}"/>`));
  });
  const eventRows = { skill: height - 38, item: height - 25, party: height - 12 };
  events.filter((event) => eventRows[event.type]).forEach((event) => {
    const shape = event.type === "party"
      ? `<path class="event-dot chart-event" fill="${EVENT_COLORS[event.type]}" d="M ${x(event.progress)} ${eventRows[event.type]-6} l 6 11 h -12 z" data-event="${esc(event.id)}"/>`
      : `<rect class="event-dot chart-event" fill="${EVENT_COLORS[event.type]}" x="${x(event.progress)-4}" y="${eventRows[event.type]-4}" width="8" height="8" transform="${event.type === "skill" ? `rotate(45 ${x(event.progress)} ${eventRows[event.type]})` : ""}" data-event="${esc(event.id)}"/>`;
    parts.push(shape);
  });
  parts.push(`<line class="selection-line" x1="${x(state.progress)}" y1="${top}" x2="${x(state.progress)}" y2="${height-bottom+13}"/>`);
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.innerHTML = parts.join("");
  $("#chart-legend").innerHTML = chartCharacters.map((character) => `<span class="legend-person" style="--person-color:${character.color ?? SERIES[character.name]}"><i></i>${esc(character.name)}</span>`).join("");
  const tooltip = $("#chart-tooltip");
  svg.querySelectorAll(".chart-event").forEach((node) => {
    const show = (event) => {
      const datum = state.data.events.find((entry) => entry.id === node.dataset.event);
      if (!datum) return;
      const rect = svg.getBoundingClientRect();
      tooltip.innerHTML = `<strong>Chapter ${datum.chapter}</strong>${esc(datum.summary ?? datum.name)}`;
      tooltip.hidden = false;
      tooltip.style.left = `${Math.min(rect.width - 270, Math.max(8, event.clientX - rect.left + 10))}px`;
      tooltip.style.top = `${Math.max(8, event.clientY - rect.top - 58)}px`;
    };
    node.addEventListener("mouseenter", show);
    node.addEventListener("mousemove", show);
    node.addEventListener("mouseleave", () => { tooltip.hidden = true; });
  });
}

function renderCharacters(events, party) {
  if (!party.length) {
    $("#party-count").textContent = "No party yet";
    $("#character-list").innerHTML = "";
    $("#character-dossier").innerHTML = '<div class="empty">No party members are known at this point.</div>';
    return;
  }
  if (!party.some((character) => character.name === state.selectedCharacter)) state.selectedCharacter = party[0].name;
  const states = party.map((character) => characterState(character, events));
  $("#party-count").textContent = `${states.length} ${states.length === 1 ? "member" : "members"}`;
  $("#character-list").innerHTML = states.map(({ character, level, skills }) => `<button class="character-tab ${character.name === state.selectedCharacter ? "active" : ""}" role="tab" aria-selected="${character.name === state.selectedCharacter}" data-character="${esc(character.name)}" style="--person-color:${character.color ?? SERIES[character.name]}"><span><strong>${esc(character.name)}</strong><span>${esc(character.role ?? "Party member")} · ${skills.length} skills</span></span><span class="mini-level"><small>Level</small>${level ?? "—"}</span></button>`).join("");
  $("#character-list").querySelectorAll("[data-character]").forEach((button) => button.addEventListener("click", () => { state.selectedCharacter = button.dataset.character; renderAll(); }));
  const selected = states.find(({ character }) => character.name === state.selectedCharacter);
  const color = selected.character.color ?? SERIES[selected.character.name];
  const statEntries = Object.entries(selected.stats);
  const levelHistory = selected.levels.map((event) => `<span>Ch. ${event.chapter}: ${event.level}</span>`).join(" → ");
  $("#character-dossier").style.setProperty("--person-color", color);
  $("#character-dossier").innerHTML = `
    <header class="dossier-head"><div><p class="eyebrow">Selected character</p><h3>${esc(selected.character.name)}</h3><span class="dossier-role">${esc(selected.character.role ?? "Party member")}</span></div><div class="dossier-level"><small>CURRENT LEVEL</small>${selected.level ?? "—"}</div></header>
    <div class="dossier-grid">
      <div class="dossier-block"><h4>Current stats</h4>${statEntries.length ? `<div class="stats">${statEntries.map(([name,value]) => `<div class="stat"><span>${esc(name)}</span>${esc(value)}</div>`).join("")}</div>` : '<div class="empty">No full stat display yet.</div>'}<h4 style="margin-top:20px">Level history</h4><div class="skill-meta">${levelHistory || "No explicit level shown yet."}</div></div>
      <div class="dossier-block"><h4>All known skills & spells</h4>${selected.skills.length ? `<div class="skills-grid">${selected.skills.map((skill) => `<div class="skill-card"><strong>${esc(skill.name)}</strong><span>${skill.level !== null ? `L${esc(skill.level)}` : "KNOWN"}</span><div class="skill-meta">Confirmed by Ch. ${skill.chapter}${skill.detail ? ` · ${esc(skill.detail)}` : ""}</div></div>`).join("")}</div>` : '<div class="empty">No named skills revealed yet.</div>'}</div>
    </div>`;
}

function renderInventory(events) {
  const allItems = inventoryAt(events);
  const owners = ["All", ...new Set(allItems.map((item) => item.subject))];
  if (!owners.includes(state.inventoryOwner)) state.inventoryOwner = "All";
  $("#inventory-owner-filters").innerHTML = owners.map((owner) => `<button type="button" class="filter-button ${owner === state.inventoryOwner ? "active" : ""}" data-owner="${esc(owner)}">${esc(owner)}</button>`).join("");
  $("#inventory-owner-filters").querySelectorAll("[data-owner]").forEach((button) => button.addEventListener("click", () => { state.inventoryOwner = button.dataset.owner; renderInventory(events); }));
  const query = state.inventorySearch.trim().toLowerCase();
  const items = allItems.filter((item) => (state.inventoryOwner === "All" || item.subject === state.inventoryOwner) && (!query || `${item.name} ${item.category ?? ""} ${item.detail ?? ""}`.toLowerCase().includes(query)));
  $("#inventory-count").textContent = `${allItems.length} active ${allItems.length === 1 ? "entry" : "entries"}`;
  $("#inventory-list").innerHTML = items.length ? items.map((item) => `<tr><td><div class="inventory-name">${esc(item.name)}${item.quantity ? ` ×${esc(item.quantity)}` : ""}</div>${item.detail ? `<div class="inventory-detail">${esc(item.detail)}</div>` : ""}</td><td>${esc(item.subject)}</td><td>${esc(item.category ?? "Item")}</td><td><span class="state-pill ${esc(item.state)}">${esc(item.state)}</span></td><td>Ch. ${esc(item.acquiredChapter ?? item.chapter)}</td></tr>`).join("") : '<tr><td colspan="5"><div class="empty">No matching active inventory.</div></td></tr>';
}

function renderHistory(events) {
  const filters = ["All", "level", "skill", "item", "party", "stat", "story"];
  $("#history-filters").innerHTML = filters.map((filter) => `<button type="button" class="filter-button ${filter === state.historyFilter ? "active" : ""}" data-history-filter="${filter}">${filter}</button>`).join("");
  $("#history-filters").querySelectorAll("[data-history-filter]").forEach((button) => button.addEventListener("click", () => { state.historyFilter = button.dataset.historyFilter; renderHistory(events); }));
  const filtered = events.filter((event) => state.historyFilter === "All" || event.type === state.historyFilter);
  $("#history-count").textContent = `${events.length} events known`;
  $("#history-list").innerHTML = filtered.length ? filtered.map((event) => `<li class="history-event" style="--event-color:${EVENT_COLORS[event.type] ?? EVENT_COLORS.story}"><span class="history-location">Chapter ${event.chapter}<br>${Math.round((event.position ?? 0)*100)}%</span><i class="history-marker"></i><div class="history-copy"><strong>${esc(event.subject ?? "Story")} · ${esc(event.name ?? event.type)}</strong><span>${esc(event.summary ?? event.detail ?? "")}</span></div></li>`).join("") : '<li class="empty">No events in this category yet.</li>';
}

function renderAll() {
  const events = visibleEvents();
  const party = partyAt(events);
  renderPosition();
  renderChart(events, party);
  renderCharacters(events, party);
  renderInventory(events);
  renderHistory(events);
  const url = new URL(window.location);
  url.search = "";
  url.searchParams.set("progress", Math.round(state.progress * 10000));
  history.replaceState(null, "", url);
}

async function start() {
  const response = await fetch("data/book-1.json?v=1.0.0", { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load dataset (${response.status})`);
  state.data = normalizeData(await response.json());
  state.data.characters ??= [];
  const params = new URLSearchParams(window.location.search);
  if (params.has("progress")) state.progress = Math.min(1, Math.max(0, Number(params.get("progress")) / 10000));
  else if (params.has("chapter")) state.progress = Math.min(1, ((Number(params.get("chapter")) || 1) - 1 + (Number(params.get("position")) || 0) / 100) / state.data.book.chapterCount);
  $("#book-title").textContent = `${state.data.book.title} · ${state.data.book.subtitle}`;
  $("#data-version").textContent = state.data.book.dataVersion;
  $("#last-chapter-label").textContent = `Chapter ${state.data.book.chapterCount}`;
  renderAll();
}

$("#book-range").addEventListener("input", (event) => { state.progress = Number(event.target.value) / 10000; renderAll(); });
$("#previous-chapter").addEventListener("click", () => { const { chapter } = currentLocation(); state.progress = Math.max(0, (chapter - 2) / state.data.book.chapterCount); renderAll(); });
$("#next-chapter").addEventListener("click", () => { const { chapter } = currentLocation(); state.progress = Math.min(1, chapter / state.data.book.chapterCount); renderAll(); });
$("#inventory-search").addEventListener("input", (event) => { state.inventorySearch = event.target.value; renderInventory(visibleEvents()); });
$("#about-button").addEventListener("click", () => { $("#about-panel").hidden = false; $("#about-button").setAttribute("aria-expanded", "true"); $("#about-close").focus(); });
$("#about-close").addEventListener("click", () => { $("#about-panel").hidden = true; $("#about-button").setAttribute("aria-expanded", "false"); $("#about-button").focus(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !$("#about-panel").hidden) $("#about-close").click(); });

start().catch((error) => { document.querySelector("main").innerHTML = `<section class="empty"><h1>Dataset unavailable</h1><p>${esc(error.message)}</p></section>`; });
