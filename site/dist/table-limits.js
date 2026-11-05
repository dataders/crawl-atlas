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
