import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require = createRequire(import.meta.url);
const {inventoryAt, inventoryRecord, itemStatBoost} = require('../site/dist/detail-model.js');
assert.equal(itemStatBoost({name:'Ring of Strength +2'}), '—');
assert.equal(itemStatBoost({statBoosts:[]}), '—');
assert.equal(itemStatBoost({statBoosts:[{stat:'DEX',value:5,unit:'points'}]}), 'DEX +5');
assert.equal(itemStatBoost({statBoosts:[{stat:'ALL',value:5,unit:'percent'}]}), 'All stats +5%');
assert.equal(itemStatBoost({statBoosts:[{stat:'STR',value:3,unit:'points',condition:'Fist mode only'},{stat:'DEX',value:1,unit:'points'}]}), 'STR +3 (Fist mode only) · DEX +1');
const common={type:'item',itemId:'ring',subject:'Carl',name:'Ring'};
const events=[
 {...common,action:'add',progress:0.1},
 {...common,action:'note',progress:0.2,statBoosts:[{stat:'DEX',value:5,unit:'points',source:'b1-c2-p3'}]},
 {...common,action:'equip',progress:0.3},
 {...common,action:'unequip',progress:0.4},
 {...common,action:'remove',progress:0.5},
];
for(const cutoff of [0.1,0.2,0.3,0.4,0.1]) {
 const [item]=inventoryAt(events.filter(event=>event.progress<=cutoff));
 assert.equal(inventoryRecord(item).stat_boost,cutoff<0.2?'—':'DEX +5');
 if(cutoff===0.4) assert.equal(item.state,'carried');
}
assert.equal(inventoryAt(events).length,0);
// Metadata changes replace the prior modifier list rather than summing item totals.
const updated=inventoryAt([...events.slice(0,3),{...common,action:'note',progress:0.35,statBoosts:[{stat:'DEX',value:10,unit:'points'}]}]);
assert.equal(inventoryRecord(updated[0]).stat_boost,'DEX +10');
