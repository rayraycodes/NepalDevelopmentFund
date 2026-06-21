// Builds the Government-of-Nepal briefing deck. Palette matches the dashboards.
const pptxgen = require("pptxgenjs");
const p = new pptxgen();
p.defineLayout({ name: "W", width: 13.333, height: 7.5 });
p.layout = "W";
p.author = "Nepal Development Funding dataset";

const NAVY = "0D2440", INK = "12233B", CRIMSON = "C0152F", TEAL = "0E7C86",
      AMBER = "E08A00", BG = "F4F6F9", CARD = "FFFFFF", MUTE = "5B6B7D",
      LINE = "DDE4EC", ICE = "CADCFC", WHITE = "FFFFFF";
const HF = "Georgia", BFONT = "Calibri";
const W = 13.333, H = 7.5;

// ---- helpers ----
function darkBase(s){ s.background = { color: NAVY }; }
function lightBase(s){
  s.background = { color: BG };
  s.addShape(p.ShapeType.rect, { x:0, y:0, w:0.18, h:H, fill:{color:CRIMSON} });
}
function tag(s, en, ne){
  s.addText([{text:en+"  ", options:{bold:true}},{text:ne, options:{color:TEAL}}], {
    x:0.55, y:0.42, w:9, h:0.4, fontFace:BFONT, fontSize:12, color:CRIMSON, charSpacing:2 });
}
function title(s, txt, y=0.85, w=11.8){
  s.addText(txt, { x:0.52, y, w, h:1.0, fontFace:HF, fontSize:33, bold:true, color:INK });
}
function foot(s, n){
  s.addText("External Development Funding to Nepal  ·  built from primary sources, retrieved 2026",
    { x:0.55, y:7.04, w:9.8, h:0.3, fontFace:BFONT, fontSize:9, color:MUTE });
  s.addText(String(n), { x:12.4, y:7.0, w:0.6, h:0.3, fontFace:BFONT, fontSize:10, color:MUTE, align:"right" });
}
function statCard(s, x, y, w, big, label, accent){
  const h=1.85;
  s.addShape(p.ShapeType.roundRect, { x, y, w, h, rectRadius:0.08, fill:{color:CARD}, line:{color:LINE, width:1}, shadow:{type:"outer", blur:9, offset:2, angle:90, opacity:0.10, color:"8895A7"} });
  s.addShape(p.ShapeType.rect, { x:x+0.0, y:y+0.32, w:0.07, h:h-0.64, fill:{color:accent} });
  s.addText(big, { x:x+0.28, y:y+0.18, w:w-0.5, h:0.95, fontFace:HF, fontSize:34, bold:true, color:accent, valign:"middle" });
  s.addText(label, { x:x+0.28, y:y+1.04, w:w-0.45, h:0.66, fontFace:BFONT, fontSize:12.5, color:INK, valign:"top" });
}
function iconRow(s, x, y, w, num, head, body, accent){
  s.addShape(p.ShapeType.ellipse, { x, y, w:0.62, h:0.62, fill:{color:accent} });
  s.addText(num, { x, y, w:0.62, h:0.62, align:"center", valign:"middle", fontFace:HF, fontSize:22, bold:true, color:WHITE });
  s.addText(head, { x:x+0.85, y:y-0.04, w:w-0.95, h:0.42, fontFace:BFONT, fontSize:17, bold:true, color:INK });
  s.addText(body, { x:x+0.85, y:y+0.40, w:w-0.95, h:1.0, fontFace:BFONT, fontSize:13, color:MUTE, lineSpacingMultiple:1.02 });
}

// ===== 1. TITLE =====
let s = p.addSlide(); darkBase(s);
s.addShape(p.ShapeType.rect, { x:0, y:0, w:W, h:0.16, fill:{color:CRIMSON} });
s.addShape(p.ShapeType.rect, { x:0, y:0.16, w:W, h:0.06, fill:{color:TEAL} });
s.addText([{text:"नेपाल  ·  ", options:{color:ICE}},{text:"NEPAL", options:{color:WHITE,bold:true}}],
  { x:0.7, y:1.5, w:11, h:0.5, fontFace:BFONT, fontSize:15, charSpacing:5 });
s.addText("External Development Funding to Nepal", { x:0.7, y:2.25, w:12, h:1.5, fontFace:HF, fontSize:46, bold:true, color:WHITE, lineSpacingMultiple:1.0 });
s.addText("A verifiable, sovereign record of who funds Nepal, what they deliver, and what for.",
  { x:0.72, y:3.95, w:11.2, h:0.8, fontFace:BFONT, fontSize:19, color:ICE });
s.addText([
  {text:"Why", options:{color:WHITE,bold:true}}, {text:"  this matters   ", options:{color:"8FA6C4"}},
  {text:"What", options:{color:WHITE,bold:true}}, {text:"  we built   ", options:{color:"8FA6C4"}},
  {text:"How", options:{color:WHITE,bold:true}}, {text:"  it stays trustworthy", options:{color:"8FA6C4"}},
], { x:0.72, y:5.5, w:11, h:0.5, fontFace:BFONT, fontSize:16 });
s.addText("A briefing for the Government of Nepal", { x:0.72, y:6.55, w:11, h:0.4, fontFace:BFONT, fontSize:13, italic:true, color:"8FA6C4" });

// ===== 2. WHY — the problem =====
s = p.addSlide(); lightBase(s); tag(s, "WHY", "किन"); title(s, "When the data goes dark, accountability does too");
s.addText("Two things make foreign aid hard for Nepal to see clearly:", { x:0.55, y:1.95, w:11.5, h:0.4, fontFace:BFONT, fontSize:15, color:MUTE });
iconRow(s, 0.7, 2.7, 5.9, "1", "The record is borrowed, not owned",
  "Aid data lives on donor websites. When USAID was dissolved in 2025, its site went offline and Nepal lost the record of assistance it had received. Dependence on a foreign portal is a sovereignty risk.", CRIMSON);
iconRow(s, 0.7, 4.55, 5.9, "2", "The two sides of the ledger disagree",
  "What donors report giving and what Nepal reports receiving differ by 7 to 33 percent every year. Without a reconciliation, planning rests on numbers nobody has squared.", TEAL);
// right visual: mini ledger mismatch
s.addShape(p.ShapeType.roundRect, { x:7.1, y:2.7, w:5.5, h:3.7, rectRadius:0.08, fill:{color:NAVY} });
s.addText("The gap, by year", { x:7.4, y:2.9, w:5, h:0.4, fontFace:BFONT, fontSize:13, bold:true, color:ICE });
const gaps = [["2017","+27%"],["2019","+48%"],["2021","-11%"],["2022","+14%"]];
let gy=3.5;
gaps.forEach(([yr,g])=>{
  s.addText(yr, { x:7.45, y:gy, w:1.2, h:0.4, fontFace:BFONT, fontSize:14, color:WHITE });
  s.addText("Nepal vs donor books "+g, { x:8.5, y:gy, w:3.9, h:0.4, fontFace:BFONT, fontSize:14, bold:true, color: g.startsWith("-")?"FF8A80":"9FE2C6", align:"right" });
  gy+=0.62;
});
s.addText("Nepal's own report is the more complete record: it captures China and India, which the international system omits.",
  { x:7.45, y:5.7, w:5.0, h:0.6, fontFace:BFONT, fontSize:11.5, italic:true, color:ICE });
foot(s,2);

// ===== 3. WHY — the cliff (stats) =====
s = p.addSlide(); lightBase(s); tag(s,"WHY","किन"); title(s,"And the ground just shifted under Nepal");
s.addText("The 2025 US restructuring is not a forecast. It is already measurable in the data.",
  { x:0.55, y:1.95, w:12, h:0.4, fontFace:BFONT, fontSize:15, color:MUTE });
statCard(s, 0.7, 2.7, 3.85, "-74%", "Fall in new US commitments in FY2025, the sharpest cut on record", CRIMSON);
statCard(s, 4.75, 2.7, 3.85, "248", "of 2,609 US awards ended inside the restructuring window", AMBER);
statCard(s, 8.8, 2.7, 3.85, "18 → 7", "Active US budget accounts for Nepal, FY2024 to FY2026", CRIMSON);
s.addShape(p.ShapeType.roundRect, { x:0.7, y:4.95, w:11.95, h:1.55, rectRadius:0.08, fill:{color:"FBEAEC"}, line:{color:"E7B6BD",width:1} });
s.addText([{text:"The pivot:  ", options:{bold:true, color:CRIMSON}},
  {text:"As USAID disappears, the $500m Millennium Challenge Corporation compact (power lines and roads, running to August 2028) becomes the dominant US channel. Nepal's leverage and obligations there now matter disproportionately.", options:{color:INK}}],
  { x:1.0, y:5.15, w:11.3, h:1.15, fontFace:BFONT, fontSize:15, valign:"middle", lineSpacingMultiple:1.05 });
foot(s,3);

// ===== 4. WHAT — what we built =====
s = p.addSlide(); lightBase(s); tag(s,"WHAT","के"); title(s,"A single, source-faithful record");
iconRow(s, 0.7, 2.2, 5.85, "A", "Both ledgers, compared",
  "Donor-side (OECD, World Bank, ADB, US, UN) set beside recipient-side (Nepal's own Development Cooperation Report). Compared, never merged, with every gap explained.", TEAL);
iconRow(s, 0.7, 4.0, 5.85, "B", "A US deep dive",
  "Down to the budget account, the sub-sector, the implementing partner, and all 2,609 individual projects, triaged by status.", NAVY);
iconRow(s, 0.7, 5.55, 5.85, "C", "The primary documents, archived",
  "The signed MCC compact, the recovered USAID strategy, ADB and World Bank frameworks, each saved with a checksum.", AMBER);
s.addShape(p.ShapeType.roundRect, { x:7.0, y:2.2, w:5.6, h:4.35, rectRadius:0.08, fill:{color:CARD}, line:{color:LINE,width:1} });
s.addText("Built for Nepal to use", { x:7.3, y:2.4, w:5, h:0.4, fontFace:BFONT, fontSize:14, bold:true, color:INK });
[["Bilingual","Full English / नेपाली, side by side"],
 ["Interactive","Search any project; switch any year"],
 ["Verifiable","Every figure links to its official source"],
 ["Resilient","Snapshots survive when source sites die"],
 ["Open","Clean CSVs anyone can re-check"]].forEach(([h,b],i)=>{
  const yy=2.95+i*0.72;
  s.addShape(p.ShapeType.ellipse,{x:7.32,y:yy+0.04,w:0.16,h:0.16,fill:{color:TEAL}});
  s.addText([{text:h+"  —  ",options:{bold:true,color:INK}},{text:b,options:{color:MUTE}}],
    {x:7.62,y:yy-0.06,w:4.85,h:0.5,fontFace:BFONT,fontSize:12.5});
});
foot(s,4);

// ===== 5. WHAT — where the money lands =====
s = p.addSlide(); lightBase(s); tag(s,"WHAT","के"); title(s,"Following each dollar to its purpose");
s.addText("Of US assistance to Nepal, 2015–2026 ($2.0 billion delivered):", { x:0.55, y:1.95, w:12, h:0.4, fontFace:BFONT, fontSize:15, color:MUTE });
const cols=[["82¢","of every promised dollar was actually delivered","Promise kept",TEAL],
            ["~50¢","reached people directly: nutrition, clinics, schools","To people",NAVY],
            ["18¢","ran the system itself: administration and oversight","To the machine",CRIMSON]];
cols.forEach((c,i)=>{
  const x=0.7+i*4.05;
  s.addShape(p.ShapeType.roundRect,{x,y:2.65,w:3.75,h:3.0,rectRadius:0.1,fill:{color:CARD},line:{color:LINE,width:1},shadow:{type:"outer",blur:9,offset:2,angle:90,opacity:0.1,color:"8895A7"}});
  s.addShape(p.ShapeType.rect,{x,y:2.65,w:3.75,h:0.12,fill:{color:c[3]}});
  s.addText(c[3]===TEAL?"GATE 1":(i===1?"GATE 2":"GATE 3"),{x:x+0.3,y:2.95,w:3,h:0.3,fontFace:BFONT,fontSize:11,bold:true,color:c[3],charSpacing:2});
  s.addText(c[0],{x:x+0.25,y:3.25,w:3.3,h:1.1,fontFace:HF,fontSize:52,bold:true,color:c[3]});
  s.addText(c[2],{x:x+0.3,y:4.45,w:3.2,h:0.4,fontFace:BFONT,fontSize:15,bold:true,color:INK});
  s.addText(c[1],{x:x+0.3,y:4.85,w:3.25,h:0.7,fontFace:BFONT,fontSize:12.5,color:MUTE});
});
s.addText("The 18¢ is only the visible overhead; what partners spend on their own administration inside program awards is not published anywhere. We say so, on the page.",
  { x:0.7, y:5.95, w:11.9, h:0.6, fontFace:BFONT, fontSize:12, italic:true, color:MUTE });
foot(s,5);

// ===== 5b. WHAT — where it landed =====
s = p.addSlide(); lightBase(s); tag(s,"WHAT","के"); title(s,"Following the money to where it landed");
s.addText("Big partners win the awards, but much is sub-granted onward — now traceable down to the district.",
  { x:0.55, y:1.95, w:12, h:0.4, fontFace:BFONT, fontSize:15, color:MUTE });
statCard(s, 0.7, 2.7, 3.85, "$1.06bn", "sub-granted onward from the largest projects — about half of what was obligated", TEAL);
statCard(s, 4.75, 2.7, 3.85, "562", "organisations received the money beneath the US primes", NAVY);
statCard(s, 8.8, 2.7, 3.85, "48 / 77", "of Nepal's districts named as where the work happened", AMBER);
s.addShape(p.ShapeType.roundRect, { x:0.7, y:4.95, w:11.95, h:1.55, rectRadius:0.08, fill:{color:"E9F4F3"}, line:{color:"BFD8D6",width:1} });
s.addText([{text:"On the live dashboard:  ", options:{bold:true, color:TEAL}},
  {text:"click any district — Achham, Surkhet, Kailali — to see the named local NGOs that received US money there, and which international partner passed it down (organisations like Social Empowerment & Building Accessibility Centre Nepal and Bahuuddeshiya Bikash Samaj).", options:{color:INK}}],
  { x:1.0, y:5.15, w:11.3, h:1.15, fontFace:BFONT, fontSize:14, valign:"middle", lineSpacingMultiple:1.05 });
foot(s,6);

// ===== 6. WHAT — what the world misses =====
s = p.addSlide(); lightBase(s); tag(s,"WHAT","के"); title(s,"What the international statistics miss");
s.addShape(p.ShapeType.roundRect,{x:0.7,y:2.3,w:5.8,h:4.0,rectRadius:0.08,fill:{color:CARD},line:{color:LINE,width:1}});
s.addText("India",{x:1.0,y:2.55,w:5,h:0.5,fontFace:HF,fontSize:24,bold:true,color:NAVY});
s.addText("$99.8m",{x:1.0,y:3.15,w:5,h:0.8,fontFace:HF,fontSize:40,bold:true,color:TEAL});
s.addText("Nepal's largest bilateral donor in FY2022/23 — and almost invisible in OECD data, because India does not report to it. Only Nepal's own books capture it.",
  {x:1.0,y:4.1,w:5.2,h:1.9,fontFace:BFONT,fontSize:14,color:MUTE,lineSpacingMultiple:1.05});
s.addShape(p.ShapeType.roundRect,{x:6.85,y:2.3,w:5.75,h:4.0,rectRadius:0.08,fill:{color:CARD},line:{color:LINE,width:1}});
s.addText("China",{x:7.15,y:2.55,w:5,h:0.5,fontFace:HF,fontSize:24,bold:true,color:NAVY});
s.addText([{text:"Big promises, ",options:{color:AMBER,bold:true}},{text:"small delivery",options:{color:CRIMSON,bold:true}}],
  {x:7.15,y:3.2,w:5.3,h:0.7,fontFace:HF,fontSize:26,bold:true});
s.addText("Chinese commitments to Nepal run to hundreds of millions; the disbursements Nepal actually records fell to about $14m by FY2022/23. The headline numbers are pledges, not cash. A measurement fact, stated neutrally.",
  {x:7.15,y:4.1,w:5.2,h:1.9,fontFace:BFONT,fontSize:14,color:MUTE,lineSpacingMultiple:1.05});
foot(s,7);

// ===== 6b. WHAT — accountability =====
s = p.addSlide(); lightBase(s); tag(s,"ACCOUNTABILITY","जवाफदेहिता"); title(s,"What the auditors found");
s.addText("The US Inspector General audits its assistance to Nepal. We traced every Nepal audit we could find.",
  { x:0.55, y:1.95, w:12, h:0.4, fontFace:BFONT, fontSize:15, color:MUTE });
statCard(s, 0.7, 2.7, 5.9, "$323,161", "total questioned costs across 7 audits — just 0.016% of the $2.0bn delivered", TEAL);
statCard(s, 6.75, 2.7, 5.9, "4 of 7", "audit PDFs archived here with checksums; the rest are now offline", NAVY);
s.addShape(p.ShapeType.roundRect, { x:0.7, y:4.95, w:11.95, h:1.55, rectRadius:0.08, fill:{color:"E9F4F3"}, line:{color:"BFD8D6",width:1} });
s.addText([{text:"What this means:  ", options:{bold:true, color:TEAL}},
  {text:"questioned costs were small ineligible-or-unsupported items, mostly on funds the Government of Nepal managed directly. Financial control was reasonable — and the accountability trail is preserved here even as USAID's own document server goes dark.", options:{color:INK}}],
  { x:1.0, y:5.15, w:11.3, h:1.15, fontFace:BFONT, fontSize:14, valign:"middle", lineSpacingMultiple:1.05 });
foot(s,8);

// ===== 7. HOW — integrity =====
s = p.addSlide(); darkBase(s);
s.addShape(p.ShapeType.rect,{x:0,y:0,w:0.18,h:H,fill:{color:CRIMSON}});
s.addText([{text:"HOW  ",options:{bold:true}},{text:"कसरी",options:{color:TEAL}}],{x:0.6,y:0.5,w:9,h:0.4,fontFace:BFONT,fontSize:12,color:CRIMSON,charSpacing:2});
s.addText("Trust is built into the method", { x:0.55, y:0.95, w:12, h:1.0, fontFace:HF, fontSize:33, bold:true, color:WHITE });
const rules=[["Primary sources only","Government and multilateral systems directly — no aggregators, no guesses."],
  ["Archived with a fingerprint","Every figure is pinned to a dated snapshot and a SHA-256 checksum."],
  ["Reconciled, not merged","The two ledgers are squared against each other; every mismatch is logged with its cause."],
  ["Never fabricated","What cannot be verified is left blank and labelled missing."],
  ["Honest about limits","Redactions, classifications and uncertainty are flagged on every chart."],
  ["Fully reproducible","Anyone can re-run the pipeline and get the same numbers."]];
rules.forEach((r,i)=>{
  const x=0.7+(i%2)*6.05, y=2.35+Math.floor(i/2)*1.45;
  s.addShape(p.ShapeType.roundRect,{x,y,w:5.75,h:1.25,rectRadius:0.06,fill:{color:"15315A"},line:{color:"24487A",width:1}});
  s.addText("✓",{x:x+0.2,y:y+0.18,w:0.55,h:0.55,align:"center",valign:"middle",fontFace:HF,fontSize:22,bold:true,color:"6FE3B8"});
  s.addText(r[0],{x:x+0.85,y:y+0.16,w:4.7,h:0.4,fontFace:BFONT,fontSize:15,bold:true,color:WHITE});
  s.addText(r[1],{x:x+0.85,y:y+0.55,w:4.75,h:0.62,fontFace:BFONT,fontSize:11.5,color:ICE});
});
s.addText("9 sources · all reconciling to the dollar where they overlap",{x:0.7,y:6.95,w:11,h:0.3,fontFace:BFONT,fontSize:11,italic:true,color:"8FA6C4"});

// ===== 8. WHAT THIS GIVES NEPAL =====
s = p.addSlide(); lightBase(s); tag(s,"FOR NEPAL","नेपालका लागि"); title(s,"What this puts in Nepal's hands");
iconRow(s, 0.7, 2.25, 11.7, "1", "A planning instrument for the gap",
  "Which sectors lost their pipeline in 2025 — health and governance most — so the budget can respond with evidence, not guesswork.", TEAL);
iconRow(s, 0.7, 3.75, 11.7, "2", "Information sovereignty",
  "Nepal stops depending on foreign portals it cannot control. The record is archived here and updates from Nepal's own AMIS / DCR system.", NAVY);
iconRow(s, 0.7, 5.25, 11.7, "3", "A public transparency portal",
  "The interactive, bilingual companion to the Development Cooperation Report the Ministry of Finance already publishes — for citizens, parliament and partners.", AMBER);
foot(s,10);

// ===== 9. CLOSE =====
s = p.addSlide(); darkBase(s);
s.addShape(p.ShapeType.rect,{x:0,y:0,w:W,h:0.16,fill:{color:TEAL}});
s.addShape(p.ShapeType.rect,{x:0,y:0.16,w:W,h:0.06,fill:{color:CRIMSON}});
s.addText("The record is Nepal's.",{x:0.8,y:2.5,w:12,h:1.0,fontFace:HF,fontSize:44,bold:true,color:WHITE});
s.addText("Built from official sources, kept verifiable, told in two languages —\nso the question “where did the money go?” always has an answer.",
  {x:0.82,y:3.9,w:11.5,h:1.2,fontFace:BFONT,fontSize:18,color:ICE,lineSpacingMultiple:1.1});
s.addText([{text:"Discuss next:  ",options:{bold:true,color:WHITE}},
  {text:"connect it to AMIS  ·  publish it through IECCD  ·  let Nepal contest the classifications",options:{color:"9FB6D4"}}],
  {x:0.82,y:5.6,w:11.6,h:0.6,fontFace:BFONT,fontSize:14});
s.addText("धन्यवाद  ·  Thank you",{x:0.82,y:6.45,w:11,h:0.5,fontFace:HF,fontSize:18,italic:true,color:TEAL});

p.writeFile({ fileName: "report/presentation/Nepal_Aid_Transparency_Briefing.pptx" })
 .then(f => console.log("wrote", f));
