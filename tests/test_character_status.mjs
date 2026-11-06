import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import test from 'node:test';
const require = createRequire(import.meta.url);
const {characterState} = require('../site/dist/detail-model.js');
const character = {name:'Example character'};
const status = (lifeStatus, progress, subject = character.name) => ({
  type:'story', action:'note', subject, lifeStatus, progress,
  source:`source-${progress}`, book:1, chapter:1,
});

test('status follows explicit revealed observations and rewinds without retaining future state', () => {
  const death = status('dead', 0.4);
  const survival = status('alive', 0.8);
  const events = [death, survival];
  const at = cutoff => characterState(character, events.filter(e => e.progress <= cutoff));
  assert.equal(at(0.39).lifeStatus, 'unknown');
  assert.equal(at(0.39).lifeStatusEvent, undefined);
  assert.equal(at(0.4).lifeStatus, 'dead');
  assert.equal(at(0.4).lifeStatusEvent, death);
  assert.equal(at(0.8).lifeStatus, 'alive');
  assert.equal(at(0.8).lifeStatusEvent, survival);
  assert.equal(at(0.7).lifeStatus, 'dead');
  assert.equal(at(0).lifeStatus, 'unknown');
});

test('presumed death stays distinct from confirmed death', () => {
  const presumption = status('presumed-dead', 0.4);
  const state = characterState(character, [presumption]);
  assert.equal(state.lifeStatus, 'presumed-dead');
  assert.equal(state.lifeStatusEvent, presumption);
});

test('other characters and unverified status fields cannot establish survival', () => {
  const state = characterState({...character, lifeStatus:'alive'}, [
    status('dead', 0.4, 'Another character'),
    status('probably-alive', 0.5),
    {type:'level', subject:character.name, level:10, progress:0.6},
  ]);
  assert.equal(state.lifeStatus, 'unknown');
  assert.equal(state.lifeStatusEvent, undefined);
});

test('Donut alias uses the same explicit status history', () => {
  const event = status('alive', 0.5, 'Donut');
  assert.equal(characterState({name:'Princess Donut'}, [event]).lifeStatusEvent, event);
});
