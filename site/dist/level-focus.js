// Keep the reader's selection as the slider swaps in a new dbt Charts export.
(() => {
  const leads = new Set(['Carl', 'Princess Donut']);
  const frame = document.getElementById('reader-board');
  let selected = null;

  frame.addEventListener('load', () => {
    const doc = frame.contentDocument;
    const chart = doc?.getElementById('chart-Level');
    if (!chart) {
      selected = null;
      return;
    }
    const entries = [...chart.querySelectorAll('.role-legend-label[data-dbt-series]')];
    if (!entries.some(entry => entry.dataset.dbtSeries === selected)) selected = null;

    // The export draws two point layers and an outline beneath each line.
    const lines = new Map();
    for (const path of chart.querySelectorAll('.mark-line path[data-dbt-series]')) {
      lines.set(path.getAttribute('d'), path.dataset.dbtSeries);
    }
    const marks = [];
    for (const mark of chart.querySelectorAll('.mark-line path, circle[data-dct-role="point"]')) {
      const series = mark.dataset.dbtSeries || lines.get(mark.getAttribute('d')) ||
        mark.getAttribute('aria-label')?.match(/; ⁢([^;]+)/)?.[1];
      if (series) marks.push({mark, series});
    }

    const controls = [];
    function paint() {
      for (const {mark, series} of marks) {
        const bright = selected ? series === selected : leads.has(series);
        mark.classList.toggle('level-muted', !bright);
      }
      for (const {entry, hit, name} of controls) {
        entry.classList.toggle('level-prominent', selected ? name === selected : leads.has(name));
        hit.setAttribute('aria-pressed', String(selected === name));
      }
    }

    for (const entry of entries) {
      const name = entry.dataset.dbtSeries;
      const label = entry.getBBox();
      const symbol = entry.previousElementSibling.getBBox();
      const hit = doc.createElementNS('http://www.w3.org/2000/svg', 'rect');
      const left = Math.min(symbol.x, label.x) - 2;
      for (const [key, value] of Object.entries({
        x:left, y:label.y - 3, width:label.x + label.width + 3 - left,
        height:label.height + 6, fill:'transparent', tabindex:0, role:'button',
        'aria-label':'Spotlight ' + name, 'data-focus-name':name
      })) hit.setAttribute(key, value);
      const hint = doc.createElementNS(hit.namespaceURI, 'title');
      hint.textContent = `Spotlight ${name}. Select again to return to Carl and Donut.`;
      hit.append(hint);
      hit.addEventListener('click', event => {
        event.preventDefault();
        event.stopPropagation();
        selected = selected === name ? null : name;
        paint();
      });
      hit.addEventListener('keydown', event => {
        if (!['Enter', ' ', 'Escape'].includes(event.key)) return;
        event.preventDefault();
        event.stopPropagation();
        if (event.repeat) return;
        selected = event.key === 'Escape' || selected === name ? null : name;
        paint();
      });
      entry.parentNode.append(hit);
      controls.push({entry, hit, name});
    }
    paint();
  });
})();
