// Each table has its own reading length. Increasing it never changes the slider.
const tableLimits = new Map();
function shownCount(key, total) {
  return Math.min(total, tableLimits.get(key) ?? 10);
}
function tableControls(key, total) {
  if (total <= 10) return '';
  const shown = shownCount(key, total);
  const button = (limit, label) => `<button type="button" data-table="${key}" data-limit="${limit}">${label}</button>`;
  return `<div class="table-controls"><span>${shown} of ${total}</span>
    ${shown < total ? button(shown + 10, 'Show more') : ''}
    ${shown + 10 < total ? button(Infinity, 'Show all') : ''}
    ${shown > 10 ? button(10, 'Show fewer') : ''}</div>`;
}

// Lay out the two exported tables with the reader's row limits. Keep dct's
// actual rows, headings, colors and columns, including all later native pages.
function installTableLimits(board) {
  const svg = board.querySelector(':scope > svg');
  if (!svg) return () => {};
  const ns = svg.namespaceURI;
  const view = svg.viewBox.baseVal;
  const originalHeight = view.height;
  const background = svg.querySelector(':scope > rect');
  const content = svg.querySelector(':scope > g');
  const innerBackground = content.querySelector(':scope > rect');
  const innerHeight = Number(innerBackground.getAttribute('height'));
  const footer = [...content.parentNode.children].slice([...svg.children].indexOf(content) + 1);
  const tables = ['levels','ledger'].map(key => {
    const chart = svg.querySelector('#chart-'+key);
    const box = chart.querySelector('.dbt-box-outer');
    const body = chart.querySelector(':scope > g');
    const wrapper = chart.parentNode;
    const top = wrapper.transform.baseVal.consolidate().matrix.f;
    const height = Number(box.getAttribute('height'));
    const rows = [...body.querySelectorAll('.dbt-table-row')];
    const metrics = rows.map(row => {
      const ys = [...row.querySelectorAll('text[y],tspan[y]')].map(cell=>Number(cell.getAttribute('y')));
      return {baseline: Math.min(...ys), height: 24 + Math.max(...ys) - Math.min(...ys)};
    });
    rows.forEach(row=>row.remove());
    body.querySelectorAll('.dbt-table-page').forEach(page=>page.remove());
    const controls = svg.ownerDocument.createElementNS(ns, 'foreignObject');
    chart.append(controls);
    return {key, chart, box, body, wrapper, top, height, rows, metrics, controls};
  });
  function layout() {
    let offset = 0;
    for (const t of tables) {
      const shown = shownCount(t.key,t.rows.length);
      let cursor = t.metrics[0]?.baseline ?? 81;
      t.rows.forEach((row,i)=>{
        if (i>=shown) {row.remove();return;}
        row.setAttribute('transform',`translate(0,${cursor-t.metrics[i].baseline})`);
        t.body.append(row);
        cursor += t.metrics[i].height;
      });
      const buttons = tableControls(t.key,t.rows.length);
      const end = cursor + 4;
      const height = end + (buttons ? 56 : 8);
      t.wrapper.setAttribute('transform',`translate(0,${t.top+offset})`);
      t.box.setAttribute('height',height);
      t.chart.querySelector('.dbt-box-inner').setAttribute('height',height-32);
      t.controls.setAttribute('x',16); t.controls.setAttribute('y',end);
      t.controls.setAttribute('width',Number(t.box.getAttribute('width'))-32);
      t.controls.setAttribute('height',buttons ? 56 : 0);
      t.controls.innerHTML = buttons ? `<div xmlns="http://www.w3.org/1999/xhtml">${buttons}</div>` : '';
      offset += height-t.height;
    }
    const height=originalHeight+offset;
    svg.setAttribute('viewBox',`0 0 ${view.width} ${height}`);
    svg.setAttribute('height',height);
    background.setAttribute('height',height);
    innerBackground.setAttribute('height',innerHeight+offset);
    footer.forEach(node=>node.setAttribute('transform',`translate(0,${offset})`));
  }
  layout();
  return layout;
}
