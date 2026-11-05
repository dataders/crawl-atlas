// The reading slider moves between static chart checkpoints. Paint the floor
// intervals at its exact position, using the Level chart's own book scale.
function updateFloorBands() {
  const frame = document.querySelector('#reader-board');
  if (frame.hidden || frame.hasAttribute('aria-busy')) return;
  const chart = frame.contentDocument?.getElementById('chart-Level');
  const axis = chart?.querySelector('[data-dct-role="x-axis"]');
  if (!axis) return;
  const plot = axis.parentNode;
  plot.querySelector('.floor-bands')?.remove();
  const ticks = axis.querySelectorAll('line');
  if (!ticks.length) return;
  const width = Number(ticks[ticks.length - 1].getAttribute('x1'));
  const height = Number(ticks[0].getAttribute('y1'));
  const bookCount = Number(axis.dataset.bookCount);
  const books = state.data.books;
  const cursor = currentLocation();
  const end = (cursor.book.number - 1 + (cursor.chapter - 1 + cursor.position) / cursor.book.chapterCount);
  const reached = state.floors.filter(entry => {
    const book = books[entry.book - 1];
    return book.startChapter + entry.chapter - 2 + entry.position <= state.progress * state.data.series.chapterCount;
  });
  const locationLabel = entry => entry.locationLabel ?? `Book ${entry.book}, Chapter ${entry.chapter}`;
  const coord = entry => entry.book - 1 + (entry.chapter - 1 + entry.position) / books[entry.book-1].chapterCount;
  const svg = (name, attrs) => {
    const node = chart.ownerDocument.createElementNS('http://www.w3.org/2000/svg', name);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  };
  const bands = svg('g', {class:'floor-bands',role:'group','aria-label':'Dungeon floors reached by the party','pointer-events':'none'});
  for (const [index, entry] of reached.entries()) {
    const left = coord(entry) * width / bookCount;
    const right = (reached[index+1] ? coord(reached[index+1]) : end) * width / bookCount;
    const span = Math.max(0, Math.min(width, right) - left);
    const label = `Floor ${entry.floor}`;
    const group = svg('g', {'data-floor':entry.floor,role:'img','aria-label':`${label}, ${locationLabel(entry)}`});
    group.append(svg('rect',{x:left,y:0,width:span,height,fill:entry.floor%2?'#bed792':'#92bac6','fill-opacity':entry.floor%2?'.11':'.055'}));
    group.append(svg('line',{x1:left,x2:left,y1:0,y2:height,stroke:'#adbdab','stroke-opacity':'.48','stroke-dasharray':'2 3'}));
    if (span >= 16) {
      const text = svg('text',{x:left+span/2,y:13,'text-anchor':'middle',fill:'#d1dcc9','font-size':10,'font-family':'system-ui,sans-serif'});
      text.textContent = span >= 42 ? label : String(entry.floor);
      group.append(text);
    }
    bands.append(group);
  }
  plot.prepend(bands);
  let key = frame.contentDocument.querySelector('.floor-key');
  if (!key && reached.length) {
    key = chart.ownerDocument.createElement('details');
    key.className = 'floor-key';
    chart.closest('.dbt-charts-board').prepend(key);
  }
  if (key) {
    key.hidden = !reached.length;
    const last = reached.at(-1);
    if (last) {
      key.innerHTML = '<summary>Party’s dungeon floor · Floor '+last.floor+'</summary><ol>'+reached.map(entry=>
        '<li>Floor '+entry.floor+' · '+locationLabel(entry)+'</li>').join('')+'</ol>';
    }
  }
}
