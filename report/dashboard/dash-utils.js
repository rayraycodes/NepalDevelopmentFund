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
    }
  };
})();
