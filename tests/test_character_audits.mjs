import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {createRequire} from 'node:module';
const {inventoryAt, characterState} = createRequire(import.meta.url)('../site/dist/detail-model.js');
const data = JSON.parse(fs.readFileSync(new URL('../site/dist/data/series.json', import.meta.url)));
const event = (subject, source, name) => data.events.find(e => e.subject === subject && e.source === source && e.name === name);
const at = (boundary, inclusive = true) => data.events.filter(e => inclusive ? e.progress <= boundary.progress : e.progress < boundary.progress);
const holds = (events, subject, name) => inventoryAt(events).find(e => e.subject === subject && e.name === name);

test('borrowed wand disappears on return and returns when reader rewinds', () => {
  const loan = event('Zhang', 'b6-c64-p39', 'Shrink wand (borrowed from Carl)');
  const returned = event('Zhang', 'b6-c72-p105', loan.name);
  assert.ok(!holds(at(loan, false), 'Zhang', loan.name));
  assert.ok(holds(at(loan), 'Zhang', loan.name));
  assert.ok(!holds(at(returned), 'Zhang', loan.name));
  assert.ok(holds(at(loan), 'Zhang', loan.name));
});

test('observed equipment is visible but historical ownership is not resurrected', () => {
  const cloak = event('Imani C.', 'b1-c22-p28', 'Magical cloak');
  assert.equal(holds(at(cloak), 'Imani C.', cloak.name).state, 'equipped');
  const ring = event('Quan Ch', 'b6-c58-p106', 'Sappy gold ring');
  assert.ok(!holds(at(ring), 'Quan Ch', ring.name));
  const transfer = event('Osvaldo', 'b7-c78-p85', 'Memorial Crystal: Apito');
  assert.ok(holds(at(transfer, false), 'Osvaldo', transfer.name));
  assert.ok(!holds(at(transfer), 'Osvaldo', transfer.name));
});

test('skill levels preserve source scope and exact reveal boundary', () => {
  const reveal = event('Firas M', 'b4-c6-p26', 'Puddle Jumper');
  const person = data.characters.find(c => c.name === 'Firas M');
  assert.equal(characterState(person, at(reveal, false)).skills.find(s => s.name === reveal.name).level, null);
  assert.equal(characterState(person, at(reveal)).skills.find(s => s.name === reveal.name).level, 10);
  const dodge = data.events.filter(e => e.subject === 'Zhang' && e.name === 'Dodge');
  assert.ok(dodge.some(e => e.skillScope === 'base' && e.level === 11));
  assert.ok(dodge.some(e => e.skillScope === 'effective' && e.level === 14));
  assert.equal(event('Frank Q', 'b1-c43-p92', 'Find Crawler').level, null);
});
