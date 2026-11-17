"""Landing-page dashboard for the forensic analyst (static HTML, data embedded as JSON)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pandas as pd

from .integrity import BANDS, PILLARS, THRESHOLDS

INTEGRITY = Path("results/integrity.csv")
NOTES = Path("results/notes.json")
BACKTEST = Path("results/backtest.json")
OUT = Path("docs/index.html")

SERIES = ["score", "M", "Z", "CFO_NI", "ICR", "LEV", "TATA", "ROA", "GROWTH"]


def clean(v):
    return None if v is None or (isinstance(v, float) and pd.isna(v)) else (round(v, 3) if isinstance(v, float) else v)


def payload(integ: pd.DataFrame, notes: dict, bt: dict) -> dict:
    companies = []
    for name, g in integ.groupby("company"):
        g = g.sort_values("fy")
        scored = g[g["score"].notna() & (g["coverage"] >= 0.5)]
        if scored.empty:
            continue
        last = scored.iloc[-1]
        companies.append({
            "name": name, "group": str(g["group"].iloc[0]), "fy": int(last["fy"]), "score": clean(float(last["score"])),
            "band": last["band"], "action": last["action"], "coverage": clean(float(last["coverage"])),
            "pillars": {k: clean(float(last[f"risk_{k}"])) if pd.notna(last[f"risk_{k}"]) else None for k in PILLARS},
            "measures": {k: clean(float(last[k])) if pd.notna(last[k]) else None for k in THRESHOLDS},
            "series": [{"fy": int(r.fy), **{k: clean(float(getattr(r, k))) if pd.notna(getattr(r, k)) else None
                                           for k in SERIES}} for r in scored.itertuples()],
            "note": notes.get(name, {}),
        })
    companies.sort(key=lambda c: c["score"])
    return {
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%d %b %Y, %H:%M UTC"),
        "companies": companies,
        "pillars": {k: {"label": v[0], "weight": v[1]} for k, v in PILLARS.items()},
        "thresholds": {k: {"good": v[0], "bad": v[1], "what": v[2]} for k, v in THRESHOLDS.items()},
        "bands": [{"floor": b[0], "label": b[1], "action": b[2]} for b in BANDS],
        "backtest": bt,
    }


def render(data: dict) -> str:
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", blob)


def main() -> None:
    if not INTEGRITY.exists() or INTEGRITY.stat().st_size < 5:
        return
    integ = pd.read_csv(INTEGRITY)
    notes = json.loads(NOTES.read_text()) if NOTES.exists() else {}
    bt = json.loads(BACKTEST.read_text()) if BACKTEST.exists() else {}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(payload(integ, notes, bt)), encoding="utf-8")
    print("dashboard ->", OUT)


TEMPLATE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Fraud Radar</title>
<style>
:root{--bg:#f6f5f1;--card:#fff;--fg:#1b2230;--mute:#667085;--line:#e3e0d6;--accent:#1f3a8a;
--clear:#2e7d4f;--mon:#b7791f;--tgt:#d9631e;--open:#b3261e;--track:#ece9df}
@media (prefers-color-scheme:dark){:root{--bg:#12151c;--card:#1b2029;--fg:#e9ebf0;--mute:#9aa3b2;--line:#2b3140;--accent:#8fb0ff;
--clear:#6fcf97;--mon:#e5b25d;--tgt:#f2955a;--open:#f2867f;--track:#2a303d}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,Segoe UI,sans-serif}
header{padding:22px 20px 8px;max-width:1180px;margin:0 auto}
h1{font-size:1.45rem;margin:0}header p{margin:4px 0 0;color:var(--mute)}
.user{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px}.user span{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px 10px;font-size:.86rem}
.user b{color:var(--accent)}
main{max-width:1180px;margin:0 auto;padding:8px 20px 56px}
.grid{display:grid;gap:14px}.kpis{grid-template-columns:repeat(auto-fit,minmax(150px,1fr));margin:14px 0}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.kpi b{display:block;font-size:1.7rem;line-height:1.1}.kpi span{color:var(--mute);font-size:.82rem}
h2{font-size:1.02rem;margin:0 0 10px}h3{font-size:.9rem;margin:14px 0 6px;color:var(--mute);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
table{width:100%;border-collapse:collapse}th,td{text-align:left;padding:8px 8px;border-bottom:1px solid var(--line);font-size:.9rem;vertical-align:middle}
th{color:var(--mute);font-weight:600;font-size:.8rem}tr.row{cursor:pointer}tr.row:hover,tr.sel{background:var(--track)}
.chip{display:inline-block;border-radius:999px;padding:2px 10px;font-size:.78rem;font-weight:700;color:#fff;white-space:nowrap}
.b-Clear{background:var(--clear)}.b-Monitor{background:var(--mon)}.b-Targeted{background:var(--tgt)}.b-Open{background:var(--open)}
.bar{height:8px;background:var(--track);border-radius:6px;overflow:hidden;min-width:70px}.bar i{display:block;height:100%}
.two{grid-template-columns:minmax(0,1fr) minmax(0,1.4fr)}@media(max-width:860px){.two{grid-template-columns:1fr}}
.gauge{text-align:center}.gauge .big{font-size:2.6rem;font-weight:800;line-height:1}.gauge small{color:var(--mute)}
.prow{display:grid;grid-template-columns:150px 1fr 38px;gap:8px;align-items:center;margin:7px 0;font-size:.86rem}
.note{border-left:4px solid var(--accent);padding-left:12px}.badge{font-size:.72rem;color:var(--mute);border:1px solid var(--line);border-radius:6px;padding:1px 6px;margin-left:6px}
ol{margin:6px 0 0 18px;padding:0}li{margin:4px 0}q{display:block;color:var(--mute);font-size:.84rem;margin:4px 0 8px}
.charts{grid-template-columns:repeat(auto-fit,minmax(230px,1fr))}.chart small{color:var(--mute);display:block}
.action{background:var(--track);border-radius:10px;padding:10px 12px;margin-top:10px}
footer{color:var(--mute);font-size:.82rem;margin-top:22px}footer p{margin:6px 0}
</style></head><body>
<header><h1>Fraud Radar</h1>
<p>Forensic triage for lenders and auditors: which companies deserve a closer look, and what to check first.</p>
<div class="user"><span><b>User</b> forensic analyst in a bank's credit-risk or audit team</span>
<span><b>Decision</b> which borrowers get a forensic review this quarter</span><span id="gen"></span></div></header>
<main>
<div class="grid kpis" id="kpis"></div>
<div class="card"><h2>Watchlist, lowest integrity score first <small style="color:var(--mute);font-weight:400">(click a company)</small></h2>
<div style="overflow-x:auto"><table id="list"><thead><tr><th>Company</th><th>FY</th><th>Integrity score</th><th>Status</th><th>Main concern</th></tr></thead><tbody></tbody></table></div></div>
<div id="detail" style="margin-top:14px"></div>
<footer id="foot"></footer>
</main>
<script>
const D=__DATA__;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const css=n=>({Clear:'var(--clear)','Monitor':'var(--mon)','Targeted review':'var(--tgt)','Open forensic review':'var(--open)'}[n]||'var(--mute)');
const cls=n=>'b-'+String(n).split(' ')[0];
const chip=n=>`<span class="chip ${cls(n)}">${esc(n)}</span>`;
const f=(v,d=2)=>v==null?'n/a':Number(v).toFixed(d);
const riskCol=r=>r>=66?'var(--open)':r>=40?'var(--tgt)':r>=20?'var(--mon)':'var(--clear)';
document.getElementById('gen').innerHTML='<b>Updated</b> '+esc(D.generated);
const cs=D.companies;
const cnt=l=>cs.filter(c=>c.band===l).length;
document.getElementById('kpis').innerHTML=[['Companies tracked',cs.length,'var(--fg)'],
 ...D.bands.slice().reverse().map(b=>[b.label,cnt(b.label),css(b.label)])]
 .map(([l,v,c])=>`<div class="card kpi"><b style="color:${c}">${v}</b><span>${esc(l)}</span></div>`).join('');
function topConcern(c){const e=Object.entries(c.pillars).filter(([k,v])=>v!=null).sort((a,b)=>b[1]-a[1])[0];
 return e&&e[1]>=25?D.pillars[e[0]].label+' ('+Math.round(e[1])+')':'None above concern level'}
const tb=document.querySelector('#list tbody');
cs.forEach((c,i)=>{const tr=document.createElement('tr');tr.className='row';tr.dataset.i=i;
 tr.innerHTML=`<td><b>${esc(c.name)}</b></td><td>${c.fy}</td><td><div style="display:flex;gap:8px;align-items:center"><b style="min-width:30px">${Math.round(c.score)}</b><div class="bar" style="flex:1"><i style="width:${c.score}%;background:${css(c.band)}"></i></div></div></td><td>${chip(c.band)}</td><td>${esc(topConcern(c))}</td>`;
 tr.onclick=()=>show(i);tb.appendChild(tr)});
function gauge(s,col){const a=Math.PI*(1-s/100),r=80,x=100+r*Math.cos(a),y=100-r*Math.sin(a);
 return `<svg viewBox="0 0 200 118" width="220" role="img" aria-label="Integrity score ${Math.round(s)} of 100"><path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="var(--track)" stroke-width="16" stroke-linecap="round"/>
 <path d="M20 100 A80 80 0 0 1 ${x} ${y}" fill="none" stroke="${col}" stroke-width="16" stroke-linecap="round"/>
 <text x="100" y="98" text-anchor="middle" font-size="38" font-weight="800" fill="currentColor">${Math.round(s)}</text></svg>`}
function line(c,key,title,opt={}){const pts=c.series.filter(p=>p[key]!=null);if(pts.length<2)return `<div class="card chart"><b>${title}</b><small>not enough years</small></div>`;
 const W=230,H=84,p=6,ys=pts.map(q=>q[key]).concat(opt.ref!=null?[opt.ref]:[]),mn=Math.min(...ys),mx=Math.max(...ys),sp=(mx-mn)||1;
 const X=i=>p+i*(W-2*p)/(pts.length-1),Y=v=>H-p-(v-mn)/sp*(H-2*p);
 const path=pts.map((q,i)=>(i?'L':'M')+X(i).toFixed(1)+' '+Y(q[key]).toFixed(1)).join(' ');
 const ref=opt.ref!=null?`<line x1="${p}" x2="${W-p}" y1="${Y(opt.ref)}" y2="${Y(opt.ref)}" stroke="var(--open)" stroke-dasharray="4 3"/>`:'';
 const last=pts[pts.length-1];
 return `<div class="card chart"><b>${title}</b><small>${opt.note||''}</small><svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${title} trend">${ref}<path d="${path}" fill="none" stroke="var(--accent)" stroke-width="2.2"/><circle cx="${X(pts.length-1)}" cy="${Y(last[key])}" r="3.5" fill="var(--accent)"/></svg>
 <small>${pts[0].fy}: ${f(pts[0][key])} &rarr; ${last.fy}: ${f(last[key])}</small></div>`}
function show(i){const c=cs[i];document.querySelectorAll('#list tr.row').forEach(r=>r.classList.toggle('sel',r.dataset.i==i));
 const n=c.note||{};const pill=Object.entries(c.pillars).map(([k,v])=>`<div class="prow"><span>${esc(D.pillars[k].label)}</span><div class="bar"><i style="width:${v==null?0:v}%;background:${riskCol(v||0)}"></i></div><b>${v==null?'n/a':Math.round(v)}</b></div>`).join('');
 const checks=(n.check_first||[]).map(x=>`<li>${esc(x)}</li>`).join('');
 const flags=(n.red_flags||[]).map(x=>`<li><b>${esc(x.type.replace(/_/g,' '))}</b> <small>(annual report FY${x.report_fy})</small><q>&ldquo;${esc(x.quote)}&rdquo;</q></li>`).join('')||'<li>No verified red flag in the newest extracted annual report, or none extracted yet.</li>';
 const ms=Object.entries(D.thresholds).map(([k,t])=>{const v=c.measures[k];if(v==null)return '';const bad=t.bad>t.good?v>=t.bad:v<=t.bad;
  return `<tr><td>${esc(t.what)}</td><td><b>${f(v)}</b></td><td>${t.good} / ${t.bad}</td><td>${bad?'<span class="chip b-Open">at bad level</span>':''}</td></tr>`}).join('');
 const peers=cs.map(p=>`<div class="prow" style="grid-template-columns:150px 1fr 38px;${p.name===c.name?'font-weight:700':''}"><span>${esc(p.name)}</span><div class="bar"><i style="width:${p.score}%;background:${css(p.band)}"></i></div><b>${Math.round(p.score)}</b></div>`).join('');
 document.getElementById('detail').innerHTML=`<div class="grid two"><div class="card gauge"><h2>${esc(c.name)} <small style="color:var(--mute);font-weight:400">FY${c.fy}</small></h2>${gauge(c.score,css(c.band))}<div>${chip(c.band)}</div>
  <div class="action"><b>Suggested action</b><br>${esc(c.action)}</div><small>Score uses ${Math.round(c.coverage*100)}% of the weighted evidence.</small>
  <h3 style="text-align:left">Risk by pillar (0 clean, 100 severe)</h3><div style="text-align:left">${pill}</div></div>
 <div class="card"><h2>What to look at <span class="badge">${n.ai_written?'AI-written, numbers verified':'rule-based'}</span></h2>
  <div class="note"><b>${esc(n.headline||'')}</b><br>${esc(n.summary||'')}</div>
  <h3>Check first</h3><ol>${checks}</ol><h3>Audit and governance red flags (AI-extracted, quote verified in the report)</h3><ul style="margin:6px 0 0 18px;padding:0">${flags}</ul></div></div>
 <h3 style="margin-top:18px">Trends</h3><div class="grid charts">${line(c,'score','Integrity score')}${line(c,'M','Beneish M-score',{ref:-1.78,note:'above the dashed line is the flag zone'})}${line(c,'Z','Altman Z-score',{ref:1.1,note:'below the dashed line is distress'})}${line(c,'CFO_NI','Cash flow / profit',{note:'1.0 means profit fully backed by cash'})}${line(c,'ICR','Interest cover',{note:'EBIT / interest'})}${line(c,'LEV','Liabilities / equity')}</div>
 <div class="grid two" style="margin-top:14px"><div class="card"><h2>Measures behind the score</h2><div style="overflow-x:auto"><table><thead><tr><th>Measure</th><th>Value</th><th>Good / bad level</th><th></th></tr></thead><tbody>${ms}</tbody></table></div></div>
 <div class="card"><h2>Against the other companies</h2>${peers}</div></div>`;
 document.getElementById('detail').scrollIntoView({behavior:'smooth',block:'nearest'})}
if(cs.length)show(0);
const b=D.backtest&&D.backtest.numbers_only;
document.getElementById('foot').innerHTML=`<p><b>How the score works.</b> Six pillars (earnings quality, cash conversion, leverage, distress, operating performance, AI-extracted audit red flags) are each rated 0-100 between a good and a bad level, weighted ${Object.values(D.pillars).map(p=>p.weight).join('/')}, and subtracted from 100. Where evidence is missing the remaining weights are rescaled and coverage is shown.</p>
<p><b>Validation, stated plainly.</b> ${b?`In a small back-test of two companies with documented regulatory action against six peers, the numbers-based screen flagged ${Math.round(b.detection_rate*100)}% of the flagged companies and ${Math.round(b.false_positive_rate*100)}% of the peers by mistake.`:'Back-test not available.'} With so few companies this is illustrative, not proof. A low score is a reason to look, never a finding of fraud.</p>
<p>Data: Yahoo Finance statements and company annual reports. Text red flags are extracted by Gemini and kept only when the quote is found word for word in the report.</p>`;
</script></body></html>
"""

if __name__ == "__main__":
    main()
