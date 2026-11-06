import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const {equipmentEffects,equipmentEffectRows}=createRequire(import.meta.url)('../site/dist/equipment-effects.js');
const e=(name,action,progress,extra={})=>({subject:'Carl',type:'item',name,action,progress,book:1,chapter:1,source:`p${progress}`,...extra});
test('attachment and equip state control effects without creating totals or learned ranks',()=>{
 const events=[e('Jacket','equip',.1),e('Patch','note',.2,{effects:[{id:'bonus',kind:'skill',target:'Handling',operation:'add',value:2,unit:'levels'}]}),e('Patch','equip',.3,{attachedTo:'Jacket'}),e('Jacket','unequip',.4),e('Jacket','equip',.5),e('Patch','remove',.6)];
 const at=p=>equipmentEffects(events.filter(e=>e.progress<=p),'Carl');
 assert.equal(at(.1).length,0);assert.equal(at(.2)[0].active,false);assert.equal(at(.3)[0].active,true);
 assert.equal(at(.4)[0].active,false);assert.equal(at(.5)[0].active,true);assert.equal(at(.6)[0].active,false);
 assert.equal(at(.3)[0].active,true);assert.equal(at(.3)[0].value,2);assert.equal(at(.3)[0].level,undefined);
});
test('patch bonuses and grants appear only after their own reveal; no future back-patch powers',()=>{
 const data=JSON.parse(fs.readFileSync(new URL('../site/dist/data/series.json',import.meta.url)));
 const reveal=data.events.find(e=>e.source==='b6-c3-p153'&&e.effects?.some(x=>x.id==='climb'));
 const before=equipmentEffects(data.events.filter(e=>e.progress<reveal.progress),'Carl');
 assert.ok(!before.some(e=>e.id==='climb'));
 const after=equipmentEffects(data.events.filter(e=>e.progress<=reveal.progress),'Carl');
 assert.ok(after.some(e=>e.id==='climb'&&e.active));
 assert.ok(after.some(e=>e.id==='peace-dex'&&e.value===10&&e.unit==='percent'&&e.active));
 assert.ok(after.some(e=>e.id==='bomb-skill'&&e.value===2));
 assert.ok(after.some(e=>e.target==='DEX'&&e.value===25&&e.unit==='points'));
 assert.ok(equipmentEffectRows(data.events,'Carl').some(e=>e.effect==='Dangerous Explosives Handling +2 levels'));
});
