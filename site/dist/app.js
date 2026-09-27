const state = {
  data: null,
  chapter: 7,
  position: 50,
  inventoryFilter: "All",
};

const $ = (selector) => document.querySelector(selector);
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
}[character]));

function checkpointAt(chapter, position) {
  const location = chapter + position / 100;
  return [...state.data.checkpoints]
    .reverse()
    .find((checkpoint) => checkpoint.chapter + checkpoint.position <= location)
    ?? state.data.checkpoints[0];
}

function levelLabel(member) {
  if (member.levelLabel) return member.levelLabel;
  if (member.level === null) return "—";
  return String(member.level);
}

function confidenceLabel(value) {
  return value === "needs-review" ? "Needs review" : value[0].toUpperCase() + value.slice(1);
}

function renderParty(checkpoint) {
  $("#party-name").textContent = checkpoint.partyName;
  $("#party-count").textContent = `${checkpoint.party.length} ${checkpoint.party.length === 1 ? "member" : "members"}`;
  $("#party-list").innerHTML = checkpoint.party.map((member) => `
    <section class="member-card">
      <div class="member-top">
        <div><h4 class="member-name">${escapeHtml(member.name)}</h4><div class="member-role">${escapeHtml(member.role)}</div></div>
        <div class="level-box"><small>LVL</small>${escapeHtml(levelLabel(member))}</div>
      </div>
      ${member.stats?.length ? `<div class="stats">${member.stats.map((stat) => `<div class="stat"><span>${escapeHtml(stat.name)}</span>${escapeHtml(stat.value)}</div>`).join("")}</div>` : ""}
      <span class="confidence ${escapeHtml(member.confidence)}">${escapeHtml(confidenceLabel(member.confidence))}</span>
    </section>
  `).join("");
}

function renderInventory(checkpoint) {
  const owners = ["All", ...new Set(checkpoint.inventory.map((item) => item.owner))];
  if (!owners.includes(state.inventoryFilter)) state.inventoryFilter = "All";
  $("#inventory-filters").innerHTML = owners.map((owner) => `<button type="button" class="filter-button ${owner === state.inventoryFilter ? "active" : ""}" data-owner="${escapeHtml(owner)}">${escapeHtml(owner)}</button>`).join("");
  const items = checkpoint.inventory.filter((item) => state.inventoryFilter === "All" || item.owner === state.inventoryFilter);
  $("#inventory-count").textContent = `${checkpoint.inventory.length} tracked`;
  $("#inventory-list").innerHTML = items.length ? items.map((item) => `
    <div class="inventory-row">
      <div><div class="item-name">${escapeHtml(item.name)}</div>${item.detail ? `<div class="item-detail">${escapeHtml(item.detail)}</div>` : ""}<span class="confidence ${escapeHtml(item.confidence)}">${escapeHtml(confidenceLabel(item.confidence))}</span></div>
      <div class="item-meta">${escapeHtml(item.owner)}<br>${escapeHtml(item.kind)}</div>
    </div>
  `).join("") : `<div class="empty">No tracked items for this filter.</div>`;
  document.querySelectorAll("[data-owner]").forEach((button) => button.addEventListener("click", () => {
    state.inventoryFilter = button.dataset.owner;
    renderInventory(checkpoint);
  }));
}

function renderSkills(checkpoint) {
  $("#skills-count").textContent = `${checkpoint.skills.length} tracked`;
  $("#skill-list").innerHTML = checkpoint.skills.length ? checkpoint.skills.map((skill) => `
    <div class="skill-row">
      <div><div class="item-name">${escapeHtml(skill.name)}</div><span class="confidence ${escapeHtml(skill.confidence)}">${escapeHtml(confidenceLabel(skill.confidence))}</span></div>
      <div class="item-meta">${escapeHtml(skill.owner)}${skill.level !== null ? `<br><span class="skill-level">Level ${escapeHtml(skill.level)}</span>` : ""}</div>
    </div>
  `).join("") : `<div class="empty">No skills revealed yet.</div>`;
}

function renderTimeline() {
  const checkpoints = new Set(state.data.checkpoints.map((checkpoint) => checkpoint.chapter));
  const fill = `${state.position}%`;
  $("#timeline").innerHTML = Array.from({ length: state.data.book.chapterCount }, (_, index) => {
    const chapter = index + 1;
    const status = chapter < state.chapter ? "past" : chapter === state.chapter ? "current" : "future";
    return `<span class="timeline-segment ${status} ${checkpoints.has(chapter) ? "checkpoint" : ""}" style="--fill:${fill}" title="Chapter ${chapter}"></span>`;
  }).join("");
}

function renderSnapshot() {
  const checkpoint = checkpointAt(state.chapter, state.position);
  state.inventoryFilter = "All";
  $("#snapshot-kicker").textContent = `Chapter ${checkpoint.chapter} · ${Math.round(checkpoint.position * 100)}% checkpoint`;
  $("#snapshot-title").textContent = checkpoint.label;
  $("#snapshot-note").textContent = checkpoint.note;
  $("#coverage-badge").textContent = `${checkpoint.coverage} coverage`;
  $("#coverage-badge").className = `coverage-badge ${checkpoint.coverage}`;
  $("#change-list").innerHTML = checkpoint.changes.map((change) => `<li>${escapeHtml(change)}</li>`).join("");
  $("#source-anchor").textContent = `Private source anchor: ${checkpoint.source} · Showing latest checkpoint before Ch. ${state.chapter}, ${state.position}%`;
  renderParty(checkpoint);
  renderInventory(checkpoint);
  renderSkills(checkpoint);
  renderTimeline();
  const url = new URL(window.location);
  url.searchParams.set("chapter", state.chapter);
  url.searchParams.set("position", state.position);
  history.replaceState(null, "", url);
}

async function start() {
  const response = await fetch("data/book-1.json");
  if (!response.ok) throw new Error(`Could not load dataset (${response.status})`);
  state.data = await response.json();
  const params = new URLSearchParams(window.location.search);
  state.chapter = Math.min(state.data.book.chapterCount, Math.max(1, Number(params.get("chapter")) || 7));
  state.position = Math.min(100, Math.max(0, Number(params.get("position")) || 50));
  $("#book-title").textContent = `${state.data.book.title} · ${state.data.book.subtitle}`;
  $("#data-version").textContent = state.data.book.dataVersion;
  $("#chapter-select").innerHTML = Array.from({ length: state.data.book.chapterCount }, (_, index) => `<option value="${index + 1}">Chapter ${index + 1}</option>`).join("");
  $("#chapter-select").value = state.chapter;
  $("#position-range").value = state.position;
  $("#position-output").textContent = `${state.position}%`;
  renderSnapshot();
}

$("#position-range").addEventListener("input", (event) => {
  state.position = Number(event.target.value);
  $("#position-output").textContent = `${state.position}%`;
});
$("#chapter-select").addEventListener("change", (event) => { state.chapter = Number(event.target.value); });
$("#locate-button").addEventListener("click", renderSnapshot);
$("#about-button").addEventListener("click", () => {
  $("#about-panel").hidden = false;
  $("#about-button").setAttribute("aria-expanded", "true");
  $("#about-close").focus();
});
$("#about-close").addEventListener("click", () => {
  $("#about-panel").hidden = true;
  $("#about-button").setAttribute("aria-expanded", "false");
  $("#about-button").focus();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("#about-panel").hidden) $("#about-close").click();
});

start().catch((error) => {
  $("#snapshot-title").textContent = "Dataset unavailable";
  $("#snapshot-note").textContent = error.message;
});

