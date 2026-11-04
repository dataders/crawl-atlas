import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
const fields = new Map();
const $ = selector => {
  if (!fields.has(selector)) fields.set(selector,{value:selector==='#query-sort'?'newest':'',innerHTML:'',textContent:'',disabled:false});
  return fields.get(selector);
};
const facts=JSON.parse(readFileSync('site/dist/data/progression.json','utf8'));
const state={facts,progress:1,followedCharacters:null};
const context=vm.createContext({state,$,esc:v=>String(v??'')});
const source=readFileSync('site/dist/explorer.js','utf8').split('function resetQuery()')[0];
vm.runInContext(source,context);
function render(){vm.runInContext('renderExplorer()',context);return JSON.parse(vm.runInContext('JSON.stringify(queryState.results)',context));}
render();$('#query-book').value='8';
const book8=render();assert.ok(book8.length>50);assert.ok(book8.every(r=>r.book===8));
state.followedCharacters=['Carl','Princess Donut'];
assert.ok(render().every(r=>state.followedCharacters.includes(r.character)));
state.progress=0;
assert.equal(render().length,0);assert.ok(!$('#query-character').innerHTML.includes('Donut'));assert.ok(!$('#query-book').innerHTML.includes('Book 8'));
state.progress=1;state.followedCharacters=[];assert.equal(render().length,0);
state.followedCharacters=['Carl'];render();$('#query-book').value='8';$('#query-search').value='Fursona';
const matches=render();assert.equal(matches.length,2);assert.equal(matches.find(r=>r.metric==='Fursona').delta,2);
console.log('Explorer: book, multiselect, spoiler boundary, empty selection, and skill search passed.');
