/* dash-utils.js — tiny shared helpers, loaded FIRST on both dashboard pages (before the inline
   page scripts and search.js). Single source of truth for organisation-name normalisation,
   country names, and "today", so the two pages and the search palette can never silently diverge.
   (Keep window.DASH.norm in lockstep with scripts/common.py norm_org — the org ids in the search
   index are built with that exact rule.) */
window.DASH = (function () {
  'use strict';
  // EN -> Nepali country names (factual; shown when the page is in नेपाली). Superset of what the
  // search palette and the deep-dive ledger each need.
  var COUNTRY_NE = {
    'United States': 'संयुक्त राज्य अमेरिका', 'Nepal': 'नेपाल', 'United Kingdom': 'बेलायत',
    'Germany': 'जर्मनी', 'Mexico': 'मेक्सिको', 'Luxembourg': 'लक्जेम्बर्ग', 'Mozambique': 'मोजाम्बिक',
    'Sri Lanka': 'श्रीलंका', 'United Arab Emirates': 'संयुक्त अरब इमिरेट्स', 'Afghanistan': 'अफगानिस्तान',
    'Canada': 'क्यानडा', 'Hong Kong': 'हङकङ', 'India': 'भारत', 'China': 'चीन',
    'Switzerland': 'स्विट्जरल्यान्ड', 'Japan': 'जापान', 'France': 'फ्रान्स', 'Belgium': 'बेल्जियम',
    'Netherlands': 'नेदरल्यान्ड्स'
  };
  return {
    // The viewer's current date (YYYY-MM-DD). Drives "deadline passed / runs until" labels so they
    // are always correct for whoever is looking — never a frozen build-time constant.
    today: new Date().toISOString().slice(0, 10),
    COUNTRY_NE: COUNTRY_NE,
    // Canonical org key — MUST match scripts/common.py norm_org so JS lookups line up with the
    // org ids baked into the search index.
    norm: function (s) {
      return String(s || '').toUpperCase().replace(/[^A-Z0-9 ]/g, ' ')
        .replace(/\b(INC|INCORPORATED|LLC|LTD|LIMITED|CORP|CORPORATION|CO|PVT|PRIVATE|THE|AND|OF|A)\b/g, ' ')
        .replace(/\s+/g, ' ').trim();
    },
    // Localised country name (Nepali when the page is in नेपाली, else as written).
    ccName: function (c) {
      return (document.documentElement.lang === 'ne' && COUNTRY_NE[c]) ? COUNTRY_NE[c] : (c || '');
    },
    // Client-side "download this view" — turn an array of plain objects into a CSV file. Lets a
    // journalist/researcher take exactly what is on screen without a server round-trip. The BOM
    // makes Excel read UTF-8 (Devanagari/diacritics) correctly.
    downloadCSV: function (filename, rows) {
      if (!rows || !rows.length) return;
      var cols = Object.keys(rows[0]);
      var cell = function (v) {
        v = (v == null ? '' : String(v));
        return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
      };
      var csv = cols.join(',') + '\n' +
        rows.map(function (r) { return cols.map(function (c) { return cell(r[c]); }).join(','); }).join('\n');
      var a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
      a.download = filename;
      document.body.appendChild(a); a.click();
      setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
    },
    // Granular sector breakdown from the treemap rows ([{cat, sec, v}, …], v in US$ m). Returns the
    // year total, category/program counts, a category breakdown sorted by amount (each with its
    // share of the total), the largest category, and the single largest program — the detailed
    // figures the "Inside the sectors" panel mirrors from the other sections. Pure + side-effect
    // free so it is unit-testable (see report/dashboard/tests/sector-summary.test.js).
    sectorSummary: function (rows) {
      rows = Array.isArray(rows) ? rows : [];
      var total = 0, byCat = {}, nProgs = 0, top = null;
      rows.forEach(function (r) {
        var v = Number(r && r.v) || 0;
        if (v <= 0) return;
        nProgs += 1;
        total += v;
        byCat[r.cat] = (byCat[r.cat] || 0) + v;
        if (!top || v > top.v) top = { name: r.sec, cat: r.cat, v: v };
      });
      var cats = Object.keys(byCat).map(function (c) {
        return { name: c, v: byCat[c], share: total ? byCat[c] / total : 0 };
      }).sort(function (a, b) { return b.v - a.v; });
      if (top) top.share = total ? top.v / total : 0;
      return {
        total: total,
        nCats: cats.length,
        nProgs: nProgs,
        cats: cats,
        topCat: cats[0] || null,
        topProg: top
      };
    }
  };
})();

// CommonJS export so the pure helpers (e.g. sectorSummary) can be unit-tested under Node without a
// browser. Harmless in the browser, where `module` is undefined.
if (typeof module !== 'undefined' && module.exports) { module.exports = window.DASH; }
