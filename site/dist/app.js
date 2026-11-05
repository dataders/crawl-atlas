const SERIES = { Carl: "#d8ff3e", "Princess Donut": "#4dd9d2", Donut: "#4dd9d2", Mongo: "#ff6441" };
const EVENT_COLORS = { level: "#d8ff3e", skill: "#4dd9d2", item: "#ff6441", party: "#ad8cff", stat: "#f5ca5c", story: "#8e9ba5" };
const state = { data: null, progress: 0, chartMetric: "level", selectedCharacter: null, rosterFilter: "All", rewardFilters: {stage:"",tier:"",kind:"",search:""}, inventorySearch: "", historyFilter: "All", followedCharacters: null };
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

function visibleEvents() { return state.data.events.filter((event) => event.progress <= state.progress); }

function followedEvents(events = visibleEvents()) {
  return state.followedCharacters === null ? events : events.filter(event => state.followedCharacters.includes(event.subject));
}
function renderCast(events) {
  const names = new Set(events.map(event => event.subject));
  const known = state.data.characters.filter(character => names.has(character.name));
  $('#cast-options').innerHTML = known.map(character => `<label class="cast-chip"><input type="checkbox" value="${esc(character.name)}" ${state.followedCharacters === null || state.followedCharacters.includes(character.name) ? 'checked' : ''}><span style="--person-color:${character.color}">${esc(character.name)}</span></label>`).join('') || '<span class="empty">Character choices appear as you meet them.</span>';
  const selected = known.filter(character => state.followedCharacters === null || state.followedCharacters.includes(character.name));
  $('#cast-status').textContent = `${selected.length} of ${known.length} known characters selected · Applies to character details, inventory, rewards and history. Saved on this device.`;
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

function renderPosition() {
  const location = currentLocation();
  const bookPercent = Math.round(100 * (location.chapter - 1 + location.position) / location.book.chapterCount);
  $("#location-chapter").textContent = `Book ${location.book.number} · Chapter ${location.chapter}`;
  $("#book-range").setAttribute("aria-valuetext", `Book ${location.book.number}, chapter ${location.chapter}, ${bookPercent} percent through book`);
  $("#location-percent").textContent = `${bookPercent}% through book`;
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

function renderChart() {
  const checkpoint = state.facts.findLast(row => row.progress <= state.progress);
  const frame = $("#reader-board");
  $("#chart-empty").hidden = Boolean(checkpoint);
  const hasDetails = !checkpoint && state.data.events.some(e => e.progress <= state.progress);
  frame.hidden = !checkpoint && !hasDetails;
  if (frame.hidden) {
    frame.removeAttribute("src");
    return;
  }
  const layout = window.matchMedia("(max-width: 820px)").matches ? "compact/" : "";
  const book = currentLocation().book.number;
  const id = checkpoint && book > checkpoint.book ? `book-start-${book}` : checkpoint?.event_id;
  const path = id ? `charts/${layout}${encodeURIComponent(id)}.html` : "charts/details-only.html";
  if (frame.getAttribute("src") !== path) {
    frame.setAttribute("aria-busy", "true");
    frame.setAttribute("src", path);
  }
}

function renderAll() {
  const allEvents = visibleEvents();
  renderCast(allEvents);
  renderPosition();
  renderChart();
  updateBoardDetails();
  const url = new URL(window.location);
  ["book", "chapter", "position"].forEach(key => url.searchParams.delete(key));
  url.searchParams.delete("progress");
  url.searchParams.set("progress", Math.round(state.progress * 10000));
  history.replaceState(null, "", url);
}

async function start() {
  const response = await fetch("data/series.json?v=2.7.0", { cache: "no-store" });
  if (!response.ok) throw new Error(`Could not load dataset (${response.status})`);
  state.data = normalizeData(await response.json());
  state.data.characters ??= [];
  const facts = await fetch("data/progression.json", { cache: "no-store" });
  if (!facts.ok) throw new Error("Could not load progression archive");
  state.facts = await facts.json();
  const tables = await fetch("data/detail-tables.json?v=3");
  if (!tables.ok) throw new Error("Could not load detail tables");
  state.detailTables = await tables.json();
  try {
    const saved = JSON.parse(localStorage.getItem('crawl-atlas-cast'));
    if (saved === null || (Array.isArray(saved) && saved.every(name => typeof name === 'string'))) state.followedCharacters = saved;
  } catch {}
  const params = new URLSearchParams(window.location.search);
  const hasProgress = params.has("progress") && params.get("progress").trim() !== "" && Number.isFinite(Number(params.get("progress")));
  const hasChapter = Number.isInteger(Number(params.get("chapter"))) && Number(params.get("chapter")) >= 1;
  if (hasProgress) state.progress = Math.min(1, Math.max(0, Number(params.get("progress")) / 10000));
  else if (hasChapter) state.progress = progressFor(Number(params.get("book")) || 1, Number(params.get("chapter")) || 1, (Number(params.get("position")) || 0) / 100);
  $("#book-title").textContent = `${state.data.series.title} · ${state.data.series.bookCount} books`;
  $("#data-version").textContent = state.data.series.dataVersion;
  $("#last-chapter-label").textContent = `Book ${state.data.books.at(-1).number} · Chapter ${state.data.books.at(-1).chapterCount}`;
  document.body.classList.toggle("choosing-position", !hasProgress && !hasChapter);
  document.body.classList.remove("reader-loading");
  $("#book-range").disabled = false;
  if (!hasProgress && !hasChapter) {
    renderPosition();
    $("#enter-reader").disabled = false;
    return;
  }
  renderAll();
  const section = location.hash.slice(1) || params.get("view");
  if (boardSections[section]) jumpToBoard(section);
  else if (section && document.querySelector(`[data-view="${CSS.escape(section)}"]`)) document.getElementById(section).scrollIntoView();
}

const boardSections = {explorer:"history", character:"character", ledger:"ledger", rewards:"rewards", history:"history"};
let pendingSection = null;
function jumpToBoard(id) {
  const frame = $("#reader-board");
  if (frame.hidden) {
    $("#progression").scrollIntoView();
    return;
  }
  const table = frame.contentDocument?.getElementById(boardSections[id]);
  if (!table) {
    pendingSection = id;
    return;
  }
  pendingSection = null;
  const top = frame.getBoundingClientRect().top + table.getBoundingClientRect().top;
  const stickyHeight = $(".topbar").offsetHeight + $(".reader-position").offsetHeight;
  window.scrollBy(0, top - stickyHeight - 8);
}
window.addEventListener("hashchange", () => {
  if (boardSections[location.hash.slice(1)]) jumpToBoard(location.hash.slice(1));
});
$("#section-jump").addEventListener("change", event => {
  const id = event.target.value;
  if (id) {
    location.hash = id;
    if (boardSections[id]) jumpToBoard(id);
    else document.getElementById(id).scrollIntoView();
  }
  event.target.value = "";
});
document.querySelector('a[href="#history"]').addEventListener("click", () => {
  if (boardSections[location.hash.slice(1)]) jumpToBoard(location.hash.slice(1));
});
new ResizeObserver(() => {
  document.documentElement.style.setProperty("--header-height", $(".topbar").offsetHeight + "px");
}).observe($(".topbar"));

$('#cast-all').addEventListener('click', () => saveCast(null));
window.matchMedia("(max-width: 820px)").addEventListener("change", () => {
  if (state.facts && !document.body.classList.contains("choosing-position")) renderChart();
});
$("#reader-board").addEventListener("load", event => {
  const frame = event.target;
  const body = frame.contentDocument?.body;
  if (!body || !frame.hasAttribute("src")) return;
  if (frame.contentDocument.URL !== frame.src) return;
  frame.removeAttribute("aria-busy");
  updateBoardDetails();
  const resize = () => { frame.style.height = Math.ceil(body.getBoundingClientRect().height) + "px"; };
  new ResizeObserver(resize).observe(body);
  resize();
  if (pendingSection) jumpToBoard(pendingSection);
});
$('#cast-none').addEventListener('click', () => saveCast([]));
$('#cast-core').addEventListener('click', () => {
  const known = new Set(visibleEvents().map(event => event.subject));
  saveCast(state.data.characters.filter(character => character.group === 'core' && known.has(character.name)).map(character => character.name));
});
$("#book-range").addEventListener("input", (event) => {
  state.progress = Number(event.target.value) / 10000;
  if (document.body.classList.contains("choosing-position")) renderPosition();
  else renderAll();
});
$("#enter-reader").addEventListener("click", () => {
  const url = new URL(window.location.href);
  url.searchParams.set("progress", $("#book-range").value);
  window.location.assign(url.href);
});
$("#book-select").addEventListener("change", (event) => { state.progress = progressFor(event.target.value, 1); renderAll(); });
$("#chapter-select").addEventListener("change", (event) => { state.progress = progressFor($("#book-select").value, event.target.value); renderAll(); });
$("#previous-chapter").addEventListener("click", () => { const { globalChapter } = currentLocation(); state.progress = Math.max(0, (globalChapter - 2) / state.data.series.chapterCount); renderAll(); });
$("#next-chapter").addEventListener("click", () => { const { globalChapter } = currentLocation(); state.progress = Math.min(1, globalChapter / state.data.series.chapterCount); renderAll(); });
$("#about-button").addEventListener("click", () => { $("#about-panel").hidden = false; $("#about-button").setAttribute("aria-expanded", "true"); $("#about-close").focus(); });
$("#about-close").addEventListener("click", () => { $("#about-panel").hidden = true; $("#about-button").setAttribute("aria-expanded", "false"); $("#about-button").focus(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !$("#about-panel").hidden) $("#about-close").click(); });

start().catch((error) => { document.body.classList.remove("reader-loading", "choosing-position"); document.querySelector("main").innerHTML = `<section class="empty"><h1>Dataset unavailable</h1><p>${esc(error.message)}</p></section>`; });
