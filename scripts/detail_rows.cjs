const {readFileSync} = require('node:fs');
const {characterState, inventoryAt, dossierTables, inventoryRecord, storyRecord} = require('../site/dist/detail-model.js');
const {rewardRows, rewardRecord} = require('../site/dist/rewards.js');
const {events, characters} = JSON.parse(readFileSync('site/dist/data/series.json'));
const tables = Object.fromEntries(['stats','skills','history','inventory','rewards','story'].map(k=>[k,new Map()]));
function collect(table, rows) {
  for (const row of rows) tables[table].set(JSON.stringify(row), row);
}
const visible = [];
for (const event of events.toSorted((a,b)=>a.progress-b.progress)) {
  visible.push(event);
  collect("story", [storyRecord(event)]);
  if (event.acquisition) collect("rewards", rewardRows(visible, visible).map(rewardRecord));
  if (event.type === 'item') collect('inventory', inventoryAt(visible).map(inventoryRecord));
  else if (['level','stat','skill'].includes(event.type)) {
    const character = characters.find(c=>c.name===event.subject || (c.name==='Princess Donut' && event.subject==='Donut'));
    if (character) for (const [type, rows] of Object.entries(dossierTables(characterState(character, visible)))) collect(type, rows);
  }
}
console.log(JSON.stringify(Object.fromEntries(Object.entries(tables).map(([k,v])=>[k,[...v.values()]]))));
