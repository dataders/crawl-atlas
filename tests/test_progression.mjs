import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const data=JSON.parse(readFileSync('site/dist/data/series.json','utf8'));
const imani=data.characters.find(c=>c.name==='Imani C.');
const events=data.events.filter(e=>e.subject===imani.name);
const growth=events.find(e=>e.action==='increase');
const fields=new Map();
const $=key=>{if(!fields.has(key))fields.set(key,{innerHTML:'',textContent:'',setAttribute(){},querySelectorAll(){return [];}});return fields.get(key);};
const state={data,progress:1,chartMetric:'level'};
const context=vm.createContext({state,$,window:{matchMedia:()=>({matches:false})},esc:String,SERIES:{},EVENT_COLORS:{skill:'red',item:'green',party:'blue'},events,imani});
const source=readFileSync('site/dist/app.js','utf8');
vm.runInContext(readFileSync('site/dist/detail-model.js','utf8'),context);
vm.runInContext(source.slice(source.indexOf('function currentLocation('),source.indexOf('function progressFor(')),context);
vm.runInContext(source.slice(source.indexOf('function renderChart('),source.indexOf('function renderAll(')),context);
context.before=events.filter(e=>e.progress<growth.progress);
assert.equal(vm.runInContext('characterState(imani,before).level',context),24);
assert.equal(vm.runInContext('characterState(imani,events).level',context),null);
state.facts = JSON.parse(readFileSync('site/dist/data/progression.json','utf8'));
const frame = $('#reader-board');
frame.setAttribute = (key, value) => frame[key] = value;
frame.getAttribute = key => frame[key];
frame.removeAttribute = key => delete frame[key];
state.followedCharacters = [];
vm.runInContext('renderChart()', context);
const late = readFileSync('site/dist/' + frame.src, 'utf8');
assert.ok(late.includes('Carl') && late.includes('Mordecai'));
state.progress = state.facts[0].progress;
vm.runInContext('renderChart()', context);
const early = readFileSync('site/dist/' + frame.src, 'utf8');
assert.ok(early.includes('Carl') && !early.includes('Mordecai'));
for (const book of data.books.slice(1).reverse()) {
  state.progress = (book.startChapter - 1 + 0.001) / data.series.chapterCount;
  vm.runInContext('renderChart()', context);
  const html = readFileSync('site/dist/' + frame.src, 'utf8');
  assert.ok(html.includes(`data-book-count="${book.number}"`));
  assert.ok(html.includes(book.number <= 3 ? `>Book ${book.number}</text>` : `>B${book.number}</text>`));
  assert.ok(!html.includes(`>B${book.number+1}</text>`));
}
// A skill between level-ups must immediately get its own native ledger row.
const skill = state.facts.find(row => row.kind === "skill" && row.progress > state.facts[0].progress);
for (const cutoff of [skill.progress, skill.progress - 1e-8]) {
  state.progress = cutoff;
  vm.runInContext('renderChart()', context);
  const html = readFileSync('site/dist/' + frame.src, 'utf8');
  const ledger = html.split('id="chart-ledger"')[1];
  assert.ok(ledger, 'dbt Charts exports the ledger in the same board');
  assert.equal((ledger.match(/class="dbt-table-row"/g)||[]).length,
    state.facts.filter(row => row.progress <= cutoff).length);
}
state.progress = 0;
vm.runInContext('renderChart()', context);
assert.ok(frame.hidden && !frame.src);
