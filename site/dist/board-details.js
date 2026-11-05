// A GitHub Pages export has no query server. Use rows rendered by dct at build
// time, mounting only the records visible at the current reading position.
function detailTable(name, rows, notes = []) {
  if (!rows.length) return '<p class="detail-empty">No observations at this position.</p>';
  const model = state.detailTables[name];
  const groups = rows.map((row, i) => {
    const [baseline, svg] = model.rows[JSON.stringify(row)];
    const text = [...Object.values(row), notes[i]].filter(Boolean).join(' · ');
    return `<g transform="translate(0,${66 + 24*i - baseline})" tabindex="0" aria-label="${esc(text)}"><title>${esc(text)}</title>${svg}</g>`;
  }).join('');
  return `<div class="detail-table-scroll"><svg data-chart-type="table" data-detail-table="${name}" role="group" aria-label="${name}" viewBox="0 0 ${model.width} ${78 + 24*(rows.length-1)}">${model.header}<g transform="translate(16,0)">${groups}</g></svg></div>`;
}
function optionList(values, current) {
  return values.map(v => `<option${v===current?' selected':''}>${esc(v)}</option>`).join('');
}
function updateBoardDetails() {
  const frame = $("#reader-board");
  if (frame.hidden || frame.hasAttribute("aria-busy")) return;
  const board = frame.contentDocument?.querySelector(".dbt-charts-board");
  if (!board) return;
  let details = board.querySelector(".reader-details");
  if (!details) {
    const css = frame.contentDocument.createElement("link");
    css.rel = "stylesheet";
    css.href = new URL("detail-tables.css", document.baseURI).href;
    frame.contentDocument.head.append(css);
    details = frame.contentDocument.createElement("div");
    details.className = "reader-details";
    details.innerHTML = `<section id="character"><h2>Party &amp; allies</h2><label>Character <select data-field="person"></select></label><div data-dossier></div></section>
      <section id="ledger"><h2>Inventory</h2><div class="detail-controls"><label>Owner <select data-field="owner"></select></label>
      <label>Search items <input type="search" data-field="search"></label></div><div data-items></div></section>`;
    board.append(details);
    details.querySelector('[data-field="person"]').onchange = e => { state.selectedCharacter = e.target.value; updateBoardDetails(); };
    details.querySelector('[data-field="owner"]').onchange = e => { state.inventoryOwner = e.target.value; updateBoardDetails(); };
    details.querySelector('[data-field="search"]').oninput = e => { state.inventorySearch = e.target.value; updateBoardDetails(); };
    details.addEventListener('click', e => {
      const row = e.target.closest('g[aria-label][tabindex]');
      if (row) {
        row.focus();
        const note = details.querySelector('[data-note="'+row.closest('svg').dataset.detailTable+'"]');
        if (note) note.textContent = row.getAttribute('aria-label');
      }
    });
    details.addEventListener('focusin', e => {
      if (e.target.matches('g[aria-label][tabindex]')) {
        const note = details.querySelector('[data-note="'+e.target.closest('svg').dataset.detailTable+'"]');
        if (note) note.textContent = e.target.getAttribute('aria-label');
      }
    });
  }
  const events = followedEvents();
  const roster = partyAt(events);
  const person = roster.find(c => c.name === state.selectedCharacter) ?? roster[0];
  state.selectedCharacter = person?.name ?? null;
  const select = details.querySelector('[data-field="person"]');
  select.innerHTML = optionList(roster.map(c=>c.name), state.selectedCharacter);
  select.disabled = !person;
  const dossier = details.querySelector('[data-dossier]');
  if (person) {
    const snapshot = characterState(person, events);
    const tables = dossierTables(snapshot);
    const observed = snapshot.levelEvent;
    const profile = [snapshot.relationship, ...Object.values(snapshot.profile)].filter(Boolean).join(' · ');
    dossier.innerHTML = `<h3>${esc(person.name)}</h3><p>${esc(profile)}</p><p>${observed ?
      `Level ${esc(snapshot.level ?? 'unknown')} · Observed in Book ${observed.book}, Chapter ${observed.chapter}` : 'Level unknown'}</p>
      <div class="detail-columns"><div><h4>Base and reported stats</h4>${detailTable('stats', tables.stats)}
      <h4>Level history</h4>${detailTable('history', tables.history.toReversed())}</div><div><h4>Skills &amp; spells</h4>
      ${detailTable('skills', tables.skills, snapshot.skills.map(s=>s.detail))}<p data-note="skills" aria-live="polite"></p></div></div>`;
  } else dossier.textContent = 'No selected party members at this position.';
  const all = inventoryAt(events);
  const owners = ['All', ...new Set(all.map(i=>i.subject))];
  if (!owners.includes(state.inventoryOwner)) state.inventoryOwner = 'All';
  details.querySelector('[data-field="owner"]').innerHTML = optionList(owners,state.inventoryOwner);
  details.querySelector('[data-field="search"]').value = state.inventorySearch;
  const query = state.inventorySearch.toLowerCase().trim();
  const items = all.filter(i => (state.inventoryOwner==='All' || state.inventoryOwner===i.subject) &&
    [i.name,i.category,i.detail].join(' ').toLowerCase().includes(query));
  details.querySelector('[data-items]').innerHTML = items.length ?
    detailTable('inventory', items.map(inventoryRecord), items.map(i=>i.detail)) + '<p data-note="inventory" aria-live="polite"></p>' : '<p>No matching items at this position.</p>';
}
