#!/usr/bin/env python3
"""Render declutter scan.json as a self-contained dark HTML report."""
import argparse
import html
import json
from pathlib import Path

CSS = """
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--fg:#e6edf3;--muted:#8b949e;
--accent:#58a6ff;--junk:#f85149;--maybe:#d29922;--keep:#3fb950}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 -apple-system,Helvetica,sans-serif;padding:24px}
h1{margin:0 0 4px;font-size:22px}h1 span{color:var(--accent)}
.sub{color:var(--muted);margin-bottom:20px}
.cards{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:12px 18px;min-width:130px}
.card b{display:block;font-size:20px}
.card small{color:var(--muted)}
.junk b{color:var(--junk)}
.chart{background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:14px 18px;margin-bottom:20px}
.chart h2{font-size:13px;color:var(--muted);margin:0 0 10px;text-transform:uppercase}
.bar{display:flex;align-items:center;gap:10px;margin:4px 0}
.bar label{width:220px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--fg)}
.bar .track{flex:1;background:#21262d;border-radius:4px;height:14px}
.bar .fill{height:14px;border-radius:4px;background:var(--accent)}
.bar span{color:var(--muted);font-size:12px;min-width:60px;text-align:right}
.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-bottom:10px;position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:5}
input[type=text]{background:var(--panel);border:1px solid var(--border);color:var(--fg);border-radius:6px;padding:7px 10px;width:220px}
button{background:var(--panel);border:1px solid var(--border);color:var(--fg);border-radius:6px;padding:7px 12px;cursor:pointer}
button:hover{border-color:var(--accent);color:var(--accent)}
button.primary{background:#1f6feb;border-color:#1f6feb;color:#fff;font-weight:600}
.chip{font-size:12px;color:var(--muted);padding:5px 10px;border:1px solid var(--border);border-radius:999px;cursor:pointer}
.chip.on{color:var(--accent);border-color:var(--accent)}
.total{margin-left:auto;color:var(--muted)} .total b{color:var(--keep)}
table{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--border);border-radius:8px;overflow:hidden}
th{background:#21262d;color:var(--muted);text-align:left;padding:9px 10px;font-size:12px;text-transform:uppercase;cursor:pointer;user-select:none}
th:hover{color:var(--accent)}
td{padding:8px 10px;border-top:1px solid var(--border);vertical-align:top}
tr:hover td{background:#1c2128}
.badge{font-size:11px;font-weight:700;padding:2px 8px;border-radius:999px;color:#0d1117}
.badge.JUNK{background:var(--junk)}.badge.MAYBE{background:var(--maybe)}.badge.KEEP{background:var(--keep)}
.flag{color:var(--junk);font-size:11px;display:block}
.sub-p{color:var(--muted);font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:340px}
.foot{color:var(--muted);font-size:12px;margin-top:14px}
input[type=checkbox]{accent-color:var(--accent);width:15px;height:15px;cursor:pointer}
input[type=checkbox]:disabled{cursor:not-allowed}
.ig{color:var(--muted);cursor:pointer;font-size:11px;margin-left:8px;text-decoration:underline}
.ig:hover{color:var(--junk)}
td.sizebar{min-width:180px}
.fill.j{background:var(--junk)}.fill.m{background:var(--maybe)}.fill.k{background:#2ea04355}
"""


def fmt_bytes(b):
    if b >= 1e9:
        return f"{b/1e9:.2f} GB"
    if b >= 1e6:
        return f"{b/1e6:.1f} MB"
    return f"{max(0, b)//1024} KB"


HTML = """<!doctype html><html><head><meta charset="utf-8">
<title>declutter report</title><style>%(css)s</style></head><body>
<h1>declutter <span>- what can go</span></h1>
<div class="sub">Scanned %(generated)s. Pick rows, hit Export selection, give the file to the agent. Nothing is deleted by this page.%(ignnote)s%(bignote)s</div>
<div class="cards">
 <div class="card"><b>%(n_items)s</b><small>items scanned</small></div>
 <div class="card junk"><b>%(n_junk)s</b><small>JUNK badges</small></div>
 <div class="card"><b>%(reclaim)s</b><small>not KEEP, reclaimable</small></div>
 <div class="card"><b>%(apps)s apps / %(formulae)s brew / %(leftovers)s leftovers</b><small>by kind</small></div>
</div>
<div class="chart"><h2>Top 10 by size</h2>%(top10)s</div>
<div class="controls">
 <input type="text" id="q" placeholder="filter by name...">
 <span class="chip on" data-k="all">all</span>
 <span class="chip" data-k="app">apps</span>
 <span class="chip" data-k="formula">brew</span>
 <span class="chip" data-k="leftover">leftovers</span>
 <span class="chip" data-k="file">files</span>
 <button id="selmj">Select MAYBE+JUNK</button>
 <button id="clear">Clear</button>
 <button class="primary" id="export">Export selection (0)</button>
 <span class="total">checked: <b id="tot">0</b> &middot; ignored: <b id="ig">0</b></span>
</div>
<table><thead><tr>
 <th></th><th data-k="badge">badge</th><th data-k="name">name</th>
 <th data-k="bytes">size &darr;</th><th data-k="days_unused">last used</th><th data-k="kind">kind</th>
</tr></thead><tbody id="tb"></tbody></table>
<div class="foot">badge: JUNK = unused 90+ days or never opened, MAYBE = 31-90 days, KEEP = used recently.
brew formulae needed by others are locked. Apps marked <span style="color:var(--junk)">running</span> are locked until quit.
Deletion route: brew uninstall for brew items, rest moves to ~/.Trash (recoverable, never rm).
File rows are regenerable caches and logs (DerivedData, node_modules, brew/pip/yarn caches, ~/Library/Logs) -
deleting them is safe, things rebuild on next use.
Large-file rows (%(big_mb)s MB+) come from anywhere in your home folder outside ~/Library - not caches, so check each before ticking;
last used is the newer of last read and last write.</div>
<script>const DATA=%(data)s;</script>
<script>
const tb=document.getElementById('tb'),q=document.getElementById('q');
let sortK='bytes',dir=-1,kindF='all';
const rows=DATA.items.map((it,i)=>({...it,i,_checked:false,ignored:false}));
const fmt=b=>b>=1e9?(b/1e9).toFixed(2)+' GB':b>=1e6?(b/1e6).toFixed(1)+' MB':Math.round(b/1024)+' KB';
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const days=x=>x==null?'unknown':(x===0?'today':x+'d ago');
const maxB=Math.max(...rows.map(r=>r.bytes),1);
function locked(r){return r.running||(r.kind==='formula'&&(r.required_by||[]).length>0)}
function reason(r){if(r.running)return'<span class="flag">running - quit first</span>';
 if((r.required_by||[]).length)return'<span class="flag">needed by '+esc(r.required_by.slice(0,2).join(', '))+'</span>';
 if(r.duplicate)return'<span class="flag">duplicate install</span>';return''}
function render(){
 const f=q.value.toLowerCase();
 const vis=rows.filter(r=>kindF==='all'||r.kind===kindF)
  .filter(r=>!f||r.name.toLowerCase().includes(f))
  .sort((a,b)=>{const x=a[sortK],y=b[sortK];
   return(dir*(typeof x==='string'?x.localeCompare(y):(x??-1)-(y??-1)))});
 tb.innerHTML=vis.map(r=>`<tr ${r.ignored?'style="opacity:.35"':''}>
  <td><input type="checkbox" data-i="${r.i}" ${r._checked?'checked':''} ${locked(r)||r.ignored?'disabled':''}></td>
  <td><span class="badge ${r.badge}">${r.badge}</span></td>
  <td><b>${esc(r.name)}</b>${r.kind==='formula'?' <small style="color:var(--muted)">'+esc(r.version||'')+'</small>':''}
      <a class="ig" data-i="${r.i}">${r.ignored?'ignored - undo':'ignore'}</a>${reason(r)}<div class="sub-p">${esc(r.path||'')}${r.from?' &middot; '+esc(r.from):''}</div></td>
  <td class="sizebar"><div class="bar" style="margin:0"><div class="track"><div class="fill ${r.badge==='JUNK'?'j':r.badge==='MAYBE'?'m':'k'}" style="width:${Math.max(1,r.bytes/maxB*100).toFixed(1)}%%"></div></div><span>${fmt(r.bytes)}</span></div></td>
  <td>${days(r.days_unused)}</td>
  <td>${r.kind}${r.kind==='app'?'<div class="sub-p">'+r.source+'</div>':''}</td></tr>`).join('')
  ||'<tr><td colspan="6" style="color:var(--muted)">nothing matches</td></tr>';}
function checked(){return rows.filter(r=>r._checked&&!locked(r))}
function tick(){
 const sel=checked(),n=sel.length,ni=rows.filter(r=>r.ignored).length;
 document.getElementById('export').textContent=`Export selection (${n})`;
 document.getElementById('tot').textContent=fmt(sel.reduce((s,r)=>s+r.bytes,0));
 document.getElementById('ig').textContent=ni;}
tb.addEventListener('change',e=>{if(e.target.dataset.i!=null){
 rows[+e.target.dataset.i]._checked=e.target.checked;tick();}});
tb.addEventListener('click',e=>{if(e.target.classList&&e.target.classList.contains('ig')){
 const r=rows[+e.target.dataset.i];r.ignored=!r.ignored;render();tick();}});
document.querySelectorAll('th[data-k]').forEach(th=>th.onclick=()=>{
 const k=th.dataset.k;dir=sortK===k?-dir:-1;sortK=k;render();});
q.oninput=render;
document.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{
 document.querySelectorAll('.chip').forEach(x=>x.classList.remove('on'));
 c.classList.add('on');kindF=c.dataset.k;render();});
document.getElementById('selmj').onclick=()=>{
 tb.querySelectorAll('input:not(:disabled)').forEach(c=>{
  c.checked=['MAYBE','JUNK'].includes(rows[+c.dataset.i].badge)});tick();};
document.getElementById('clear').onclick=()=>{
 tb.querySelectorAll('input').forEach(c=>c.checked=false);tick();};
document.getElementById('export').onclick=()=>{
 const sel=checked().filter(r=>!r.ignored);
 const items=sel.map(r=>r.kind==='app'&&r.source==='brew'
  ?{kind:'cask',name:r.name,path:r.path,cask:r.cask}:({kind:r.kind,name:r.name,path:r.path}));
 const ignore=rows.filter(r=>r.ignored).map(r=>({kind:r.kind,name:r.name,path:r.path}));
 const blob=new Blob([JSON.stringify({generated:DATA.generated,items,ignore},null,1)],{type:'application/json'});
 const a=document.createElement('a');a.href=URL.createObjectURL(blob);
 a.download='declutter-selection.json';a.click();};
render();tick();
</script></body></html>"""


def top10_bars(items):
    top = sorted(items, key=lambda x: -x["bytes"])[:10]
    if not top:
        return "<div>No items.</div>"
    mx = top[0]["bytes"] or 1
    cls = lambda b: "j" if b == "JUNK" else ("m" if b == "MAYBE" else "k")
    return "".join(
        f'<div class="bar"><label>{html.escape(i["name"])}</label>'
        f'<div class="track"><div class="fill {cls(i["badge"])}" '
        f'style="width:{max(1, i["bytes"]/mx*100):.1f}%"></div></div>'
        f'<span>{fmt_bytes(i["bytes"])}</span></div>'
        for i in top)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scan")
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()
    data = json.loads(Path(args.scan).read_text())
    counts = data["counts"]
    html = HTML % {
        "css": CSS,
        "generated": data["generated"][:19].replace("T", " ") + " UTC",
        "n_items": counts["apps"] + counts["formulae"] + counts["leftovers"],
        "n_junk": counts["junk"],
        "reclaim": fmt_bytes(counts["reclaimable_bytes"]),
        "apps": counts["apps"],
        "formulae": counts["formulae"],
        "leftovers": counts["leftovers"],
        "top10": top10_bars(data["items"]),
        "ignnote": (f" {counts['ignored_hidden']} item(s) hidden by your ignore list."
                    if counts.get("ignored_hidden") else ""),
        "big_mb": counts.get("big_mb", 500),
        "bignote": (" Large-file scan hit its time limit; some big files may be missing."
                    if counts.get("big_scan_truncated") else ""),
        "data": json.dumps(data),
    }
    Path(args.out).write_text(html)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
