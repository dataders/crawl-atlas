// A GitHub Pages export has no query server. Use rows rendered by dct at build
// time, mounting only the records visible at the current reading position.
function detailTable(name, rows, notes = []) {
  if (!rows.length) return '<p class="detail-empty">No observations at this position.</p>';
  const model = state.detailTables[name];
  const shown = rows.slice(0, shownCount(name,rows.length));
  let cursor = 66;
  const groups = shown.map((row, i) => {
    const [baseline, svg, height] = model.rows[JSON.stringify(row)];
    const text = [...Object.values(row), notes[i]].filter(Boolean).join(' · ');
    const offset = cursor - baseline;
    cursor += height;
    return `<g transform="translate(0,${offset})" tabindex="0" aria-label="${esc(text)}"><title>${esc(text)}</title>${svg}</g>`;
  }).join('');
  return `<div class="detail-table-scroll"><svg data-chart-type="table" data-detail-table="${name}" role="group" aria-label="${name}" viewBox="0 0 ${model.width} ${cursor - 12}">${model.header}<g transform="translate(16,0)">${groups}</g></svg></div>${tableControls(name,rows.length)}`;
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
      <section id="rewards"><h2>Boxes &amp; rewards</h2><div class="detail-controls">
        <label>Stage<select data-reward="stage"></select></label><label>Tier<select data-reward="tier"></select></label>
        <label>Box type<select data-reward="kind"></select></label><label>Search rewards<input type="search" data-reward="search"></label></div>
        <div data-reward-rows></div><p data-note="rewards" aria-live="polite"></p></section>
      <section id="history"><h2>Story history</h2><label>Event type<select data-event-type></select></label>
        <div data-story></div><p data-note="story" aria-live="polite"></p></section>`;
    const inventory = details.ownerDocument.createElement('div');
    inventory.id = 'ledger';
    inventory.innerHTML = '<h4>Inventory</h4><label>Search items <input type="search" data-field="search"></label><div data-items></div><p data-note="inventory" aria-live="polite"></p>';
    details.querySelector('#character').append(inventory);
    board.append(details);
    const layoutNativeTables = installTableLimits(board);
    board.addEventListener('click', e=>{
      const button = e.target.closest('button[data-limit]');
      if (!button) return;
      tableLimits.set(button.dataset.table, Number(button.dataset.limit));
      if (['ledger','levels'].includes(button.dataset.table)) layoutNativeTables();
      else updateBoardDetails();
    });
    details.querySelector('[data-field="person"]').onchange = e => {
      state.selectedCharacter = e.target.value;
      state.inventorySearch = '';
      for (const key of ['stats','skills','history','inventory']) tableLimits.delete(key);
      updateBoardDetails();
    };
    for (const input of details.querySelectorAll('[data-reward]')) {
      input.addEventListener(input.type==='search'?'input':'change', () => {
        state.rewardFilters[input.dataset.reward] = input.value;
        tableLimits.delete('rewards'); updateBoardDetails();
      });
    }
    details.querySelector('[data-event-type]').onchange = e=>{
      state.historyFilter=e.target.value; tableLimits.delete('story'); updateBoardDetails();
    };
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
  const allItems = inventoryAt(events);
  const names = [...new Set([...roster.map(c=>c.name), ...allItems.map(i=>i.subject)])];
  if (!names.includes(state.selectedCharacter)) state.selectedCharacter = names[0] ?? null;
  const person = state.data.characters.find(c=>c.name === state.selectedCharacter);
  const select = details.querySelector('[data-field="person"]');
  select.innerHTML = optionList(names,state.selectedCharacter);
  select.disabled = !names.length;
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
  } else dossier.textContent = state.selectedCharacter === 'Party' ? 'Shared party inventory' : 'No selected characters at this position.';
  details.querySelector('[data-field="search"]').value = state.inventorySearch;
  const query = state.inventorySearch.toLowerCase().trim();
  const items = allItems.filter(i => i.subject === state.selectedCharacter &&
    [i.name,i.category,i.detail].join(' ').toLowerCase().includes(query))
    .sort((a,b) => b.acquiredProgress - a.acquiredProgress || a.name.localeCompare(b.name));
  details.querySelector('[data-items]').innerHTML = items.length ?
    detailTable('inventory', items.map(inventoryRecord), items.map(i=>i.detail)) : '<p>No matching items at this position.</p>';
  const rewards = rewardRows(events, visibleEvents());
  const filters = state.rewardFilters;
  for (const field of ['stage','tier','kind']) {
    const choices = [...new Set(rewards.map(r=>field==='stage' ? r.event.acquisition.stage : r[field]).filter(Boolean))].sort();
    if (!choices.includes(filters[field])) filters[field] = '';
    const select = details.querySelector(`[data-reward="${field}"]`);
    select.innerHTML = '<option value="">All</option>'+optionList(choices,filters[field]);
  }
  details.querySelector('[data-reward="search"]').value = filters.search;
  const matches = rewards.filter(r=>rewardMatches(r,filters)).reverse();
  const notes = matches.map(({event,parents}) => [
    event.acquisition.quantity != null ? `Quantity ${event.acquisition.quantity}` : '',
    parents.map(p=>p.name).join(' → ') || event.acquisition.reasonDetail,
    event.acquisition.attribution==='batch' ? 'Batch attribution · specific box unknown' : '',
    event.summary, event.acquisition.occurrenceDetail, event.source,
    ...parents.map(p=>`${p.name} · B${p.book} Ch ${p.chapter} · ${p.source}`)
  ].filter(Boolean).join(' · '));
  details.querySelector('[data-reward-rows]').innerHTML = detailTable('rewards', matches.map(rewardRecord), notes);
  const types = ['All', ...new Set(events.map(e=>e.type))];
  if (!types.includes(state.historyFilter)) state.historyFilter='All';
  details.querySelector('[data-event-type]').innerHTML = optionList(types,state.historyFilter);
  const history = events.filter(e=>state.historyFilter==='All'||e.type===state.historyFilter).reverse();
  details.querySelector('[data-story]').innerHTML = detailTable('story', history.map(storyRecord), history.map(e=>e.summary??e.detail));
  details.querySelectorAll('[data-note]').forEach(note=>note.textContent='');
}
