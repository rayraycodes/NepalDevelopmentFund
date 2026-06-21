/* search.js — cross-dataset entity search + profile, shared by both dashboard pages.
   Loads window.SEARCH_INDEX (search_index.js, built by scripts/93_search_index.py).
   Self-contained: injects its own (AAA-contrast, scoped .sx-) styles and a command palette.
   Accessible: combobox/listbox semantics, full keyboard control, focus trap, Esc, focus return.
   Bilingual: follows the page's <html lang> and re-renders when the language toggle flips. */
(function () {
  'use strict';
  var IDX = window.SEARCH_INDEX || [];
  var LOCBYNAME = {};            // normalised org name -> {country, city, ...} for counterparty lists
  var PAGE = window.US_SUBS ? 'us' : 'main';           // which page are we on
  var OTHER = PAGE === 'us' ? '../index.html' : 'usforeignaiddata/index.html';

  var T = {
    en: {
      ph: 'Search organisations, districts, projects…', open: 'Search',
      empty: 'Search every dataset at once — organisations, sub-recipients, districts, projects, donors, budget accounts, sectors, sources and audits. Pick any result to open its full profile.',
      findhint: 'Search for any organisation, district, project, or funder, and see everything we know about it in one place.',
      no: 'No matches for', sug: 'Try one of these', count: '{n} results',
      roles: { prime: 'Prime partner', sub: 'Sub-recipient' }, based_in: 'Based in',
      types: { org: 'Organisation', district: 'District', project: 'Project', donor: 'Donor', account: 'Budget account', sector: 'Sector', source: 'Source', audit: 'Audit' },
      as_prime: 'As a prime partner', as_sub: 'As a sub-recipient',
      obligated: 'Obligated', outlayed: 'Outlayed (actually spent)', onward: 'Passed onward',
      current: 'Current award', potential: 'Potential award', received: 'Received', delivered: 'Delivered', rate: 'delivery rate',
      awarded: 'Awarded',
      across: 'across', awards: 'awards', subawards: 'sub-awards',
      funders: 'Top funders', districts_l: 'Where it landed', projects_l: 'Projects', orgs_l: 'Organisations', primes_l: 'Prime partners',
      subs_l: 'Sub-recipients',
      dl_passed: 'Deadline passed', dl_until: 'Runs until', dl_none: 'No end date recorded',
      recipient: 'Recipient', agency: 'Agency', status: 'Status', year: 'year',
      open_ledger: 'See full breakdown', open_us: 'Open in the US deep dive', open_main: 'Open on the main dashboard',
      view_source: 'Open source', open_record: 'Open USAspending record', open_report: 'Open audit report',
      questioned: 'Questioned costs', verdict: 'Finding', nondac: 'Non-DAC partner — recipient-reported (Nepal does, OECD misses)',
      acct_title: 'Financial accountability', single_audit: 'Single Audit (audited financials)', ein: 'EIN',
      fac_view: 'View on the Federal Audit Clearinghouse', fac_lookup: 'Look up audited financials (Single Audit)',
      usas_rec: 'USAspending recipient record', oig_audit: 'USAID Inspector General audit',
      sa_note: 'A Single Audit is the audited financial statement plus the schedule of US federal awards that a non-federal recipient files each year. For-profit contractors are not required to file one, and foreign organisations do not appear in this US registry.',
      latest: 'Most recent year', back: 'Back to results', close: 'Close',
      both_roles: 'This organisation appears in both roles below.',
      stat: { active: 'Active', completed: 'Completed', ended_2526: 'Ended FY25/26', undated: 'Undated' }
    },
    ne: {
      ph: 'संस्था, जिल्ला, परियोजना खोज्नुहोस्…', open: 'खोज्नुहोस्',
      empty: 'सबै डेटासेट एकैपटक खोज्नुहोस् — संस्था, उप-प्राप्तकर्ता, जिल्ला, परियोजना, दाता, बजेट खाता, क्षेत्र, स्रोत र लेखापरीक्षण। पूरा विवरण हेर्न कुनै नतिजा छान्नुहोस्।',
      findhint: 'कुनै पनि संस्था, जिल्ला, परियोजना वा दाता खोज्नुहोस्, र त्यसबारे हामीसँग भएको सबै जानकारी एकै ठाउँमा हेर्नुहोस्।',
      no: 'नतिजा भेटिएन:', sug: 'यीमध्ये प्रयास गर्नुहोस्', count: '{n} नतिजा',
      roles: { prime: 'प्रमुख साझेदार', sub: 'उप-प्राप्तकर्ता' }, based_in: 'अवस्थित',
      types: { org: 'संस्था', district: 'जिल्ला', project: 'परियोजना', donor: 'दाता', account: 'बजेट खाता', sector: 'क्षेत्र', source: 'स्रोत', audit: 'लेखापरीक्षण' },
      as_prime: 'प्रमुख साझेदारको रूपमा', as_sub: 'उप-प्राप्तकर्ताको रूपमा',
      obligated: 'प्रतिबद्ध', outlayed: 'वास्तवमा खर्च भएको', onward: 'अगाडि पठाइएको',
      current: 'हालको अवार्ड', potential: 'सम्भावित अवार्ड', received: 'प्राप्त', delivered: 'वितरण', rate: 'वितरण दर',
      awarded: 'अवार्ड मिति',
      across: '—', awards: 'अवार्ड', subawards: 'उप-अवार्ड',
      funders: 'प्रमुख दाता', districts_l: 'कहाँ पुग्यो', projects_l: 'परियोजना', orgs_l: 'संस्था', primes_l: 'प्रमुख साझेदार',
      subs_l: 'उप-प्राप्तकर्ता',
      dl_passed: 'म्याद सकियो', dl_until: 'सम्म चल्छ', dl_none: 'अन्त्य मिति छैन',
      recipient: 'प्राप्तकर्ता', agency: 'एजेन्सी', status: 'अवस्था', year: 'वर्ष',
      open_ledger: 'पूरा विवरण हेर्नुहोस्', open_us: 'US डिप डाइभमा खोल्नुहोस्', open_main: 'मुख्य ड्यासबोर्डमा खोल्नुहोस्',
      view_source: 'स्रोत खोल्नुहोस्', open_record: 'USAspending रेकर्ड खोल्नुहोस्', open_report: 'रिपोर्ट खोल्नुहोस्',
      questioned: 'प्रश्न उठेको खर्च', verdict: 'निष्कर्ष', nondac: 'गैर-DAC साझेदार — प्राप्तकर्ताले रिपोर्ट गर्छ (OECD ले छुटाउँछ)',
      acct_title: 'वित्तीय जवाफदेहिता', single_audit: 'एकल लेखापरीक्षण (लेखापरीक्षित वित्तीय विवरण)', ein: 'EIN',
      fac_view: 'Federal Audit Clearinghouse मा हेर्नुहोस्', fac_lookup: 'लेखापरीक्षित वित्तीय विवरण खोज्नुहोस् (Single Audit)',
      usas_rec: 'USAspending प्राप्तकर्ता रेकर्ड', oig_audit: 'USAID महालेखापरीक्षक लेखापरीक्षण',
      sa_note: 'Single Audit भनेको अमेरिकी गैर-संघीय प्राप्तकर्ताले हरेक वर्ष पेस गर्ने लेखापरीक्षित वित्तीय विवरण र संघीय अनुदानको तालिका हो। नाफामुखी ठेकेदारले पेस गर्नु पर्दैन, र विदेशी संस्था यो अमेरिकी रजिस्ट्रीमा देखिँदैनन्।',
      latest: 'पछिल्लो वर्ष', back: 'नतिजामा फर्कनुहोस्', close: 'बन्द गर्नुहोस्',
      both_roles: 'यो संस्था तल दुवै भूमिकामा देखिन्छ।',
      stat: { active: 'सक्रिय', completed: 'सम्पन्न', ended_2526: 'FY25/26 मा सकिएको', undated: 'मिति नभएको' }
    }
  };
  function L() { return (document.documentElement.lang === 'ne') ? T.ne : T.en; }

  // ---- formatting ----
  function money(v) {
    v = +v || 0;
    if (v >= 1e9) return '$' + (v / 1e9).toFixed(2) + 'bn';
    if (v >= 1e6) return '$' + (v / 1e6).toFixed(1) + 'm';
    if (v >= 1e3) return '$' + Math.round(v / 1e3) + 'k';
    return '$' + Math.round(v);
  }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;'); }
  var TODAY = '2026-06-21';

  // Country names in Nepali (factual; used only when the page is in नेपाली). City/state stay as-is.
  var COUNTRY_NE = {
    'United States': 'संयुक्त राज्य अमेरिका', 'Nepal': 'नेपाल', 'United Kingdom': 'बेलायत',
    'Germany': 'जर्मनी', 'Mexico': 'मेक्सिको', 'Luxembourg': 'लक्जेम्बर्ग', 'Mozambique': 'मोजाम्बिक',
    'Sri Lanka': 'श्रीलंका', 'United Arab Emirates': 'संयुक्त अरब इमिरेट्स', 'Afghanistan': 'अफगानिस्तान',
    'Canada': 'क्यानडा', 'Hong Kong': 'हङकङ', 'India': 'भारत', 'China': 'चीन', 'Switzerland': 'स्विट्जरल्यान्ड',
    'Japan': 'जापान', 'France': 'फ्रान्स', 'Belgium': 'बेल्जियम', 'Netherlands': 'नेदरल्यान्ड्स'
  };
  function countryName(c) { return (document.documentElement.lang === 'ne' && COUNTRY_NE[c]) ? COUNTRY_NE[c] : c; }
  function locText(loc) {
    if (!loc) return '';
    return [loc.city, loc.state, countryName(loc.country)].filter(Boolean).join(', ');
  }
  var PIN = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" aria-hidden="true"><path d="M12 21s7-5.5 7-11a7 7 0 0 0-14 0c0 5.5 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/></svg>';
  function locLine(loc) {
    if (!loc || !(loc.city || loc.country)) return '';
    return '<div class="sx-loc">' + PIN + '<span><b>' + esc(L().based_in) + ':</b> ' + esc(locText(loc)) +
      (loc.addr ? '<br><span class="sx-addr">' + esc(loc.addr) + '</span>' : '') + '</span></div>';
  }

  // ---- search ranking ----
  var TW = { org: 50, donor: 48, district: 45, project: 40, account: 25, audit: 22, sector: 20, source: 12 };
  function score(e, q, toks) {
    var name = e.n.toLowerCase();
    var hay = (e.n + ' ' + e.k.join(' ')).toLowerCase();
    for (var i = 0; i < toks.length; i++) { if (hay.indexOf(toks[i]) < 0) return 0; }
    var s;
    if (name === q) s = 1000;
    else if (name.indexOf(q) === 0) s = 600;
    else if ((' ' + name).indexOf(' ' + q) >= 0) s = 420;
    else if (name.indexOf(q) >= 0) s = 240;
    else s = 110;
    if (e.k.some(function (k) { return k.toLowerCase() === q; })) s += 320;
    else if (e.k.some(function (k) { return k.toLowerCase().indexOf(q) === 0; })) s += 480;
    else if (e.k.some(function (k) { return k.toLowerCase().indexOf(q) >= 0; })) s += 140;
    s += TW[e.t] || 0;
    s += Math.min(45, Math.log10((e.a || 0) + 10) * 5.2);
    return s;
  }
  function run(q) {
    q = (q || '').trim().toLowerCase();
    if (!q) return [];
    var toks = q.split(/\s+/);
    var hits = [];
    for (var i = 0; i < IDX.length; i++) {
      var sc = score(IDX[i], q, toks);
      if (sc > 0) hits.push([sc, IDX[i]]);
    }
    hits.sort(function (a, b) { return b[0] - a[0] || (b[1].a - a[1].a); });
    return hits.slice(0, 40).map(function (h) { return h[1]; });
  }

  // ---- styles (scoped .sx-, AAA contrast, uses the page's CSS vars) ----
  var CSS = `
  .sx-trigger{display:inline-flex;align-items:center;gap:8px;margin-left:auto;background:rgba(255,255,255,.10);
    border:1px solid rgba(255,255,255,.28);color:#eaf1f8;border-radius:9px;padding:0 12px;min-height:44px;
    font:inherit;font-size:13px;cursor:pointer;font-weight:600;white-space:nowrap}
  .sx-trigger:hover{background:rgba(255,255,255,.18)}
  .sx-trigger .sx-kbd{font-size:11px;background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.22);
    border-radius:5px;padding:1px 6px;font-weight:700}
  @media(max-width:760px){.sx-trigger .sx-kbd{display:none}.sx-trigger .sx-lbl{display:none}.sx-trigger{padding:0 12px}}
  /* prominent central search in the hero */
  .sx-hero{max-width:640px;margin:20px 0 2px}
  .sx-herobtn{display:flex;align-items:center;gap:11px;width:100%;background:#fff;border:1px solid rgba(255,255,255,.5);
    border-radius:13px;padding:0 16px;min-height:56px;font:inherit;font-size:16px;color:#3d4b5a;cursor:text;
    box-shadow:0 8px 26px rgba(0,0,0,.20);text-align:left}
  .sx-herobtn:hover{border-color:#fff}
  .sx-herobtn .sx-hicon{flex:none;color:#0a5a61}
  .sx-herobtn .sx-htext{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .sx-herobtn .sx-hk{flex:none;font-size:12px;color:#3d4b5a;background:#eef1f6;border-radius:6px;padding:3px 9px;font-weight:700}
  .sx-herohint{color:#cdd9e8;font-size:13px;margin:11px 0 0;line-height:1.55}
  .sx-herochips{display:flex;flex-wrap:wrap;gap:8px;margin-top:9px}
  .sx-herochips .sx-try{color:#9fb3cc;font-size:12.5px;align-self:center;margin-right:1px}
  .sx-herochip{background:rgba(255,255,255,.13);border:1px solid rgba(255,255,255,.34);color:#fff;border-radius:999px;
    padding:7px 13px;font:inherit;font-size:13px;font-weight:600;cursor:pointer;min-height:38px}
  .sx-herochip:hover{background:rgba(255,255,255,.24)}
  .sx-herobtn:focus-visible,.sx-herochip:focus-visible{outline:3px solid #9fe1e8;outline-offset:2px}
  @media(max-width:560px){.sx-herobtn .sx-hk{display:none}}
  .sx-ov{position:fixed;inset:0;background:rgba(13,36,64,.55);opacity:0;pointer-events:none;transition:opacity .15s;z-index:300;backdrop-filter:blur(3px)}
  .sx-ov.open{opacity:1;pointer-events:auto}
  .sx-modal{position:fixed;left:50%;top:54px;transform:translate(-50%,-8px);width:min(680px,94vw);max-height:84vh;
    background:var(--card,#fff);border:1px solid var(--line,#d8dfe8);border-radius:15px;z-index:301;
    box-shadow:0 18px 60px rgba(16,29,46,.32);display:flex;flex-direction:column;opacity:0;pointer-events:none;
    transition:opacity .15s,transform .15s;overflow:hidden}
  .sx-modal.open{opacity:1;pointer-events:auto;transform:translate(-50%,0)}
  .sx-inbar{display:flex;align-items:center;gap:10px;padding:13px 16px;border-bottom:1px solid var(--line,#d8dfe8)}
  .sx-inbar svg{flex:none}
  .sx-in{flex:1;font:inherit;font-size:17px;border:0;outline:none;background:transparent;color:var(--ink,#10202f);min-width:0}
  .sx-x{background:#eef1f6;border:1px solid var(--line,#d8dfe8);border-radius:8px;width:40px;height:40px;font-size:18px;
    cursor:pointer;color:var(--ink,#10202f);flex:none;line-height:1}
  .sx-x:hover{background:#e2e7ef}
  .sx-body{overflow-y:auto;padding:8px}
  .sx-hint{padding:14px 12px;color:var(--muted,#3d4b5a);font-size:13.5px;line-height:1.5}
  .sx-grouplbl{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted,#3d4b5a);font-weight:700;padding:10px 12px 4px}
  .sx-opt{display:flex;align-items:center;gap:12px;width:100%;text-align:left;background:none;border:0;font:inherit;
    padding:10px 12px;border-radius:10px;cursor:pointer;color:var(--ink,#10202f)}
  .sx-opt:hover,.sx-opt.sx-act{background:#eaf3f3}
  .sx-opt .sx-ic{flex:none;width:34px;height:34px;border-radius:9px;display:grid;place-items:center;font-size:15px;font-weight:800;background:#eef3f6}
  .sx-opt .sx-nm{flex:1;min-width:0}
  .sx-opt .sx-nm b{display:block;font-weight:650;font-size:14.5px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .sx-opt .sx-nm span{display:block;font-size:12px;color:var(--muted,#3d4b5a);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .sx-opt .sx-amt{flex:none;font-weight:700;font-variant-numeric:tabular-nums;color:var(--teal,#0a5a61);font-size:13.5px}
  .sx-chip{display:inline-block;font-size:10.5px;font-weight:700;padding:2px 8px;border-radius:999px;background:#eef3f6;color:var(--muted,#3d4b5a);white-space:nowrap}
  /* profile view */
  .sx-prof{padding:6px 18px 22px}
  .sx-back{display:inline-flex;align-items:center;gap:6px;background:none;border:0;color:var(--teal,#0a5a61);
    font:inherit;font-weight:650;cursor:pointer;padding:8px 4px;min-height:40px}
  .sx-ph{margin:4px 0 2px;font-size:21px;font-weight:760;line-height:1.2}
  .sx-roles{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0 4px}
  .sx-loc{display:flex;align-items:flex-start;gap:7px;font-size:13.5px;color:var(--ink,#10202f);margin:8px 0 2px;line-height:1.4}
  .sx-loc svg{flex:none;margin-top:2px;color:var(--teal,#0a5a61)}
  .sx-loc .sx-addr{color:var(--muted,#3d4b5a);font-size:12.5px}
  .sx-sec{margin-top:16px}
  .sx-sec h5{margin:0 0 8px;font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--muted,#3d4b5a);font-weight:700}
  .sx-grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 16px;background:#f4f6f9;border:1px solid var(--line,#d8dfe8);border-radius:12px;padding:14px}
  .sx-grid .sx-v{font-size:19px;font-weight:760}
  .sx-grid .sx-k{font-size:11.5px;color:var(--muted,#3d4b5a);margin-top:1px}
  .sx-rows{border:1px solid var(--line,#d8dfe8);border-radius:11px;overflow:hidden}
  .sx-row{display:flex;align-items:center;gap:12px;width:100%;text-align:left;background:#fff;border:0;border-top:1px solid var(--line,#d8dfe8);
    font:inherit;padding:10px 13px;cursor:default;color:var(--ink,#10202f)}
  .sx-row:first-child{border-top:0}
  button.sx-row{cursor:pointer}button.sx-row:hover{background:#eaf3f3}
  .sx-row .sx-rv{flex:none;font-weight:700;color:var(--teal,#0a5a61);font-variant-numeric:tabular-nums;min-width:64px}
  .sx-row .sx-rn{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis}
  .sx-row .sx-rn small{color:var(--muted,#3d4b5a)}
  .sx-cta{display:inline-flex;align-items:center;gap:7px;margin-top:16px;background:var(--teal,#0a5a61);color:#fff;
    border:0;border-radius:10px;padding:0 16px;min-height:46px;font:inherit;font-weight:700;cursor:pointer;text-decoration:none}
  .sx-cta:hover{filter:brightness(1.08)}
  .sx-cta.sec{background:#eef3f6;color:var(--teal,#0a5a61);border:1px solid var(--line,#d8dfe8)}
  .sx-note{font-size:12px;color:var(--muted,#3d4b5a);margin-top:14px;line-height:1.5}
  .sx-aud{background:#f4f6f9;border:1px solid var(--line,#d8dfe8);border-radius:11px;padding:12px 14px;margin-bottom:9px}
  .sx-aud .sx-audh{font-weight:700;font-size:14px}
  .sx-aud .sx-audm{font-size:12.5px;color:var(--muted,#3d4b5a);margin:2px 0 10px;font-variant-numeric:tabular-nums}
  .sx-aud .sx-cta{min-height:40px}
  .sx-audlinks{display:flex;flex-wrap:wrap;gap:8px 16px;margin-top:6px;font-size:13px}
  .sx-dl{font-size:13px;font-weight:700;margin-top:10px}
  @media(prefers-reduced-motion:reduce){.sx-ov,.sx-modal{transition:none}}
  @media(max-width:560px){.sx-modal{top:0;left:0;transform:none;width:100vw;max-height:100vh;height:100vh;border-radius:0}
    .sx-modal.open{transform:none}.sx-grid{grid-template-columns:1fr}}
  `;

  // type icon glyphs
  var GL = { org: 'O', district: '◆', project: '▤', donor: '$', account: '▦', sector: '◷', source: '⛭', audit: '✓' };
  var ICCOL = { org: '#0a5a61', district: '#8f1f1a', project: '#1d4ed8', donor: '#7a4708', account: '#475569', sector: '#0a5e2f', source: '#475569', audit: '#0a5e2f' };

  // ---- DOM ----
  var ov, modal, input, body, lastFocus, mode = 'search', curResults = [], actIdx = -1, curEntity = null;
  function build() {
    var st = document.createElement('style'); st.textContent = CSS; document.head.appendChild(st);
    ov = document.createElement('div'); ov.className = 'sx-ov'; ov.addEventListener('click', close);
    modal = document.createElement('div'); modal.className = 'sx-modal'; modal.setAttribute('role', 'dialog');
    modal.setAttribute('aria-modal', 'true'); modal.setAttribute('aria-label', L().open);
    modal.innerHTML =
      '<div class="sx-inbar">' +
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="' + (ICCOL.org) + '" stroke-width="2.2" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>' +
        '<input class="sx-in" type="text" role="combobox" aria-expanded="true" aria-autocomplete="list" aria-controls="sx-list" autocomplete="off" spellcheck="false">' +
        '<button class="sx-x" type="button" aria-label="' + esc(L().close) + '">×</button>' +
      '</div>' +
      '<div class="sx-body" id="sx-list" role="listbox" aria-label="' + esc(L().open) + '"></div>';
    input = modal.querySelector('.sx-in'); body = modal.querySelector('#sx-list');
    modal.querySelector('.sx-x').addEventListener('click', close);
    input.placeholder = L().ph;
    input.addEventListener('input', function () { mode = 'search'; render(); });
    input.addEventListener('keydown', onKey);
    document.body.appendChild(ov); document.body.appendChild(modal);
    // re-render on language flip
    new MutationObserver(function () { if (ov.classList.contains('open')) { input.placeholder = L().ph; render(); } })
      .observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
  }

  function open() {
    lastFocus = document.activeElement;
    input.placeholder = L().ph;                 // pick up any language change made while closed
    modal.setAttribute('aria-label', L().open);
    ov.classList.add('open'); modal.classList.add('open');
    document.body.style.overflow = 'hidden';
    mode = 'search'; render(); input.focus();
  }
  function close() {
    ov.classList.remove('open'); modal.classList.remove('open');
    document.body.style.overflow = '';
    input.value = ''; curEntity = null; mode = 'search';
    if (location.hash.indexOf('#find=') === 0) history.replaceState(null, '', location.pathname + location.search);
    var back = (lastFocus && lastFocus.focus && lastFocus !== document.body) ? lastFocus : document.getElementById('sx-open');
    if (back && back.focus) back.focus();
  }

  function onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); if (mode === 'profile') { mode = 'search'; render(); input.focus(); } else close(); return; }
    if (mode !== 'search') return;
    if (e.key === 'ArrowDown') { e.preventDefault(); move(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); move(-1); }
    else if (e.key === 'Enter') { e.preventDefault(); if (curResults[actIdx]) openEntity(curResults[actIdx]); }
  }
  function move(d) {
    if (!curResults.length) return;
    actIdx = (actIdx + d + curResults.length) % curResults.length;
    paintActive();
    var el = body.querySelector('[data-ri="' + actIdx + '"]');
    if (el) el.scrollIntoView({ block: 'nearest' });
  }
  function paintActive() {
    body.querySelectorAll('.sx-opt').forEach(function (o) {
      var on = +o.dataset.ri === actIdx;
      o.classList.toggle('sx-act', on); o.setAttribute('aria-selected', on ? 'true' : 'false');
      if (on) input.setAttribute('aria-activedescendant', o.id);
    });
  }

  // trap Tab inside the modal
  document.addEventListener('keydown', function (e) {
    if (!ov || !ov.classList.contains('open') || e.key !== 'Tab') return;
    var f = [].slice.call(modal.querySelectorAll('input,button,a[href],[tabindex]:not([tabindex="-1"])'))
      .filter(function (el) { return el.offsetParent !== null && !el.disabled; });
    if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  });

  // ---- rendering: search results ----
  function render() {
    if (mode === 'profile' && curEntity) return renderProfile(curEntity);
    var t = L(), q = input.value;
    curResults = run(q); actIdx = curResults.length ? 0 : -1;
    if (!q) {
      var top = IDX.filter(function (e) { return e.t === 'org' || e.t === 'district' || e.t === 'donor'; }).slice(0, 6);
      body.innerHTML = '<div class="sx-hint">' + esc(t.empty) + '</div>' +
        '<div class="sx-grouplbl">' + esc(t.sug) + '</div>' + top.map(optHTML).join('');
      curResults = top; wireOpts(); return;
    }
    if (!curResults.length) {
      body.innerHTML = '<div class="sx-hint">' + esc(t.no) + ' “' + esc(q) + '”.</div>';
      return;
    }
    body.innerHTML = '<div class="sx-grouplbl">' + t.count.replace('{n}', curResults.length) + '</div>' +
      curResults.map(optHTML).join('');
    wireOpts(); paintActive();
  }
  function optHTML(e, i) {
    var t = L();
    var sub = e.t === 'org'
      ? (e.p.roles || []).map(function (r) { return t.roles[r]; }).join(' · ') +
        (e.loc && e.loc.country ? ' · ' + countryName(e.loc.country) : '')
      : (e.t === 'district' && e.ne ? e.ne + ' · ' + t.types.district : t.types[e.t]);
    var amt = e.a > 0 ? money(e.a) : '';
    return '<button type="button" class="sx-opt" role="option" id="sx-o' + i + '" data-ri="' + i + '" aria-selected="false">' +
      '<span class="sx-ic" style="color:' + ICCOL[e.t] + '">' + GL[e.t] + '</span>' +
      '<span class="sx-nm"><b>' + esc(e.n) + '</b><span>' + esc(sub || t.types[e.t]) + '</span></span>' +
      (amt ? '<span class="sx-amt">' + amt + '</span>' : '') + '</button>';
  }
  function wireOpts() {
    body.querySelectorAll('.sx-opt').forEach(function (o) {
      o.addEventListener('click', function () { openEntity(curResults[+o.dataset.ri]); });
      o.addEventListener('mousemove', function () { actIdx = +o.dataset.ri; paintActive(); });
    });
  }

  function openEntity(e) {
    if (!e) return;
    curEntity = e; mode = 'profile';
    history.replaceState(null, '', '#find=' + encodeURIComponent(e.i));
    renderProfile(e); body.scrollTop = 0;
    var b = body.querySelector('.sx-back'); if (b) b.focus();
  }

  // ---- rendering: entity profile (the "specific page" for that entity) ----
  function renderProfile(e) {
    var t = L(), p = e.p || {}, h = '';
    h += '<button type="button" class="sx-back">‹ ' + esc(t.back) + '</button>';
    h += '<div class="sx-prof">';
    h += '<div class="sx-ph">' + esc(e.n) + '</div>';

    if (e.t === 'org') {
      var roles = (p.roles || []).map(function (r) { return '<span class="sx-chip">' + esc(t.roles[r]) + '</span>'; }).join('');
      h += '<div class="sx-roles">' + roles + '</div>';
      h += locLine(e.loc);
      if (p.prime) {
        h += sec(t.as_prime,
          grid([[money(p.prime.out), t.outlayed], [money(p.prime.obl), t.obligated],
                [money(p.prime.onward), t.onward], [p.prime.n + ' ' + t.awards, t.types.project + 's']]) +
          rows((p.prime.aw || []).map(function (a) {
            var when = (a.s ? L().awarded + ' ' + a.s + ' · ' : '') + dlText(a.e);
            return { v: money(a.o != null ? a.o : a.b), n: a.j, sub: when, act: a.w, kind: 'proj' };
          })));
      }
      if (p.sub) {
        h += sec(t.as_sub,
          '<div class="sx-note" style="margin-top:0;margin-bottom:10px"><b style="color:var(--ink)">' + money(p.sub.recv) + '</b> ' +
            esc(t.received.toLowerCase()) + ' ' + esc(t.across) + ' ' + p.sub.n + ' ' + esc(t.subawards) + '.</div>' +
          (p.sub.from && p.sub.from.length ? subhead(t.funders) + rows(p.sub.from.map(mapNA)) : '') +
          (p.sub.dist && p.sub.dist.length ? subhead(t.districts_l) + rows(p.sub.dist.map(mapNA)) : '') +
          (p.sub.proj && p.sub.proj.length ? subhead(t.projects_l) + rows(p.sub.proj.map(mapNA)) : ''));
      }
      h += renderAudit(e);
    }

    else if (e.t === 'district') {
      if (e.ne) h += '<div class="sx-roles"><span class="sx-chip">' + esc(e.ne) + '</span><span class="sx-chip">' + esc(t.types.district) + '</span></div>';
      h += '<div class="sx-note" style="margin:6px 0 0"><b style="color:var(--ink);font-size:15px">' + money(p.landed) + '</b> ' +
        esc(t.across) + ' ' + p.n + ' ' + esc(t.subawards) + '.</div>';
      h += sec(t.orgs_l, rows((p.orgs || []).map(mapNA)));
      if (p.primes && p.primes.length) h += sec(t.primes_l, rows(p.primes.map(mapNA)));
    }

    else if (e.t === 'project') {
      if (!p.light) {
        h += sec('', grid([[money(p.o), t.outlayed], [money(p.b), t.obligated], [money(p.c), t.current], [money(p.pt), t.potential]]) +
          (p.s ? '<div class="sx-dl" style="color:var(--ink)">' + esc(t.awarded) + ': ' + esc(p.s) + '</div>' : '') +
          '<div class="sx-dl" style="color:' + (p.e && p.e < TODAY ? '#a51328' : 'var(--ink)') + '">' + dlText(p.e) + '</div>');
        h += metaList([[t.recipient, p.rec], [t.based_in, locText(p.loc)], [t.agency, p.ag], [t.status, t.stat[p.st] || p.st]]);
        if (p.subs && p.subs.length) h += sec(t.subs_l, rows(p.subs.map(mapNA)));
        if (p.dist && p.dist.length) h += sec(t.districts_l, rows(p.dist.map(mapNA)));
      } else {
        h += sec('', grid([[money(p.b), t.obligated]]));
        h += metaList([[t.recipient, p.rec], [t.based_in, locText(p.loc)], [t.agency, p.ag], [t.status, t.stat[p.st] || p.st]]);
      }
      if (p.link) h += '<div><a class="sx-cta sec" href="' + esc(p.link) + '" target="_blank" rel="noopener">' + esc(t.open_record) + ' ↗</a></div>';
    }

    else if (e.t === 'donor') {
      if (p.nondac) h += '<div class="sx-roles"><span class="sx-chip">' + esc(t.nondac) + '</span></div>';
      if (p.latest_usd != null) h += '<div class="sx-note" style="margin:6px 0 0"><b style="color:var(--ink);font-size:15px">' + money(p.latest_usd) + '</b> · ' + esc(t.latest) + (p.year ? ' (' + p.year + ')' : '') + '</div>';
      if (p.series && p.series.length) h += sec(t.latest, rows(p.series.slice().reverse().map(function (r) { return { v: '$' + r.m + 'm', n: r.y }; })));
      if (p.note) h += '<div class="sx-note">' + esc(p.note) + '</div>';
    }

    else if (e.t === 'account') {
      h += sec('', grid([['$' + p.ob + 'm', t.obligated], ['$' + p.di + 'm', t.delivered], [p.rate + '%', t.rate], [esc(p.ag), t.agency]]));
    }
    else if (e.t === 'sector') {
      h += sec('', grid([[money(p.usd), t.types.sector], [p.year, t.year]]));
      if (p.side) h += '<div class="sx-note">' + esc(p.side) + '</div>';
    }
    else if (e.t === 'source') {
      h += '<div class="sx-roles"><span class="sx-chip">' + esc(p.side) + '</span><span class="sx-chip">' + esc(p.status) + '</span></div>';
      if (p.url) h += '<div><a class="sx-cta sec" href="' + esc(p.url) + '" target="_blank" rel="noopener">' + esc(t.view_source) + ' ↗</a></div>';
    }
    else if (e.t === 'audit') {
      h += sec('', grid([[money(p.q), t.questioned], [esc(p.verdict), t.verdict]]));
      if (p.period) h += '<div class="sx-note">' + esc(p.period) + '</div>';
      if (p.url) h += '<div><a class="sx-cta sec" href="' + esc(p.url) + '" target="_blank" rel="noopener">' + esc(t.open_report) + ' ↗</a></div>';
    }

    // primary cross-page / drill CTA
    var cta = primaryCTA(e);
    if (cta) h += '<div style="margin-top:4px">' + cta + '</div>';
    h += '<div class="sx-note">' + sourceNote(e) + '</div>';
    h += '</div>';
    body.innerHTML = h;

    body.querySelector('.sx-back').addEventListener('click', function () { mode = 'search'; render(); input.focus(); });
    body.querySelectorAll('button.sx-row[data-proj]').forEach(function (b) {
      b.addEventListener('click', function () { drillTo('proj', b.dataset.proj, b.dataset.label); });
    });
    var dr = body.querySelector('[data-drill]');
    if (dr) dr.addEventListener('click', function () { drillTo(dr.dataset.drill, dr.dataset.key, dr.dataset.label); });
  }

  // Financial accountability: confirmed Single Audit + OIG audits + always-available lookups.
  function fmtEin(x) { return (x && x.length === 9) ? x.slice(0, 2) + '-' + x.slice(2) : (x || ''); }
  function renderAudit(e) {
    var t = L(), a = e.audit || {}, name = e.n, isPrime = e.p && e.p.prime;
    if (!a.fac && !a.oig && !isPrime) return '';   // nothing meaningful for foreign-only sub-recipients
    var facSearch = 'https://app.fac.gov/dissemination/search/?query=' + encodeURIComponent(name);
    var usas = 'https://www.usaspending.gov/search?keyword=' + encodeURIComponent(name);
    var inner = '';
    if (a.fac) {
      var f = a.fac, url = f.summary || facSearch;
      inner += '<div class="sx-aud"><div class="sx-audh">' + esc(t.single_audit) + ' — FY' + esc(f.year) + '</div>' +
        '<div class="sx-audm">' + esc(t.ein) + ' ' + esc(fmtEin(f.ein)) +
        (f.auditee && norm(f.auditee) !== norm(name) ? ' · ' + esc(f.auditee) : '') + '</div>' +
        '<a class="sx-cta sec" href="' + url + '" target="_blank" rel="noopener">' + esc(t.fac_view) + ' ↗</a></div>';
    }
    (a.oig || []).forEach(function (o) {
      inner += '<div class="sx-aud"><div class="sx-audh">' + esc(t.oig_audit) + ' · ' + esc(o.report) + '</div>' +
        '<div class="sx-audm">' + (o.questioned > 0 ? esc(t.questioned) + ': ' + money(o.questioned) + ' · ' : '') + esc(o.verdict) + '</div>' +
        '<a class="sx-cta sec" href="' + esc(o.url) + '" target="_blank" rel="noopener">' + esc(t.open_report) + ' ↗</a></div>';
    });
    inner += '<div class="sx-audlinks">' +
      '<a href="' + facSearch + '" target="_blank" rel="noopener">' + esc(t.fac_lookup) + ' ↗</a>' +
      '<a href="' + usas + '" target="_blank" rel="noopener">' + esc(t.usas_rec) + ' ↗</a></div>' +
      '<div class="sx-note">' + esc(t.sa_note) + '</div>';
    return sec(t.acct_title, inner);
  }
  function norm(s) { return String(s || '').toUpperCase().replace(/[^A-Z0-9 ]/g, ' ').replace(/\b(INC|INCORPORATED|LLC|LTD|LIMITED|CORP|CORPORATION|CO|PVT|PRIVATE|THE|AND|OF|A)\b/g, ' ').replace(/\s+/g, ' ').trim(); }

  // section + helpers
  function sec(title, inner) { return '<div class="sx-sec">' + (title ? '<h5>' + esc(title) + '</h5>' : '') + inner + '</div>'; }
  function subhead(s) { return '<h5 style="margin:14px 0 6px">' + esc(s) + '</h5>'; }
  function grid(pairs) {
    return '<div class="sx-grid">' + pairs.map(function (p) {
      return '<div><div class="sx-v">' + p[0] + '</div><div class="sx-k">' + esc(p[1]) + '</div></div>';
    }).join('') + '</div>';
  }
  function metaList(pairs) {
    return '<div class="sx-note" style="margin-top:12px">' + pairs.filter(function (p) { return p[1]; })
      .map(function (p) { return '<div><b style="color:var(--ink)">' + esc(p[0]) + ':</b> ' + esc(p[1]) + '</div>'; }).join('') + '</div>';
  }
  function mapNA(r) { return { v: money(r.a), n: r.n }; }
  function rows(list) {
    if (!list || !list.length) return '';
    return '<div class="sx-rows">' + list.map(function (r) {
      var clickable = r.kind === 'proj' && PAGE === 'us' && window.drillProj;
      var tag = clickable ? 'button' : 'div';
      var attr = clickable ? ' data-proj="' + esc(r.act) + '" data-label="' + esc(r.n) + '"' : '';
      var lc = LOCBYNAME[norm(r.n)];      // show the counterparty's country when we know it
      var cc = lc && lc.country ? ' <small>· ' + esc(countryName(lc.country)) + '</small>' : '';
      return '<' + tag + ' class="sx-row"' + attr + (clickable ? ' type="button"' : '') + '>' +
        '<span class="sx-rv">' + r.v + '</span><span class="sx-rn">' + esc(r.n) + cc +
        (r.sub ? ' <small>· ' + esc(r.sub) + '</small>' : '') + '</span></' + tag + '>';
    }).join('') + '</div>';
  }
  function dlText(d) {
    var t = L();
    if (!d) return t.dl_none;
    return (d < TODAY ? t.dl_passed + ': ' : t.dl_until + ' ') + d;
  }

  function primaryCTA(e) {
    var t = L();
    // same page + a live drill available -> open the rich drawer
    if (PAGE === 'us' && e.g === 'us') {
      if (e.t === 'district' && window.drillDist) return drillBtn('dist', e.n, '', t.open_ledger);
      if (e.t === 'org') {
        if (e.p.prime && e.p.prime.aw && e.p.prime.aw.length && window.drillProj)
          return drillBtn('proj', e.p.prime.aw[0].w, e.p.prime.aw[0].j, t.open_ledger);
        if (e.p.sub && e.p.sub.sname && window.drillSub) return drillBtn('sub', e.p.sub.sname, '', t.open_ledger);
      }
      if (e.t === 'project' && e.d && window.drillProj) return drillBtn('proj', e.d, e.n, t.open_ledger);
    }
    // other page -> deep-link that auto-opens this profile there
    if (e.g !== PAGE) {
      var label = e.g === 'us' ? t.open_us : t.open_main;
      return '<a class="sx-cta" href="' + OTHER + '#find=' + encodeURIComponent(e.i) + '">' + esc(label) + ' →</a>';
    }
    if (e.h) return '<a class="sx-cta" href="' + e.h + '">' + esc(PAGE === 'us' ? t.open_us : t.open_main) + '</a>';
    return '';
  }
  function drillBtn(kind, key, label, text) {
    return '<button type="button" class="sx-cta" data-drill="' + esc(kind) + '" data-key="' + esc(key) +
      '" data-label="' + esc(label) + '">' + esc(text) + '</button>';
  }
  function drillTo(kind, key, label) {
    close();
    setTimeout(function () {
      if (kind === 'proj' && window.drillProj) window.drillProj(key, label || key);
      else if (kind === 'sub' && window.drillSub) window.drillSub(key);
      else if (kind === 'dist' && window.drillDist) window.drillDist(key);
    }, 60);
  }
  function sourceNote(e) {
    var map = { org: 'USAspending sub-award + award data', district: 'USAspending sub-award data', project: 'ForeignAssistance.gov + USAspending', donor: 'OECD / Nepal DCR', account: 'ForeignAssistance.gov', sector: 'OECD DAC', source: 'Source registry', audit: 'USAID OIG' };
    return 'Source: ' + (map[e.t] || 'dashboard data') + '.';
  }

  // ---- triggers + deep-link ----
  function mountTrigger() {
    var langEl = document.querySelector('header .lang');
    var btn = document.createElement('button');
    btn.id = 'sx-open'; btn.type = 'button'; btn.className = 'sx-trigger';
    btn.setAttribute('aria-haspopup', 'dialog');
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>' +
      '<span class="sx-lbl">' + esc(L().open) + '</span><span class="sx-kbd">/</span>';
    btn.addEventListener('click', open);
    if (langEl && langEl.parentNode) langEl.parentNode.insertBefore(btn, langEl);
    else document.querySelector('header .hbar').appendChild(btn);
    // keep label localized
    new MutationObserver(function () { btn.querySelector('.sx-lbl').textContent = L().open; })
      .observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
  }
  function openWith(q) { open(); input.value = q; mode = 'search'; render(); }

  // Prominent, central search in the hero + a teaching line + example chips.
  var EXAMPLES = PAGE === 'us'
    ? ['Save the Children', 'Helen Keller', 'Early Grade Reading', 'Surkhet']
    : ['World Bank', 'India', 'Education', 'Save the Children'];
  function mountHero() {
    var host = document.getElementById('sx-hero');
    if (!host) return;
    function paint() {
      var t = L();
      host.className = 'sx-hero';
      host.innerHTML =
        '<button type="button" class="sx-herobtn" id="sx-herobtn" aria-haspopup="dialog">' +
          '<svg class="sx-hicon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.3" aria-hidden="true"><circle cx="11" cy="11" r="7"/><line x1="21" y1="21" x2="16.5" y2="16.5"/></svg>' +
          '<span class="sx-htext">' + esc(t.ph) + '</span><span class="sx-hk">/</span>' +
        '</button>' +
        '<p class="sx-herohint">' + esc(t.findhint) + '</p>' +
        '<div class="sx-herochips"><span class="sx-try">' + esc(t.sug) + ':</span>' +
          EXAMPLES.map(function (x) { return '<button type="button" class="sx-herochip">' + esc(x) + '</button>'; }).join('') +
        '</div>';
      host.querySelector('#sx-herobtn').addEventListener('click', open);
      host.querySelectorAll('.sx-herochip').forEach(function (b) {
        b.addEventListener('click', function () { openWith(b.textContent); });
      });
    }
    paint();
    new MutationObserver(paint).observe(document.documentElement, { attributes: true, attributeFilter: ['lang'] });
  }

  function globalKeys(e) {
    if ((e.key === 'k' || e.key === 'K') && (e.metaKey || e.ctrlKey)) { e.preventDefault(); ov.classList.contains('open') ? close() : open(); return; }
    var tag = (document.activeElement && document.activeElement.tagName) || '';
    if (e.key === '/' && !ov.classList.contains('open') && !/INPUT|TEXTAREA|SELECT/.test(tag)) { e.preventDefault(); open(); }
  }
  function maybeDeepLink() {
    var m = /^#find=(.+)$/.exec(location.hash);
    if (!m) return;
    var id = decodeURIComponent(m[1]);
    var e = IDX.find(function (x) { return x.i === id; });
    if (e) { open(); openEntity(e); }
  }

  function init() {
    if (!IDX.length) return;
    // On the deep-dive page, search_index_us.js adds the heavy profiles (sub-recipient,
    // award and district lists). Merge them onto the slim core entries. The main board
    // ships only the headline scalars and reaches the full profile via the #find deep-link.
    if (window.SEARCH_US) {
      for (var j = 0; j < IDX.length; j++) {
        var full = window.SEARCH_US[IDX[j].i];
        if (full) IDX[j].p = full;
      }
    }
    // Look up an organisation's location by name, so counterparty lists (a project's
    // sub-recipients, a district's partners) can show where each one is based too.
    IDX.forEach(function (e) {
      if (e.t === 'org' && e.loc && e.loc.country) {
        [e.n].concat(e.k || []).forEach(function (nm) {
          var k = norm(nm); if (k && !LOCBYNAME[k]) LOCBYNAME[k] = e.loc;
        });
      }
    });
    build(); mountTrigger(); mountHero();
    document.addEventListener('keydown', globalKeys);
    window.addEventListener('hashchange', maybeDeepLink);
    maybeDeepLink();
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
