import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const html=readFileSync('site/dist/index.html','utf8');
const reader=readFileSync('site/dist/static-reader.js','utf8');
const fake=JSON.parse(readFileSync('site/dist/data/spoiler-free.json','utf8'));

assert.ok(html.includes("I haven't read them yet, can I see a spoiler-free version?"));
assert.ok(html.includes('class="spoiler-free-banner"'));
assert.ok(reader.includes("data/spoiler-free.json?v=1"));
assert.ok(reader.includes("charts/${file}.html"));
assert.equal(fake.series.dataVersion,'FAKE-1');
assert.equal(fake.checkpoints.length,5);
assert.equal(fake.characters.length,0);

const serialized=JSON.stringify(fake);
for(const name of ['Carl','Donut','Mongo','Katia','Mordecai','Imani','Prepotente']){
  assert.ok(!serialized.includes(name),`fake catalog includes ${name}`);
}
