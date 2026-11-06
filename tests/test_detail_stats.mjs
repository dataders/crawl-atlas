import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import test from 'node:test';
const require = createRequire(import.meta.url);
const {characterState, dossierTables, storyEntries} = require('../site/dist/detail-model.js');
const character = {name:'Carl'};
const stat = (data) => ({type:'stat', subject:'Carl', book:1, chapter:1, position:0.5, ...data});

test('delta-only observations cannot turn stale or mixed-scope readings into totals', () => {
  const base = stat({stats:{DEX:10}, statScopes:{DEX:'base'}});
  const gear = stat({stats:{DEX:18}, statScopes:{DEX:'effective'}});
  const delta = stat({statsDelta:{DEX:5}, statScopes:{DEX:'equipment'}});
  const state = characterState(character, [base, gear, delta]);
  assert.equal(state.stats.DEX, null);
  assert.equal(state.baseStats.DEX, 10);
  assert.deepEqual(dossierTables(state).stats, [{stat:'DEX', base:'10', reported:'—'}]);
  assert.equal(characterState(character, [base, gear]).stats.DEX, 18, 'rewind restores the observation');
  assert.equal(characterState(character, [delta]).stats.DEX, null, 'no baseline is not zero');
});

test('an explicit total restores reported state and takes precedence over its own delta', () => {
  const delta = stat({statsDelta:{DEX:5}, statScopes:{DEX:'base'}});
  const total = stat({stats:{DEX:30}, statsDelta:{DEX:3}, statScopes:{DEX:'base'}});
  const state = characterState(character, [delta, total]);
  assert.equal(state.stats.DEX, 30);
  assert.equal(state.baseStats.DEX, 30);
});

test('estimates and bounds never replace or invalidate exact dossier observations', () => {
  const exact = stat({stats:{DEX:10}, statScopes:{DEX:'base'}});
  const approximate = ['estimate', 'lower-bound'].map(scope => stat({
    stats:{DEX:100}, statsDelta:{DEX:20}, statScopes:{DEX:scope}
  }));
  const state = characterState(character, [exact, ...approximate]);
  assert.equal(state.stats.DEX, 10);
  assert.equal(state.baseStats.DEX, 10);
});

test('delta-only observation stays visible in History at its reveal position', () => {
  const delta = stat({id:'delta', statsDelta:{DEX:5}, progress:0.5});
  const fact = {event_id:'delta', progress:0.5, action:'delta', delta:5, value:null,
    metric:'DEX', scope:'equipment', source:'b1-c1-p1'};
  assert.equal(storyEntries([delta], [fact], 0.49).length, 0);
  assert.equal(storyEntries([delta], [fact], 0.5)[0].row.what_changed, 'DEX +5 (equipment)');
});
