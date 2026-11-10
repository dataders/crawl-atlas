const root = require('node:path').resolve(__dirname, '..');
const {inventoryAt,inventoryRecord,storyEntries} = require(root+'/site/dist/detail-model.js');
const {equipmentEffectRows} = require(root+'/site/dist/equipment-effects.js');
const {rewardRows,rewardRecord} = require(root+'/site/dist/rewards.js');
const {dossierRecord,dossierEvents,isRecordedEquipped} = require(root+'/site/dist/board-details.js');
const readline = require('node:readline');
let data, facts;
readline.createInterface({input: process.stdin}).on('line', line => {
  const request = JSON.parse(line);
  if (request.series) {
    data = request.series;
    facts = request.facts;
    return;
  }
  const {cutoff, character} = request;
  const visible = data.events.filter(e=>e.progress<=cutoff).sort((a,b)=>a.progress-b.progress);
  const own = dossierEvents(visible,character);
  const items = inventoryAt(visible).filter(e=>e.subject===character||(character==='Princess Donut'&&e.subject==='Donut'));
  items.sort((a,b)=>(b.acquiredProgress??b.progress)-(a.acquiredProgress??a.progress));
  console.log(JSON.stringify({
   effects:equipmentEffectRows(visible,character),
   inventory:items.map(e=>dossierRecord('inventory',inventoryRecord(e))),
   equipped:items.filter(isRecordedEquipped).map(e=>dossierRecord('inventory',inventoryRecord(e))),
   rewards:rewardRows(own,visible).sort((a,b)=>b.event.progress-a.event.progress).map(e=>dossierRecord('rewards',rewardRecord(e))),
   history:storyEntries(own,facts,cutoff).map(e=>({...dossierRecord('story',e.row),evidence:e.note}))
  }));
});
