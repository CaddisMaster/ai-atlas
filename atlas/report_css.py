"""Styles for the HTML report.

⚠️ No webfonts. A local report that fetched a font from Google would be an
outbound request from a tool whose first promise is that nothing leaves the
machine — and it would happen in the reader's browser, where SECURITY.md cannot
see it. System stacks only, everywhere, including in the published demo, so the
two renders stay identical.

Colour carries the state model, and it is the one from `decisions/0004`:
present, absent and unknown are three answers, and a refusal is **not** a
failure. Pine is measured, brass is unknown or untested, clay is stale, plain
grey is absent. Nothing on this page is red for being honest.
"""

CSS = """
:root{
  --ground:#F1F2ED; --surface:#FBFBF7; --surface-2:#E9EBE3;
  --ink:#191C18; --ink-2:#5F675C; --ink-3:#8A9186;
  --rule:#DBDFD3; --rule-strong:#C4CABA;
  --pine:#2C6349;  --pine-bg:#DDEADF;
  --brass:#8E6B1B; --brass-bg:#F0E6CE;
  --clay:#963B2C;  --clay-bg:#F4DFD9;
  --shadow:0 1px 2px rgba(25,28,24,.06),0 8px 24px -16px rgba(25,28,24,.28);
  --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --ground:#141719; --surface:#1B1F21; --surface-2:#242A2C;
    --ink:#E9EBE3; --ink-2:#98A096; --ink-3:#6E766D;
    --rule:#2C3235; --rule-strong:#3C4448;
    --pine:#63B18B;  --pine-bg:#17301F;
    --brass:#D6A63E; --brass-bg:#3A3016;
    --clay:#D07A66;  --clay-bg:#3A1E18;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -16px rgba(0,0,0,.8);
  }
}
:root[data-theme="dark"]{
  --ground:#141719; --surface:#1B1F21; --surface-2:#242A2C;
  --ink:#E9EBE3; --ink-2:#98A096; --ink-3:#6E766D;
  --rule:#2C3235; --rule-strong:#3C4448;
  --pine:#63B18B;  --pine-bg:#17301F;
  --brass:#D6A63E; --brass-bg:#3A3016;
  --clay:#D07A66;  --clay-bg:#3A1E18;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -16px rgba(0,0,0,.8);
}

*{box-sizing:border-box}
body{
  margin:0; background:var(--ground); color:var(--ink);
  font-family:var(--sans); font-size:15px; line-height:1.5;
  -webkit-font-smoothing:antialiased;
}
h1,h2,h3{margin:0; font-weight:650; letter-spacing:-.02em; text-wrap:balance}
a{color:var(--pine)}
:focus-visible{outline:2px solid var(--brass); outline-offset:2px; border-radius:3px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}

.app{display:grid; grid-template-columns:210px minmax(0,1fr); min-height:100vh}
.rail{
  border-right:1px solid var(--rule); background:var(--surface);
  padding:22px 14px; position:sticky; top:0; height:100vh;
  display:flex; flex-direction:column; gap:24px;
}
.brand b{display:block; font-size:17px; letter-spacing:-.015em}
.brand span{font-family:var(--mono); font-size:10.5px; color:var(--ink-3); letter-spacing:.04em}
.nav{display:flex; flex-direction:column; gap:1px}
.nav a{
  display:flex; justify-content:space-between; gap:8px; align-items:baseline;
  padding:7px 9px; border-radius:5px; text-decoration:none;
  color:var(--ink-2); font-size:14px; font-weight:500;
}
.nav a:hover{background:var(--surface-2); color:var(--ink)}
.nav a .n{font-family:var(--mono); font-size:11px; color:var(--ink-3); font-weight:400}
.rail-foot{margin-top:auto; border-top:1px solid var(--rule); padding-top:14px}
.rail-foot p{margin:0; font-size:11.5px; color:var(--ink-3); line-height:1.45}
.rail-foot code{font-family:var(--mono); font-size:10.5px}

.main{min-width:0; padding:26px 34px 72px; max-width:1140px}
section{scroll-margin-top:20px; margin-bottom:46px}
.head h1{font-size:26px}
.head .sub{color:var(--ink-2); font-size:14px; max-width:66ch; margin:7px 0 0}
.sec{display:flex; align-items:baseline; gap:10px; margin:0 0 14px}
.sec h2{font-size:15px}
.sec .line{flex:1; height:1px; background:var(--rule)}
.sec .cnt{font-family:var(--mono); font-size:11px; color:var(--ink-3)}

.banner{
  border:1px solid var(--brass); background:var(--brass-bg); color:var(--ink);
  border-radius:8px; padding:13px 16px; margin-bottom:22px;
}
.banner b{color:var(--brass)}
.banner p{margin:5px 0 0; font-size:13px; color:var(--ink-2); max-width:74ch}

.cluster{
  display:grid; grid-template-columns:repeat(auto-fit,minmax(148px,1fr));
  border:1px solid var(--rule); border-radius:8px; overflow:hidden;
  background:var(--surface); margin:20px 0 28px; box-shadow:var(--shadow);
}
.stat{padding:14px 16px; border-right:1px solid var(--rule)}
.stat:last-child{border-right:none}
.stat .k{font-family:var(--mono); font-size:9.5px; letter-spacing:.12em;
  text-transform:uppercase; color:var(--ink-3)}
.stat .v{font-size:24px; font-weight:700; letter-spacing:-.02em; margin-top:5px;
  font-variant-numeric:tabular-nums}
.stat .v small{font-size:13px; font-weight:600; color:var(--ink-2); margin-left:2px}
.stat .d{font-size:11.5px; color:var(--ink-3); margin-top:2px}
.stat .v.pine{color:var(--pine)} .stat .v.brass{color:var(--brass)}

.chip{
  font-family:var(--mono); font-size:9.5px; letter-spacing:.08em; text-transform:uppercase;
  padding:2.5px 7px; border-radius:3px; font-weight:500; white-space:nowrap;
}
.chip.pine{background:var(--pine-bg); color:var(--pine)}
.chip.brass{background:var(--brass-bg); color:var(--brass)}
.chip.clay{background:var(--clay-bg); color:var(--clay)}
.chip.mute{background:var(--surface-2); color:var(--ink-3)}

.card{
  background:var(--surface); border:1px solid var(--rule); border-radius:8px;
  padding:15px 17px; margin-bottom:10px; box-shadow:var(--shadow);
}
.card h3{font-size:15px; display:flex; align-items:center; gap:9px; flex-wrap:wrap}
.card p{margin:7px 0 0; color:var(--ink-2); font-size:13.5px; max-width:74ch}
.card .seq{font-family:var(--mono); font-size:13px; line-height:1.6; color:var(--ink)}
.evidence{
  font-family:var(--mono); font-size:11px; color:var(--ink-3);
  margin-top:11px; padding-top:9px; border-top:1px dashed var(--rule);
  display:flex; flex-wrap:wrap; gap:5px 15px;
}
.evidence b{color:var(--ink-2); font-weight:500}

.tbl-wrap{overflow-x:auto; border:1px solid var(--rule); border-radius:8px;
  background:var(--surface); box-shadow:var(--shadow)}
table{border-collapse:collapse; width:100%; font-size:13px; min-width:560px}
th{
  font-family:var(--mono); font-size:9.5px; letter-spacing:.11em; text-transform:uppercase;
  color:var(--ink-3); text-align:left; padding:11px 14px; font-weight:400;
  border-bottom:1px solid var(--rule);
}
td{padding:10px 14px; border-bottom:1px solid var(--rule); color:var(--ink-2)}
tr:last-child td{border-bottom:none}
td.nm{color:var(--ink); font-family:var(--mono); font-size:12.5px}
td.num{text-align:right; font-family:var(--mono); font-size:12.5px;
  font-variant-numeric:tabular-nums}
td.path{font-family:var(--mono); font-size:11px; color:var(--ink-3);
  word-break:break-all; max-width:38ch}
tbody tr:hover td{background:var(--surface-2)}

.note{
  margin-top:20px; padding:13px 16px; border-left:2px solid var(--brass);
  background:var(--surface); border-radius:0 6px 6px 0;
}
.note p{margin:0; font-size:12.5px; color:var(--ink-2); max-width:78ch}
.note b{color:var(--ink)}
.note + .note{margin-top:9px}

.legend{display:flex; flex-wrap:wrap; gap:8px 18px; margin:14px 0 0;
  font-size:12px; color:var(--ink-3)}
.legend span{display:flex; align-items:center; gap:6px}

.foot{border-top:1px solid var(--rule); padding-top:16px; margin-top:40px;
  font-size:12px; color:var(--ink-3); max-width:78ch}
.foot code{font-family:var(--mono)}

@media (max-width:840px){
  .app{grid-template-columns:1fr}
  .rail{position:static; height:auto; flex-direction:row; align-items:center;
    gap:14px; overflow-x:auto; border-right:none; border-bottom:1px solid var(--rule);
    padding:12px 14px}
  .rail-foot{display:none}
  .nav{flex-direction:row; gap:3px}
  .nav a{white-space:nowrap; padding:6px 10px}
  .main{padding:20px 18px 52px}
}
@media print{
  .rail{display:none} .app{grid-template-columns:1fr} .card,.tbl-wrap{box-shadow:none}
}
"""
