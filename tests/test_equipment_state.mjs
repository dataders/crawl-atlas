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
