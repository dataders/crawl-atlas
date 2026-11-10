import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const {inventoryAt} = createRequire(import.meta.url)('../site/dist/detail-model.js');
test('equipment transitions override stale state and rewind with reader events', () => {
  const item={type:'item',subject:'Carl',name:'Test ring',itemId:'ring',quantity:1};
  const owned={...item,action:'add',progress:0.1};
  const worn={...item,action:'equip',state:'equipped',progress:0.2};
  const removed={...item,action:'unequip',state:'equipped',progress:0.3};
  const lost={...item,action:'lose',progress:0.4};
  const events=[owned,worn,removed,lost];
  const at=p=>inventoryAt(events.filter(e=>e.progress<=p));
  assert.equal(at(0.1)[0].state,'carried');
  assert.equal(at(0.2)[0].state,'equipped');
  assert.equal(at(0.3)[0].state,'carried');
  assert.equal(at(0.3)[0].acquiredProgress,0.1);
  assert.equal(at(0.4).length,0);
  assert.equal(at(0.2)[0].state,'equipped');
});

test('revealed aliases share one inventory item and ownership stays separate', () => {
 const events=[{type:'item',subject:'Carl',name:'Sock',itemId:'sock',action:'add',progress:.1},
 {type:'item',subject:'Carl',name:'Jefferson',itemId:'sock',action:'note',progress:.2},
 {type:'item',subject:'Carl',name:'Sock',action:'remove',progress:.3},
 {type:'item',subject:'Dong',name:'Jefferson',itemId:'sock',action:'equip',progress:.3}];
 assert.equal(inventoryAt(events.slice(0,1))[0].name,'Sock');
 assert.equal(inventoryAt(events.slice(0,2)).length,1);
 assert.deepEqual(inventoryAt(events).map(e=>e.subject),['Dong']);
});
test('floor-limited loot expires only after a revealed physical floor transition', () => {
 const item={type:'item',subject:'Louis',name:'Decorations',action:'add',expiresAfterFloor:8,progress:.1};
 const floor={type:'story',subject:'Carl',floor:9,mode:'physical',progress:.2};
 assert.equal(inventoryAt([item]).length,1);
 assert.equal(inventoryAt([item,floor]).length,0);
 assert.equal(inventoryAt([item]).length,1);
 assert.equal(inventoryAt([item,{...floor,historyOnly:true}]).length,1);
});
