/* Unit tests for DASH.sectorSummary — the data transformation behind the granular breakdown in the
   "Inside the sectors" section. Pure logic, no browser needed. Run with: node report/dashboard/tests/sector-summary.test.js
   (exits non-zero on failure). */
'use strict';
const assert = require('assert');

// dash-utils.js assigns window.DASH and (for Node) exports it. Provide the minimal browser globals
// it touches at load time so it can be required here.
global.window = {};
global.document = { documentElement: { lang: 'en' } };
const DASH = require('../dash-utils.js');

const near = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;

// --- typical treemap rows: two categories, three programs ---
(function () {
  const rows = [
    { cat: 'Health', sec: 'HIV/AIDS', v: 3 },
    { cat: 'Health', sec: 'Nutrition', v: 1 },
    { cat: 'Economic Development', sec: 'Infrastructure', v: 16 },
  ];
  const s = DASH.sectorSummary(rows);
  assert.strictEqual(s.total, 20, 'total sums all program values');
  assert.strictEqual(s.nCats, 2, 'distinct category count');
  assert.strictEqual(s.nProgs, 3, 'program count');
  // categories sorted by amount, each with its share of the total
  assert.deepStrictEqual(s.cats.map(c => c.name), ['Economic Development', 'Health']);
  assert.strictEqual(s.cats[0].v, 16);
  assert.strictEqual(s.cats[1].v, 4);
  assert.ok(near(s.cats[0].share, 0.8), 'top category share');
  assert.ok(near(s.cats[1].share, 0.2), 'second category share');
  assert.ok(near(s.cats.reduce((t, c) => t + c.share, 0), 1), 'shares sum to 1');
  assert.strictEqual(s.topCat.name, 'Economic Development');
  // biggest single program is the largest single row, not the largest category rollup
  assert.strictEqual(s.topProg.name, 'Infrastructure');
  assert.strictEqual(s.topProg.cat, 'Economic Development');
  assert.ok(near(s.topProg.share, 0.8), 'top program share of total');
})();

// --- ignores zero / non-positive / missing values ---
(function () {
  const s = DASH.sectorSummary([
    { cat: 'Health', sec: 'A', v: 5 },
    { cat: 'Health', sec: 'B', v: 0 },
    { cat: 'Governance', sec: 'C', v: -2 },
    { cat: 'Governance', sec: 'D' },
  ]);
  assert.strictEqual(s.total, 5);
  assert.strictEqual(s.nProgs, 1, 'only positive-value programs are counted');
  assert.strictEqual(s.nCats, 1, 'a category with no positive value is dropped');
})();

// --- empty / invalid input is safe ---
(function () {
  for (const bad of [[], null, undefined, 'nope']) {
    const s = DASH.sectorSummary(bad);
    assert.strictEqual(s.total, 0);
    assert.strictEqual(s.nCats, 0);
    assert.strictEqual(s.nProgs, 0);
    assert.deepStrictEqual(s.cats, []);
    assert.strictEqual(s.topCat, null);
    assert.strictEqual(s.topProg, null);
  }
})();

console.log('sector-summary.test.js: all assertions passed');
