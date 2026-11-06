// Equipment effects are not character totals. Reduce only already-revealed events.
const {inventoryAt} = require('./detail-model.js');
const key = (subject, name) => `${subject}|${name}`.toLowerCase();
function equipmentEffects(events, character) {
  const own = events.filter(e => e.subject === character && e.type === 'item' && !e.historyOnly);
  const held = new Map(inventoryAt(own).map(e => [key(e.subject,e.name), e]));
  const catalog = new Map();
  for (const event of own) {
    const k = key(event.subject,event.name);
    const entry = catalog.get(k) ?? {name:event.name, effects:new Map()};
    if (event.attachedTo) entry.attachedTo=event.attachedTo;
    for (const effect of event.effects ?? []) entry.effects.set(effect.id,{...effect, source:event.source, book:event.book, chapter:event.chapter, progress:event.progress});
    for (const boost of event.statBoosts ?? []) {
      const id=`stat:${boost.stat}:${boost.unit}:${boost.condition??''}`;
      entry.effects.set(id,{id,kind:'stat',target:boost.stat,operation:'add',value:boost.value,unit:boost.unit,condition:boost.condition,source:boost.source,book:event.book,chapter:event.chapter,progress:event.progress});
    }
    catalog.set(k,entry);
  }
  function status(k, visited=new Set()) {
    if(visited.has(k)) return 'Attachment unresolved';
    visited.add(k);
    const item=held.get(k);
    if(!item) return 'No longer held';
    if(item.state!=='equipped') return 'Not equipped';
    const parent=catalog.get(k)?.attachedTo;
    if(parent) {
      const parentState=status(key(character,parent),visited);
      if(parentState!=='Equipped') return `Jacket/item: ${parentState.toLowerCase()}`;
    }
    return 'Equipped';
  }
  return [...catalog.entries()].flatMap(([k,item]) => [...item.effects.values()].map(effect => ({
    ...effect, item:item.name, attachedTo:item.attachedTo, status:status(k),
    active:status(k)==='Equipped' && !effect.condition
  }))).sort((a,b)=>b.progress-a.progress || a.item.localeCompare(b.item));
}
function effectLabel(effect) {
  const {target,operation,value,unit}=effect;
  if(operation==='add') return `${target} ${value>=0?'+':''}${value}${unit==='percent'?'%':unit==='levels'?' levels':' points'}`;
  if(operation==='multiply') return `${target} ×${value}`;
  if(operation==='grant') return `${target} granted`;
  if(operation==='immune') return `Immune: ${target}`;
  return `${target}: ${operation.replace(/^(rule|grant): /,'')}`;
}
function equipmentEffectRows(events,character) {
  return equipmentEffects(events,character).map(e=>({effect:effectLabel(e),from_item:e.item,
    attached_to:e.attachedTo??'—',state:e.status,condition:e.condition??'—',
    observed:`B${e.book} · Ch ${e.chapter}`}));
}
module.exports={equipmentEffects,equipmentEffectRows,effectLabel};
