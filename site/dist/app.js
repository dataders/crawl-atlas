const SERIES = { Carl: "#d8ff3e", "Princess Donut": "#4dd9d2", Donut: "#4dd9d2", Mongo: "#ff6441" };
const EVENT_COLORS = { level: "#d8ff3e", skill: "#4dd9d2", item: "#ff6441", party: "#ad8cff", stat: "#f5ca5c", story: "#8e9ba5" };
const state = { data: null, progress: 0, chartMetric: "level", selectedCharacter: null, rosterFilter: "All", inventoryOwner: "All", inventorySearch: "", historyFilter: "All", followedCharacters: null };
const $ = (selector) => document.querySelector(selector);
const esc = (value) => String(value ?? "").replace(/[&<>'"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[c]));
const slug = (value) => String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");

function eventProgress(event, chapterCount) {
  if (Number.isFinite(event.progress)) return event.progress;
  return Math.min(1, Math.max(0, ((event.chapter - 1) + (event.position ?? 0)) / chapterCount));
}

function normalizeData(raw) {
  if (Array.isArray(raw.events)) {
    const count = raw.series?.chapterCount ?? raw.book?.chapterCount;
    raw.events.forEach((event) => { event.progress = eventProgress(event, count); });
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
  const count = state.data.series.chapterCount;
  const scaled = Math.min(count - 1e-9, state.progress * count);
  const globalChapter = Math.floor(scaled) + 1;
  const book = state.data.books.find((row) => globalChapter >= row.startChapter && globalChapter <= row.endChapter) ?? state.data.books.at(-1);
  return { book, chapter: globalChapter - book.startChapter + 1, globalChapter, position: scaled - Math.floor(scaled) };
}

function progressFor(bookNumber, chapter, position = 0) {
  const book = state.data.books.find((row) => row.number === Number(bookNumber));
  const localChapter = Math.min(book.chapterCount, Math.max(1, Number(chapter) || 1));
  return Math.min(1, (book.startChapter + localChapter - 2 + position) / state.data.series.chapterCount);
}

function visibleEvents() { return state.data.events.filter((event) => event.progress <= state.progress + 1e-8); }

function followedEvents(events = visibleEvents()) {
  return state.followedCharacters === null ? events : events.filter(event => state.followedCharacters.includes(event.subject));
}
function renderCast(events) {
  const names = new Set(events.map(event => event.subject));
  const known = state.data.characters.filter(character => names.has(character.name));
  $('#cast-options').innerHTML = known.map(character => `<label class="cast-chip"><input type="checkbox" value="${esc(character.name)}" ${state.followedCharacters === null || state.followedCharacters.includes(character.name) ? 'checked' : ''}><span style="--person-color:${character.color}">${esc(character.name)}</span></label>`).join('') || '<span class="empty">Character choices appear as you meet them.</span>';
  const selected = known.filter(character => state.followedCharacters === null || state.followedCharacters.includes(character.name));
  $('#cast-status').textContent = `${selected.length} of ${known.length} known characters selected · Applies to every view and export. Saved on this device.`;
  $('#cast-options').querySelectorAll('input').forEach(input => input.addEventListener('change', () => {
    const selection = new Set(state.followedCharacters ?? known.map(character => character.name));
    input.checked ? selection.add(input.value) : selection.delete(input.value);
    saveCast([...selection]);
  }));
}
function saveCast(selection) {
  state.followedCharacters = selection;
  try { localStorage.setItem('crawl-atlas-cast', JSON.stringify(selection)); } catch {}
  renderAll();
}

function partyAt(events) {
  const membership = new Map();
  events.filter((event) => event.type === "party" && ["join", "leave"].includes(event.action)).forEach((event) => membership.set(event.subject, event.action !== "leave"));
  return state.data.characters.filter((character) => membership.get(character.name));
}

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
  return { character, relationship, profile, levelEvent: levels.at(-1), level: levels.at(-1)?.level ?? null, levels, stats, baseStats, skills: [...skills.values()].sort((a, b) => a.name.localeCompare(b.name)), events: mine };
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
      inventory.set(key, { ...previous, ...event, quantity, acquiredBook: previous.acquiredBook ?? event.book, acquiredChapter: previous.acquiredChapter ?? event.chapter, state: event.action === "equip" || event.state === "equipped" ? "equipped" : event.action === "unequip" ? "carried" : event.state ?? previous.state ?? "carried" });
    }
  });
  return [...inventory.values()].sort((a, b) => a.subject.localeCompare(b.subject) || a.name.localeCompare(b.name));
}

function renderPosition() {
  const location = currentLocation();
  $("#location-chapter").textContent = `Book ${location.book.number} · Chapter ${location.chapter}`;
  $("#location-percent").textContent = `${Math.round(location.position * 100)}% through chapter`;
  $("#overall-progress").textContent = `${Math.round(state.progress * 100)}% of series`;
  $("#book-range").value = Math.round(state.progress * 10000);
  $("#book-range").style.setProperty("--range-fill", `${state.progress * 100}%`);
  $("#chapter-ruler").style.setProperty("--range-fill", `${state.progress * 100}%`);
  const bookSelect = $("#book-select");
  if (bookSelect.options.length !== state.data.books.length) {
    bookSelect.innerHTML = state.data.books.map((book) => `<option value="${book.number}">Book ${book.number} · ${esc(book.title)}</option>`).join("");
  }
  bookSelect.value = String(location.book.number);
  const chapterSelect = $("#chapter-select");
  if (chapterSelect.dataset.book !== String(location.book.number)) {
    chapterSelect.innerHTML = Array.from({ length: location.book.chapterCount }, (_, index) => `<option value="${index + 1}">Chapter ${index + 1}</option>`).join("");
    chapterSelect.dataset.book = String(location.book.number);
  }
  chapterSelect.value = String(location.chapter);
}

function renderChart(events) {
  const select = $("#chart-character");
  const previous = select.value;
  const known = state.data.characters.filter(person => events.some(event => event.subject === person.name));
  select.innerHTML = known.map(person => `<option>${esc(person.name)}</option>`).join("");
  if (known.some(person => person.name === previous)) select.value = previous;
  else if (known.some(person => person.name === "Carl")) select.value = "Carl";
  select.disabled = !known.length;
  const rows = state.facts.filter(row => row.character === select.value && row.progress <= state.progress &&
    (row.kind === "level" || row.kind === "stat"));
  const checkpoint = rows.at(-1);
  $("#reader-chart-stack").innerHTML = checkpoint
    ? `<img src="reader-charts/${encodeURIComponent(checkpoint.event_id)}.svg" alt="${esc(select.value)}: level and five stat histories through Book ${checkpoint.book}, Chapter ${checkpoint.chapter}">`
    : '<p class="empty">No level or stat observations at this reading position.</p>';
}

function renderCharacters(events, roster) {
  if (!roster.length) {
    $("#party-count").textContent = "No characters known yet";
    $("#roster-filters").innerHTML = "";
    $("#character-list").innerHTML = "";
    $("#character-dossier").innerHTML = '<div class="empty">No selected characters are known at this point. Adjust Your cast or the reading position.</div>';
    return;
  }
  const filters = [{ id: "All", label: "All" }, { id: "core", label: "Core" }, { id: "support", label: "Support" }, { id: "ally", label: "Allies" }];
  const availableFilters = filters.filter((filter) => filter.id === "All" || roster.some((character) => character.group === filter.id));
  if (!availableFilters.some((filter) => filter.id === state.rosterFilter)) state.rosterFilter = "All";
  $("#roster-filters").innerHTML = availableFilters.map((filter) => `<button type="button" class="filter-button ${filter.id === state.rosterFilter ? "active" : ""}" data-roster-filter="${filter.id}">${filter.label}</button>`).join("");
  $("#roster-filters").querySelectorAll("[data-roster-filter]").forEach((button) => button.addEventListener("click", () => { state.rosterFilter = button.dataset.rosterFilter; renderCharacters(events, roster); }));
  const allStates = roster.map((character) => characterState(character, events));
  const states = allStates.filter(({ character }) => state.rosterFilter === "All" || character.group === state.rosterFilter);
  if (!states.some(({ character }) => character.name === state.selectedCharacter)) state.selectedCharacter = states[0].character.name;
  $("#party-count").textContent = `${allStates.length} known ${allStates.length === 1 ? "character" : "characters"}`;
  $("#character-list").innerHTML = states.map(({ character, relationship, level, skills }) => `<button class="character-tab ${character.name === state.selectedCharacter ? "active" : ""}" role="tab" aria-selected="${character.name === state.selectedCharacter}" data-character="${esc(character.name)}" style="--person-color:${character.color ?? SERIES[character.name]}"><span><strong>${esc(character.name)}</strong><span>${esc(relationship)} · ${skills.length} ${skills.length === 1 ? "skill" : "skills"}</span></span><span class="mini-level"><small>Observed</small>${level ?? "—"}</span></button>`).join("");
  $("#character-list").querySelectorAll("[data-character]").forEach((button) => button.addEventListener("click", () => { state.selectedCharacter = button.dataset.character; renderAll(); }));
  const selected = states.find(({ character }) => character.name === state.selectedCharacter);
  const color = selected.character.color ?? SERIES[selected.character.name];
  const baseStatEntries = Object.entries(selected.baseStats);
  const reportedEntries = Object.entries(selected.stats).filter(([name, value]) => selected.baseStats[name] !== value);
  const levelHistory = selected.levels.map((event) => `<span>B${event.book} Ch. ${event.chapter}: ${event.level ?? "Increased; total unknown"}</span>`).join(" → ");
  $("#character-dossier").style.setProperty("--person-color", color);
  $("#character-dossier").innerHTML = `
    <header class="dossier-head"><div><p class="eyebrow">Selected character</p><h3>${esc(selected.character.name)}</h3><span class="dossier-role">${esc(selected.relationship)}${Object.keys(selected.profile).length ? ` · ${esc(Object.values(selected.profile).join(" · "))}` : ""}</span></div><div class="dossier-level"><small>LAST OBSERVED</small>${selected.level ?? "Unknown"}<small>${selected.levelEvent ? `Book ${selected.levelEvent.book} · Ch. ${selected.levelEvent.chapter}` : "No level recorded"}</small></div></header>
    <p class="observation-note">${selected.levelEvent?.action === "increase" ? `Later level gains are confirmed in Book ${selected.levelEvent.book}, Chapter ${selected.levelEvent.chapter}, but the exact total is unstated. ${esc(selected.levelEvent.summary)}` : selected.levelEvent ? `Level last observed in Book ${selected.levelEvent.book}, Chapter ${selected.levelEvent.chapter}. Later growth may not be recorded; this is not a claim about their current level.` : "No explicit level recorded for this character yet."}</p>
    <div class="dossier-grid">
      <div class="dossier-block"><h4>Confirmed base stats</h4>${baseStatEntries.length ? `<div class="stats">${baseStatEntries.map(([name,value]) => `<div class="stat"><span>${esc(name)}</span>${esc(value)}</div>`).join("")}</div><div class="skill-meta">Latest explicitly unmodified values; unreported growth is not guessed.</div>` : '<div class="empty">No unmodified stat display yet.</div>'}${reportedEntries.length ? `<h4 style="margin-top:20px">Reported with modifiers</h4><div class="stats">${reportedEntries.map(([name,value]) => `<div class="stat modified"><span>${esc(name)}</span>${esc(value)}</div>`).join("")}</div>` : ""}<h4 style="margin-top:20px">Level history</h4><div class="skill-meta">${levelHistory || "No explicit level shown yet."}</div></div>
      <div class="dossier-block"><h4>All known skills & spells</h4>${selected.skills.length ? `<div class="skills-grid">${selected.skills.map((skill) => `<div class="skill-card"><strong>${esc(skill.name)}</strong><span>${skill.level !== null ? `L${esc(skill.level)}` : "KNOWN"}</span><div class="skill-meta">${esc(skill.scope)} · Confirmed by Book ${skill.book ?? 1}, Ch. ${skill.chapter}${skill.detail ? ` · ${esc(skill.detail)}` : ""}</div></div>`).join("")}</div>` : '<div class="empty">No named skills revealed yet.</div>'}</div>
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
  $("#inventory-list").innerHTML = items.length ? items.map((item) => `<tr><td><div class="inventory-name">${esc(item.name)}${item.quantity ? ` ×${esc(item.quantity)}` : ""}</div>${item.detail ? `<div class="inventory-detail">${esc(item.detail)}</div>` : ""}</td><td>${esc(item.subject)}</td><td>${esc(item.category ?? "Item")}</td><td><span class="state-pill ${esc(item.state)}">${esc(item.state)}</span></td><td>B${esc(item.acquiredBook ?? item.book ?? 1)} · Ch. ${esc(item.acquiredChapter ?? item.chapter)}</td></tr>`).join("") : '<tr><td colspan="5"><div class="empty">No matching active inventory.</div></td></tr>';
}

function renderHistory(events) {
  const filters = ["All", "level", "skill", "item", "party", "stat", "story"];
  $("#history-filters").innerHTML = filters.map((filter) => `<button type="button" class="filter-button ${filter === state.historyFilter ? "active" : ""}" data-history-filter="${filter}">${filter}</button>`).join("");
  $("#history-filters").querySelectorAll("[data-history-filter]").forEach((button) => button.addEventListener("click", () => { state.historyFilter = button.dataset.historyFilter; renderHistory(events); }));
  const filtered = events.filter((event) => state.historyFilter === "All" || event.type === state.historyFilter);
  $("#history-count").textContent = `${events.length} events known`;
  $("#history-list").innerHTML = filtered.length ? filtered.map((event) => `<li class="history-event" style="--event-color:${EVENT_COLORS[event.type] ?? EVENT_COLORS.story}"><span class="history-location">Book ${event.book}<br>Chapter ${event.chapter} · ${Math.round((event.position ?? 0)*100)}%</span><i class="history-marker"></i><div class="history-copy"><strong>${esc(event.subject ?? "Story")} · ${esc(event.name ?? event.type)}</strong><span>${esc(event.summary ?? event.detail ?? "")}</span></div></li>`).join("") : '<li class="empty">No events in this category yet.</li>';
}

function renderAll() {
  const allEvents = visibleEvents();
  renderCast(allEvents);
  const events = followedEvents(allEvents);
  const party = partyAt(events);
  renderPosition();
  renderChart(events);
  renderCharacters(events, party);
  renderInventory(events);
  renderHistory(events);
  renderExplorer();
  renderRewards(events);
  const url = new URL(window.location);
  ["book", "chapter", "position"].forEach(key => url.searchParams.delete(key));
  url.searchParams.delete("progress");
  if (state.progress > 0) url.searchParams.set("progress", Math.round(state.progress * 10000));
  history.replaceState(null, "", url);
}

async function start() {
  const response = await fetch("data/series.json?v=2.6.0", { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load dataset (${response.status})`);
  state.data = normalizeData(await response.json());
  state.data.characters ??= [];
  const facts = await fetch("data/progression.json", { cache: "no-store" });
  if (!facts.ok) throw new Error("Could not load progression archive");
  state.facts = await facts.json();
  try {
    const saved = JSON.parse(localStorage.getItem('crawl-atlas-cast'));
    if (saved === null || (Array.isArray(saved) && saved.every(name => typeof name === 'string'))) state.followedCharacters = saved;
  } catch {}
  const params = new URLSearchParams(window.location.search);
  if (params.has("progress") && Number.isFinite(Number(params.get("progress")))) state.progress = Math.min(1, Math.max(0, Number(params.get("progress")) / 10000));
  else if (params.has("chapter")) state.progress = progressFor(Number(params.get("book")) || 1, Number(params.get("chapter")) || 1, (Number(params.get("position")) || 0) / 100);
  $("#book-title").textContent = `${state.data.series.title} · ${state.data.series.bookCount} books`;
  $("#data-version").textContent = state.data.series.dataVersion;
  $("#last-chapter-label").textContent = `Book ${state.data.books.at(-1).number} · Chapter ${state.data.books.at(-1).chapterCount}`;
  renderAll();
  const view = params.get("view");
  if (["explorer", "progression", "character", "ledger", "history", "rewards"].includes(view)) document.querySelector(`[data-view="${view}"]`).click();
}

$('#cast-all').addEventListener('click', () => saveCast(null));
$("#chart-character").addEventListener("change", () => renderChart(followedEvents()));
$('#cast-none').addEventListener('click', () => saveCast([]));
$('#cast-core').addEventListener('click', () => {
  const known = new Set(visibleEvents().map(event => event.subject));
  saveCast(state.data.characters.filter(character => character.group === 'core' && known.has(character.name)).map(character => character.name));
});
$("#book-range").addEventListener("input", (event) => { state.progress = Number(event.target.value) / 10000; renderAll(); });
$("#book-select").addEventListener("change", (event) => { state.progress = progressFor(event.target.value, 1); renderAll(); });
$("#chapter-select").addEventListener("change", (event) => { state.progress = progressFor($("#book-select").value, event.target.value); renderAll(); });
$("#previous-chapter").addEventListener("click", () => { const { globalChapter } = currentLocation(); state.progress = Math.max(0, (globalChapter - 2) / state.data.series.chapterCount); renderAll(); });
$("#next-chapter").addEventListener("click", () => { const { globalChapter } = currentLocation(); state.progress = Math.min(1, globalChapter / state.data.series.chapterCount); renderAll(); });
$("#inventory-search").addEventListener("input", (event) => { state.inventorySearch = event.target.value; renderInventory(followedEvents()); });
$("#about-button").addEventListener("click", () => { $("#about-panel").hidden = false; $("#about-button").setAttribute("aria-expanded", "true"); $("#about-close").focus(); });
$("#about-close").addEventListener("click", () => { $("#about-panel").hidden = true; $("#about-button").setAttribute("aria-expanded", "false"); $("#about-button").focus(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !$("#about-panel").hidden) $("#about-close").click(); });

start().catch((error) => { document.querySelector("main").innerHTML = `<section class="empty"><h1>Dataset unavailable</h1><p>${esc(error.message)}</p></section>`; });
