// A GitHub Pages export has no query server. Use rows rendered by dct at build
// time, mounting only the records visible at the current reading position.
// One character is selected for every dossier table. Keep its identity in the
// dossier header, not in a repeated table column. Used by the native row build too.
function dossierRecord(name, row) {
  const redundant = {inventory:'owner', rewards:'recipient', story:'who'}[name];
  return Object.fromEntries(Object.entries(row).filter(([key]) => key !== redundant));
}
function dossierEvents(events, name) {
  return events.filter(event => event.subject === name ||
    (name === 'Princess Donut' && event.subject === 'Donut'));
}
// Inventory ownership alone does not establish that an item is being worn.
// Fleeting/temporary use is not a persistent equipment state.
function isRecordedEquipped(item) {
  const recorded = String(item.state ?? '').toLowerCase().trim();
  return item.action !== 'unequip' &&
    /^(equipped|worn|attached|installed)(?:$|[ ;])/.test(recorded) &&
    !/fleeting|temporary|no longer|removed|destroyed|stored/.test(recorded);
}
// Checkpoint lookup always uses the exact reader boundary, including rewinds.
function dossierChartAt(charts, name, cutoff) {
  return (charts?.characters?.[name] ?? []).findLast(row => row.progress <= cutoff);
}
function dossierChartMarkup(name) {
  if (!state.dossierCharts) return `<p class="detail-empty" role="status">${state.dossierChartsError ? 'Stat history could not be loaded. Reload to try again.' : 'Loading stat history…'}</p>`;
  const checkpoint = dossierChartAt(state.dossierCharts, name, state.progress);
  if (!checkpoint) return '<p class="detail-empty">No stat measurements recorded at this position.</p>';
  const compact = window.matchMedia('(max-width: 820px)').matches;
  return `<div class="dossier-stat-chart" role="group" aria-label="${esc(name)} stat progression">${compact ? checkpoint.compactSvg : checkpoint.svg}<div class="stat-chart-key" aria-label="Chart key"><span><i class="key-base"></i>Base</span><span><i class="key-total"></i>With modifiers</span><span><i class="key-estimate"></i>Estimate / minimum</span></div><p class="stat-chart-note" data-stat-note aria-live="polite"></p></div>`;
}
function skillHistoryMarkup(name) {
  if (state.skillChartsError) return '<p class="detail-empty">Skill history could not be loaded. Reload to try again.</p>';
  if (!state.skillCharts || state.skillCharts.version !== 2) return '<p class="detail-empty">Loading skill history…</p>';
  const checkpoint = dossierChartAt(state.skillCharts, name, state.progress);
  if (!checkpoint?.count) return '<p class="detail-empty">No skills with two recorded level changes or a recorded level above 5 at this position.</p>';
  const compact = window.matchMedia('(max-width: 820px)').matches;
  return `<section class="skill-history">${compact ? checkpoint.compactSvg : checkpoint.svg}
    <p class="skill-scope-key"><span><i class="scope-base"></i>Base</span><span><i class="scope-reported"></i>Reported</span><span><i class="scope-modified"></i>Equipment, granted, or effective</span></p>
    <p class="detail-caption">${checkpoint.count} skills with at least two recorded level changes or a latest level above 5. Lines connect levels of the same scope. The first point is the first recorded level, which may be later than acquisition.</p></section>`;
}
// Keep hover copy short. The complete source note remains available on
// click/focus, and as the point's accessible description.
function statTooltipSummary(description) {
  const match = description.match(/^(.+?)\s+(-?\d+(?:\.\d+)?)\s+\(([^)]+)\),\s+Book\s+(\d+),\s+Chapter\s+(\d+)/);
  if (!match) return ['Stat observation', 'Select for source details'];
  const [, stat, value, kind, book, chapter] = match;
  const estimate = kind.includes('estimate');
  const lowerBound = kind.includes('lower bound');
  const scope = kind === 'base' ? 'Base' : kind === 'total including modifiers' ? 'With modifiers' :
    kind === 'estimated base' ? 'Estimated base' : kind === 'estimated total' ? 'Estimated total' :
    lowerBound ? 'Base lower bound' : 'Estimate · scope unknown';
  return [`${stat} ${estimate ? '≈' : ''}${value}${lowerBound ? ' minimum' : ''}`, `${scope} · Book ${book}, Ch. ${chapter}`];
}
function initStatTooltip(details, frame) {
  const doc = details.ownerDocument;
  const tip = doc.createElement('div');
  tip.className = 'stat-point-tooltip';
  tip.id = 'stat-point-tooltip';
  tip.setAttribute('role', 'tooltip');
  tip.hidden = true;
  tip.innerHTML = '<strong></strong><span></span>';
  doc.body.append(tip);
  let active = null;
  const pointAt = target => target?.closest?.('.dossier-stat-chart circle[tabindex]');
  function hide() {
    if (active) active.removeAttribute('aria-describedby');
    active = null;
    tip.hidden = true;
  }
  function show(point, event) {
    if (!point?.dataset.statDescription) return;
    if (active && active !== point) active.removeAttribute('aria-describedby');
    active = point;
    const [value, location] = statTooltipSummary(point.dataset.statDescription);
    tip.querySelector('strong').textContent = value;
    tip.querySelector('span').textContent = location;
    tip.hidden = false;
    point.setAttribute('aria-describedby', tip.id);
    const box = point.getBoundingClientRect();
    const anchorX = event?.clientX ?? box.left + box.width / 2;
    const anchorY = event?.clientY ?? box.bottom;
    const outer = frame.getBoundingClientRect();
    // This iframe expands to document height. Clamp to its intersection with
    // the actual browser viewport, not its thousands-of-pixels innerHeight.
    const leftEdge = Math.max(8, -outer.left + 8);
    const rightEdge = Math.min(doc.documentElement.clientWidth - 8, window.innerWidth - outer.left - 8);
    const chromeBottom = Math.max(0, document.querySelector('.topbar')?.getBoundingClientRect().bottom ?? 0,
      document.querySelector('.reader-position')?.getBoundingClientRect().bottom ?? 0);
    const topEdge = Math.max(8, chromeBottom - outer.top + 8);
    const bottomEdge = Math.min(doc.documentElement.clientHeight - 8, window.innerHeight - outer.top - 8);
    tip.style.maxWidth = `${Math.max(120, Math.min(270, rightEdge - leftEdge))}px`;
    const width = tip.offsetWidth;
    const height = tip.offsetHeight;
    const x = Math.max(leftEdge, Math.min(anchorX + 12, rightEdge - width));
    const preferredY = anchorY + 12 + height <= bottomEdge ? anchorY + 12 : anchorY - height - 12;
    const y = Math.max(topEdge, Math.min(preferredY, bottomEdge - height));
    tip.style.left = `${x}px`;
    tip.style.top = `${y}px`;
  }
  details.addEventListener('pointerover', event => show(pointAt(event.target), event));
  details.addEventListener('pointermove', event => {
    const point = pointAt(event.target);
    if (point) show(point, event);
  });
  details.addEventListener('pointerout', event => {
    if (pointAt(event.target) && pointAt(event.relatedTarget) !== active) hide();
  });
  details.addEventListener('pointerleave', hide);
  details.addEventListener('focusin', event => show(pointAt(event.target)));
  details.addEventListener('focusout', event => { if (pointAt(event.target)) hide(); });
  details.addEventListener('keydown', event => { if (event.key === 'Escape') hide(); });
  const controller = new AbortController();
  window.addEventListener('scroll', hide, {passive:true, signal:controller.signal});
  window.addEventListener('resize', hide, {passive:true, signal:controller.signal});
  const escape = event => { if (event.key === 'Escape') hide(); };
  window.addEventListener('keydown', escape, {signal:controller.signal});
  doc.addEventListener('keydown', escape, {signal:controller.signal});
  doc.defaultView.addEventListener('pagehide', () => controller.abort(), {once:true});
  details.statTooltip = {hide};
}
function prepareStatPoints(details) {
  details.statTooltip?.hide();
  details.querySelectorAll('.dossier-stat-chart circle[tabindex]').forEach(point => {
    const title = point.querySelector('title');
    const description = title?.textContent ?? point.getAttribute('aria-label') ?? '';
    point.dataset.statDescription = description;
    point.setAttribute('aria-label', description);
    title?.remove();
  });
}
let dossierTab = 'overview';
function activateDossierTab(id) {
  const tab = id === 'character' ? 'overview' : id;
  if (!['overview','ledger','rewards','history'].includes(tab)) return;
  dossierTab = tab;
  const details = $('#reader-board').contentDocument?.querySelector('.reader-details');
  if (!details) return;
  details.statTooltip?.hide();
  details.querySelectorAll('[data-dossier-tab]').forEach(button => {
    const active = button.dataset.dossierTab === tab;
    button.setAttribute('aria-selected', String(active));
    button.tabIndex = active ? 0 : -1;
  });
  details.querySelectorAll('[data-dossier-panel]').forEach(panel => {
    panel.hidden = panel.dataset.dossierPanel !== tab;
  });
}
function detailTable(name, rows, notes = []) {
  if (!rows.length) return '<p class="detail-empty">No observations at this position.</p>';
  rows = rows.map(row => dossierRecord(name, row));
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
  if (!state.dossierCharts && !state.dossierChartsLoading) {
    state.dossierChartsLoading = true;
    fetch('data/dossier-charts.json').then(response => {
      if (!response.ok) throw new Error('Stat history unavailable');
      return response.json();
    }).then(data => { state.dossierCharts = data; updateBoardDetails(); })
      .catch(() => { state.dossierChartsError = true; updateBoardDetails(); });
  }
  if (!state.skillCharts && !state.skillChartsLoading) {
    state.skillChartsLoading = true;
    fetch('data/skill-charts.json').then(response => {
      if (!response.ok) throw new Error('Skill history unavailable');
      return response.json();
    }).then(data => { state.skillCharts = data; updateBoardDetails(); })
      .catch(() => { state.skillChartsError = true; updateBoardDetails(); });
  }
  let details = board.querySelector(".reader-details");
  if (!details) {
    const css = frame.contentDocument.createElement("link");
    css.rel = "stylesheet";
    css.href = new URL("detail-tables.css?v=3", document.baseURI).href;
    frame.contentDocument.head.append(css);
    details = frame.contentDocument.createElement("div");
    details.className = "reader-details";
    details.innerHTML = `<section id="character" class="character-dossier">
      <div class="dossier-heading"><h2>Character dossier</h2><label>Character<select data-field="person"></select></label></div>
      <div data-profile></div>
      <div class="dossier-tabs" role="tablist" aria-label="Character details">
        <button id="tab-overview" type="button" role="tab" data-dossier-tab="overview" aria-controls="dossier-overview">Overview</button>
        <button id="tab-ledger" type="button" role="tab" data-dossier-tab="ledger" aria-controls="ledger">Inventory</button>
        <button id="tab-rewards" type="button" role="tab" data-dossier-tab="rewards" aria-controls="rewards">Boxes &amp; rewards</button>
        <button id="tab-history" type="button" role="tab" data-dossier-tab="history" aria-controls="history">History</button>
      </div>
      <div id="dossier-overview" role="tabpanel" aria-labelledby="tab-overview" data-dossier-panel="overview" data-dossier></div>
      <div id="ledger" role="tabpanel" aria-labelledby="tab-ledger" data-dossier-panel="ledger" hidden>
        <div class="inventory-toolbar"><div class="inventory-views" role="group" aria-label="Inventory view">
          <button type="button" data-inventory-view="all" aria-pressed="true">All items</button>
          <button type="button" data-inventory-view="equipped" aria-pressed="false">Equipped</button>
        </div><label>Search items<input type="search" data-field="search"></label></div>
        <p class="inventory-coverage" data-inventory-coverage></p><div data-items></div><p data-note="inventory" aria-live="polite"></p>
      </div>
      <div id="rewards" role="tabpanel" aria-labelledby="tab-rewards" data-dossier-panel="rewards" hidden><div class="detail-controls">
        <label>Stage<select data-reward="stage"></select></label><label>Tier<select data-reward="tier"></select></label>
        <label>Box type<select data-reward="kind"></select></label><label>Search rewards<input type="search" data-reward="search"></label></div>
        <div data-reward-rows></div><p data-note="rewards" aria-live="polite"></p></div>
      <div id="history" role="tabpanel" aria-labelledby="tab-history" data-dossier-panel="history" hidden>
        <label>Event type<select data-event-type></select></label>
        <div data-story></div><p data-note="story" aria-live="polite"></p></div>
    </section>`;
    board.append(details);
    initStatTooltip(details, frame);
    details.querySelector('[role="tablist"]').addEventListener('click', e => {
      const button = e.target.closest('[data-dossier-tab]');
      if (button) activateDossierTab(button.dataset.dossierTab);
    });
    details.querySelector('[role="tablist"]').addEventListener('keydown', e => {
      const tabs = [...details.querySelectorAll('[data-dossier-tab]')];
      const index = tabs.indexOf(e.target);
      if (index < 0 || !['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) return;
      e.preventDefault();
      const next = e.key === 'Home' ? 0 : e.key === 'End' ? tabs.length - 1 :
        (index + (e.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      activateDossierTab(tabs[next].dataset.dossierTab);
      tabs[next].focus();
    });
    board.addEventListener('click', e=>{
      const button = e.target.closest('button[data-limit]');
      if (!button) return;
      tableLimits.set(button.dataset.table, Number(button.dataset.limit));
      updateBoardDetails();
    });
    details.querySelector('[data-field="person"]').onchange = e => {
      state.selectedCharacter = e.target.value;
      state.inventorySearch = '';
      state.rewardFilters = {stage:'',tier:'',kind:'',search:''};
      state.historyFilter = 'All';
      for (const key of ['stats','skills','history','inventory','rewards','story']) tableLimits.delete(key);
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
    details.querySelectorAll('[data-inventory-view]').forEach(button => {
      button.onclick = () => {
        state.inventoryView = button.dataset.inventoryView;
        tableLimits.delete('inventory');
        updateBoardDetails();
      };
    });
    details.querySelector('[data-field="search"]').oninput = e => { state.inventorySearch = e.target.value; tableLimits.delete('inventory'); updateBoardDetails(); };
    function showStatNote(target) {
      const point = target.closest('.dossier-stat-chart circle[tabindex]');
      if (!point) return;
      const note = details.querySelector('[data-stat-note]');
      if (note) note.textContent = point.dataset.statDescription ?? '';
    }
    details.addEventListener('click', e => {
      showStatNote(e.target);
      const row = e.target.closest('g[aria-label][tabindex]');
      if (row) {
        row.focus();
        const note = details.querySelector('[data-note="'+row.closest('svg').dataset.detailTable+'"]');
        if (note) note.textContent = row.getAttribute('aria-label');
      }
    });
    details.addEventListener('focusin', e => {
      showStatNote(e.target);
      if (e.target.matches('g[aria-label][tabindex]')) {
        const note = details.querySelector('[data-note="'+e.target.closest('svg').dataset.detailTable+'"]');
        if (note) note.textContent = e.target.getAttribute('aria-label');
      }
    });
  }
  const events = visibleEvents();
  const roster = partyAt(events);
  const allItems = inventoryAt(events);
  const characterNames = new Set(state.data.characters.map(c => c.name));
  const names = [...new Set([...roster.map(c=>c.name), ...events.map(e=>e.subject)])]
    .filter(name => name !== 'Party' && characterNames.has(name));
  if (!names.includes(state.selectedCharacter)) state.selectedCharacter = names.includes('Carl') ? 'Carl' : names[0] ?? null;
  const person = state.data.characters.find(c=>c.name === state.selectedCharacter);
  const select = details.querySelector('[data-field="person"]');
  select.innerHTML = optionList(names,state.selectedCharacter);
  select.disabled = !names.length;
  const dossier = details.querySelector('[data-dossier]');
  if (person) {
    const snapshot = characterState(person, events);
    const observed = snapshot.levelEvent;
    const profile = [snapshot.relationship, ...Object.values(snapshot.profile)].filter(Boolean).join(' · ');
    const statusLabels = {dead:'Confirmed dead', 'presumed-dead':'Presumed dead', alive:'Confirmed alive'};
    const statusEvent = snapshot.lifeStatusEvent;
    const status = statusEvent && statusLabels[snapshot.lifeStatus]
      ? `<p class="dossier-status" data-life-status="${esc(snapshot.lifeStatus)}"><span>${statusLabels[snapshot.lifeStatus]}</span> · Book ${statusEvent.book}, Chapter ${statusEvent.chapter}</p>` : '';
    details.querySelector('[data-profile]').innerHTML = `<div class="dossier-profile"><div><h3>${esc(person.name)}</h3><p>${esc(profile)}</p>${status}</div>
      <div class="dossier-level"><strong>${esc(snapshot.level ?? '—')}</strong><span>Last recorded level</span>${observed ?
      `<small>Book ${observed.book}, Chapter ${observed.chapter}</small>` : ''}</div></div>`;
    dossier.innerHTML = `${dossierChartMarkup(person.name)}${skillHistoryMarkup(person.name)}`;
  } else {
    const shared = state.selectedCharacter === 'Party';
    details.querySelector('[data-profile]').innerHTML = shared ? '<h3>Party</h3><p>Shared items, rewards, and events.</p>' : '';
    dossier.textContent = shared ? 'Choose Inventory, Boxes & rewards, or History to see shared party records.' : 'No selected characters at this position.';
  }
  prepareStatPoints(details);
  const mine = dossierEvents(events, state.selectedCharacter);
  details.querySelector('[data-field="search"]').value = state.inventorySearch;
  const query = state.inventorySearch.toLowerCase().trim();
  const ownedItems = allItems.filter(i => i.subject === state.selectedCharacter);
  const equippedCount = ownedItems.filter(isRecordedEquipped).length;
  const equippedOnly = state.inventoryView === 'equipped';
  details.querySelectorAll('[data-inventory-view]').forEach(button => {
    const equipped = button.dataset.inventoryView === 'equipped';
    button.setAttribute('aria-pressed', String(equipped === equippedOnly));
    button.textContent = `${equipped ? 'Equipped' : 'All items'} (${equipped ? equippedCount : ownedItems.length})`;
  });
  details.querySelector('[data-inventory-coverage]').textContent = equippedOnly
    ? 'Last recorded equipment; later swaps may be missing.' : '';
  const items = ownedItems.filter(i => (!equippedOnly || isRecordedEquipped(i)) &&
    [i.name,i.category,i.detail].join(' ').toLowerCase().includes(query))
    .sort((a,b) => b.acquiredProgress - a.acquiredProgress || a.name.localeCompare(b.name));
  details.querySelector('[data-items]').innerHTML = items.length ?
    detailTable('inventory', items.map(inventoryRecord), items.map(i=>[i.detail, `Last observed Book ${i.book ?? 1}, Chapter ${i.chapter}`, i.source, ...(i.statBoosts ?? []).map(b=>`Bonus source: ${b.source}`)].filter(Boolean).join(' · '))) : `<p>${equippedOnly ? 'No matching equipment recorded' : 'No matching items'} at this position.</p>`;
  const rewards = rewardRows(mine, visibleEvents());
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
  const entries = storyEntries(mine, state.facts, state.progress);
  const types = ['All', ...new Set(entries.map(entry => entry.type))];
  if (!types.includes(state.historyFilter)) state.historyFilter='All';
  details.querySelector('[data-event-type]').innerHTML = optionList(types,state.historyFilter);
  const history = entries.filter(entry => state.historyFilter === 'All' || entry.type === state.historyFilter);
  details.querySelector('[data-story]').innerHTML = detailTable('story', history.map(entry => entry.row), history.map(entry => entry.note));
  details.querySelectorAll('[data-note]').forEach(note=>note.textContent='');
  activateDossierTab(dossierTab);
}

if (typeof module !== 'undefined') module.exports = {dossierRecord, dossierEvents, dossierChartAt, isRecordedEquipped, statTooltipSummary};
