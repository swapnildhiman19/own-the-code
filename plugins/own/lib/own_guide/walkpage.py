"""The code-walk picture: one numbered flow, and for each step the screen, the code, the values and the calls.

Claude writes the facts of a walk as JSON (see `validate()` for the shape); this module turns them into
the same picture every time, in two forms:

- `fragment()` - for drawing inside the chat (the desktop app's inline pictures);
- `page()`     - a standalone page saved in the guide as `walks/<flow>.html`, to open any time.

Example: Mia's coupon change. Lanes "You", "Web app: src/cart.js", "Server: app/cart.py". Step 3 is the arrow
Server -> Server "checks the coupon", marked "will change"; its panel shows `app/cart.py:52 apply_coupon()`,
the three real lines, the values `code = "SPRING10"`, `expires = 2026-10-25`, and the calls
`checkout() -> apply_coupon()`. The arrow number, the step number and the panel always match.

Everything from the repo is shown with textContent (never as HTML), and the JSON is embedded so that no code
line can end the script early. Nothing is loaded from the internet.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any

MOMENTS = ("before", "after", "bug")
MARKS = ("", "will change", "changed", "broken")
HOWS = ("", "calls", "runs", "wakes", "http", "returns")
STEP_FIELDS = ("label", "title", "note", "screen", "file", "code", "hl", "values", "calls")
LIMITS = {"label": 40, "title": 120, "note": 240, "screen": 240, "file": 140, "line": 200, "lane": 40}
MAX_LANES, MAX_STEPS, MAX_CODE, MAX_VALUES, MAX_CALLS = 5, 12, 12, 10, 8


def _text(value: Any, field: str, limit: int, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    value = " ".join(value.split()) if field != "code" else value.rstrip()
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > limit:
        raise ValueError(f"{field} is longer than {limit} characters: shorten it")
    return value


def _step_fields(raw: dict[str, Any], where: str, partial: bool) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in ("label", "title", "note", "screen", "file"):
        if key in raw or not partial:
            out[key] = _text(raw.get(key), f"{where}.{key}", LIMITS[key if key in LIMITS else "note"],
                             required=(key in ("label", "title") and not partial))
    if "code" in raw or not partial:
        code = raw.get("code") or []
        if not isinstance(code, list) or len(code) > MAX_CODE:
            raise ValueError(f"{where}.code must be a list of at most {MAX_CODE} lines")
        out["code"] = [_text(line, "code", LIMITS["line"]) for line in code]
    if "hl" in raw or not partial:
        hl = raw.get("hl", -1)
        if not isinstance(hl, int) or isinstance(hl, bool):
            raise ValueError(f"{where}.hl must be the index of the line to highlight (or -1)")
        out["hl"] = hl
    if "values" in raw or not partial:
        values = raw.get("values") or []
        if not isinstance(values, list) or len(values) > MAX_VALUES:
            raise ValueError(f"{where}.values must be a list of at most {MAX_VALUES} [name, value] pairs")
        out["values"] = [[_text(p[0], f"{where}.values", LIMITS["line"]), _text(p[1], f"{where}.values", LIMITS["line"])]
                         for p in values if isinstance(p, list) and len(p) == 2] if values else []
        if len(out["values"]) != len(values):
            raise ValueError(f"{where}.values: every item must be a [name, value] pair of text")
    if "calls" in raw or not partial:
        calls = raw.get("calls") or []
        if not isinstance(calls, list) or len(calls) > MAX_CALLS:
            raise ValueError(f"{where}.calls must be a list of at most {MAX_CALLS} [function, file:line, how] items")
        out["calls"] = []
        for item in calls:
            if not (isinstance(item, list) and len(item) == 3 and item[2] in HOWS):
                raise ValueError(f"{where}.calls: each item is [function, file:line, how], how one of {HOWS[1:]}")
            out["calls"].append([_text(item[0], "call", LIMITS["line"], required=True),
                                 _text(item[1], "call", LIMITS["file"]), item[2]])
    return out


def validate(data: Any) -> dict[str, Any]:
    """Check a walk's facts and return a clean copy (unknown keys dropped). Raises ValueError, in plain words."""
    if not isinstance(data, dict):
        raise ValueError("the walk must be a JSON object")
    flow = data.get("flow")
    if not isinstance(flow, str) or not re.fullmatch(r"[\w.-]+", flow) or flow.startswith("."):
        raise ValueError("flow must be the flow page's name, e.g. checkout for flows/checkout.md")
    moment = data.get("moment")
    if moment not in MOMENTS:
        raise ValueError(f"moment must be one of {MOMENTS}")
    lanes = data.get("lanes")
    if not isinstance(lanes, list) or not 2 <= len(lanes) <= MAX_LANES:
        raise ValueError(f"lanes must list 2 to {MAX_LANES} parts, e.g. \"Web app: src/cart.js\"")
    clean = {"flow": flow, "moment": moment, "title": _text(data.get("title"), "title", LIMITS["title"], True),
             "lanes": [_text(lane, "lane", LIMITS["lane"], True) for lane in lanes], "steps": []}
    steps = data.get("steps")
    if not isinstance(steps, list) or not 1 <= len(steps) <= MAX_STEPS:
        raise ValueError(f"steps must list 1 to {MAX_STEPS} steps (one per numbered arrow)")
    for i, raw in enumerate(steps, 1):
        where = f"step {i}"
        if not isinstance(raw, dict):
            raise ValueError(f"{where} must be an object")
        ends = [raw.get("from"), raw.get("to")]
        if not all(isinstance(e, int) and not isinstance(e, bool) and 0 <= e < len(lanes) for e in ends):
            raise ValueError(f"{where}: from and to must be lane numbers 0 to {len(lanes) - 1}")
        if raw.get("mark", "") not in MARKS:
            raise ValueError(f"{where}.mark must be one of {MARKS[1:]} (or left out)")
        step = {"from": ends[0], "to": ends[1], "mark": raw.get("mark", ""), **_step_fields(raw, where, False)}
        if raw.get("after") is not None:
            if not isinstance(raw["after"], dict):
                raise ValueError(f"{where}.after must be an object with the fields that change")
            step["after"] = _step_fields(raw["after"], f"{where}.after", True)
        clean["steps"].append(step)
    return clean


def _embed(data: dict[str, Any]) -> str:
    """JSON that is safe inside <script>: no "</script>" or line-separator surprises from code lines.

    "<!--" is escaped too: followed by "<script" it would make the browser read past the real "</script>"
    (a walk through an HTML template with a commented-out script tag). In a JS string "\\!" is just "!".
    """
    text = json.dumps(data, ensure_ascii=False)
    return (text.replace("</", "<\\/").replace("<!--", "<\\!--")
            .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


_CSS = """
.ow{font-size:14px;line-height:1.6;color:var(--text-primary,#1f1f1c)}
.ow .bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:0 0 10px}
.ow button{font:inherit;font-size:13px;padding:4px 12px;border-radius:8px;cursor:pointer;
 background:transparent;color:inherit;border:0.5px solid var(--border-strong,#c9c7bd)}
.ow button.on{border-color:var(--border-accent,#378ADD);color:var(--text-accent,#185FA5)}
.ow .cd{background:var(--surface-1,#f3f2ee);border-radius:12px;padding:10px 14px;margin:0 0 10px}
.ow .lb{font-size:12px;color:var(--text-secondary,#6b6a63);margin:0 0 6px}
.ow pre{font-family:var(--font-mono,ui-monospace,Menlo,monospace);font-size:12px;margin:0;white-space:pre-wrap;line-height:1.6}
.ow .hl{background:var(--bg-warning,#FAEEDA);color:var(--text-warning,#854F0B);border-radius:4px}
.ow .tag{font-size:12px;padding:2px 8px;border-radius:8px;margin-left:8px;font-weight:400;
 background:var(--bg-warning,#FAEEDA);color:var(--text-warning,#854F0B)}
.ow .tag.broken{background:var(--bg-danger,#FCEBEB);color:var(--text-danger,#A32D2D)}
.ow .tag.fixed{background:var(--bg-success,#EAF3DE);color:var(--text-success,#3B6D11)}
.ow .key{font-size:12px;color:var(--text-secondary,#6b6a63);margin:4px 0 10px}
.ow svg text{font-family:inherit}
"""

_BODY = """<div class="ow">
<div class="bar" id="ow-modes"></div>
<div id="ow-svg"></div>
<p class="key" id="ow-key"></p>
<div class="bar" id="ow-pills"></div>
<p id="ow-title" style="font-size:16px;font-weight:500;margin:0 0 8px"></p>
<p id="ow-note" style="margin:0 0 10px"></p>
<div class="cd"><p class="lb">On your screen</p><p id="ow-screen" style="margin:0"></p></div>
<div class="cd"><p class="lb" id="ow-file"></p><pre id="ow-code"></pre></div>
<div class="cd"><p class="lb">The values at this moment</p><pre id="ow-vals"></pre></div>
<div class="cd"><p class="lb">Who calls whom to get here</p><pre id="ow-calls"></pre></div>
<div class="bar"><button id="ow-back">Back</button><button id="ow-next">Next</button></div>
</div>"""

_JS = """
(function(){
const W=__DATA__;const NS='http://www.w3.org/2000/svg';
const hasAfter=W.steps.some(s=>s.after);
let mode=W.moment==='after'&&hasAfter?'after':'before',step=Math.min(W.steps.length,Math.max(1,__START__))-1;
const want=/step=(\\d+)/.exec(location.hash||''),wantMode=/mode=(before|after)/.exec(location.hash||'');
if(want)step=Math.min(W.steps.length,Math.max(1,+want[1]))-1;
if(wantMode&&hasAfter)mode=wantMode[1];
const $=id=>document.getElementById(id);
const get=(s,k)=>(mode==='after'&&s.after&&s.after[k]!==undefined)?s.after[k]:s[k];
const HOW={calls:'calls',runs:'runs',wakes:'wakes another thread (a signal, not a call)',http:'HTTP request to',returns:'returns to'};
function color(s){if(!s.mark)return null;if(s.mark==='broken')return mode==='after'?'#639922':'#E24B4A';
 return mode==='after'?'#639922':'#BA7517';}
function el(tag,attrs,text){const e=document.createElementNS(NS,tag);for(const k in attrs)e.setAttribute(k,attrs[k]);
 if(text!==undefined)e.textContent=text;return e;}
function draw(){
 const n=W.lanes.length,lw=640/n,cx=i=>20+lw*(i+.5),top=72,gap=40,h=top+W.steps.length*gap+16;
 const svg=el('svg',{width:'100%',viewBox:'0 0 680 '+h,role:'img'});
 svg.appendChild(el('title',{},W.title));
 const defs=el('defs',{});const m=el('marker',{id:'ow-arrow',viewBox:'0 0 10 10',refX:'8',refY:'5',markerWidth:'6',markerHeight:'6',orient:'auto-start-reverse'});
 m.appendChild(el('path',{d:'M2 1L8 5L2 9',fill:'none',stroke:'context-stroke','stroke-width':'1.5','stroke-linecap':'round'}));
 defs.appendChild(m);svg.appendChild(defs);
 const INK='fill:var(--text-primary,#1f1f1c)',MUTED='fill:var(--text-secondary,#6b6a63)',RULE='stroke:var(--border-strong,#c9c7bd)';
 W.lanes.forEach((lane,i)=>{const bw=Math.min(150,lw-12),x=cx(i)-bw/2,parts=lane.split(': ');
  svg.appendChild(el('rect',{x:x,y:8,width:bw,height:46,rx:6,'stroke-width':'0.5',style:'fill:var(--surface-1,#f3f2ee);'+RULE}));
  svg.appendChild(el('text',{x:cx(i),y:parts[1]?26:35,'text-anchor':'middle','font-size':'13','font-weight':'500',style:INK},parts[0]));
  if(parts[1])svg.appendChild(el('text',{x:cx(i),y:44,'text-anchor':'middle','font-size':'11',style:MUTED},parts.slice(1).join(': ')));
  svg.appendChild(el('line',{x1:cx(i),y1:54,x2:cx(i),y2:h-6,'stroke-dasharray':'3 4','stroke-width':'0.5',style:RULE}));});
 W.steps.forEach((s,i)=>{const y=top+i*gap+18,a=cx(s.from),b=cx(s.to),c='stroke:'+(color(s)||'var(--text-secondary,#6b6a63)');
  const g=el('g',{style:'cursor:pointer'});g.addEventListener('click',()=>{step=i;render();});
  const w=i===step?'3':'1.5';let line;
  if(s.from===s.to){line=el('path',{d:`M${a+4} ${y-8} L${a+40} ${y-8} L${a+40} ${y+8} L${a+8} ${y+8}`,fill:'none','stroke-width':w,'marker-end':'url(#ow-arrow)',style:c});}
  else{const d=b>a?-6:6;line=el('line',{x1:a+(b>a?4:-4),y1:y,x2:b+d,y2:y,'stroke-width':w,'marker-end':'url(#ow-arrow)',style:c});}
  g.appendChild(line);const txt=(i+1)+'  '+get(s,'label'),self=s.from===s.to;
  let lx=self?a+48:Math.min(a,b)+8,anchor='start';
  if(lx+txt.length*6.6>676){lx=self?a-6:Math.max(a,b)-8;anchor='end';}
  g.appendChild(el('text',{x:lx,y:self?y+4:y-7,'font-size':'12','text-anchor':anchor,style:INK},txt));
  svg.appendChild(g);});
 const box=$('ow-svg');box.textContent='';box.appendChild(svg);
 const marks=W.steps.map(s=>s.mark).filter(Boolean);
 $('ow-key').textContent=marks.length?(mode==='after'?'Green arrows: what changed.':
  (marks.includes('broken')?'Red arrow: where it broke. ':'')+(marks.some(x=>x!=='broken')?'Amber arrows: what '+(W.moment==='before'?'will change.':'changed.'):'')):'';}
function render(){
 const s=W.steps[step],tag=$('ow-title');tag.textContent=(step+1)+'. '+get(s,'title');
 if(s.mark){const t=document.createElement('span');t.className='tag'+(s.mark==='broken'&&mode!=='after'?' broken':mode==='after'?' fixed':'');
  t.textContent=mode==='after'?(s.mark==='broken'?'fixed':'changed'):s.mark;tag.appendChild(t);}
 $('ow-note').textContent=get(s,'note')||'';$('ow-screen').textContent=get(s,'screen')||'';
 $('ow-file').textContent='The code that runs'+(get(s,'file')?': '+get(s,'file'):'');
 const code=$('ow-code');code.textContent='';(get(s,'code')||[]).forEach((l,i)=>{const d=document.createElement('div');
  d.textContent=l||' ';if(i===get(s,'hl'))d.className='hl';code.appendChild(d);});
 const v=get(s,'values')||[],w=Math.max(0,...v.map(p=>p[0].length));
 $('ow-vals').textContent=v.length?v.map(p=>p[1]?p[0].padEnd(w)+'  =  '+p[1]:p[0]).join('\\n'):'(none for this step)';
 const calls=get(s,'calls')||[];
 $('ow-calls').textContent=calls.length?calls.map((c,i)=>(i?'  '.repeat(i-1)+'\\u2514 '+(HOW[calls[i-1][2]]||'calls')+' ':'')+c[0]+(c[1]?'   '+c[1]:'')).join('\\n'):'(none for this step)';
 const p=$('ow-pills');p.textContent='';W.steps.forEach((_,i)=>{const b=document.createElement('button');b.textContent=i+1;
  if(i===step)b.className='on';b.setAttribute('aria-label','Step '+(i+1));b.onclick=()=>{step=i;render();};p.appendChild(b);});
 draw();}
const modes=$('ow-modes');
if(hasAfter){[['before','Before'],['after','After']].forEach(([k,t])=>{const b=document.createElement('button');b.textContent=t;
 b.onclick=()=>{mode=k;[...modes.children].forEach(x=>x.classList.toggle('on',x===b));render();};if(k===mode)b.className='on';modes.appendChild(b);});}
$('ow-back').onclick=()=>{step=Math.max(0,step-1);render();};
$('ow-next').onclick=()=>{step=Math.min(W.steps.length-1,step+1);render();};
render();})();
"""


def fragment(data: dict[str, Any], start: int = 1) -> str:
    """The picture for the chat: style, body and script, no page around it, opened at step `start`.

    A walk shows the same picture at each stop, opened at that stop's first arrow (`walk-page --step 3`).
    """
    clean = validate(data)
    if not isinstance(start, int) or not 1 <= start <= len(clean["steps"]):
        raise ValueError(f"--step must be a step number from 1 to {len(clean['steps'])}")
    summary = html.escape(f"{clean['title']}: {len(clean['steps'])} numbered steps, each with the screen, the code, "
                          "the values and the calls.")
    script = _JS.replace("__DATA__", _embed(clean)).replace("__START__", str(start))
    return (f"<style>{_CSS}</style>\n<h2 class=\"sr-only\" style=\"position:absolute;left:-9999px\">{summary}</h2>\n"
            f"{_BODY}\n<script>{script}</script>\n")


def page(data: dict[str, Any], project: str) -> str:
    """The same picture as a page of its own, kept in the guide (`walks/<flow>.html`)."""
    clean = validate(data)
    title = html.escape(f"{clean['title']} - {project}")
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">"
        f"<title>{title}</title><style>"
        ":root{color-scheme:light dark;--surface-1:#f3f2ee;--text-primary:#1f1f1c;--text-secondary:#6b6a63;"
        "--border-strong:#c9c7bd}"
        "@media (prefers-color-scheme: dark){:root{--surface-1:#1e1e1c;--text-primary:#ecebe6;"
        "--text-secondary:#a3a29b;--border-strong:#44433e;--bg-warning:#633806;--text-warning:#FAC775;"
        "--bg-danger:#791F1F;--text-danger:#F7C1C1;--bg-success:#27500A;--text-success:#C0DD97;"
        "--border-accent:#85B7EB;--text-accent:#85B7EB}}"
        "body{margin:0;background:Canvas;color:var(--text-primary);"
        "font:15px/1.5 -apple-system,BlinkMacSystemFont,\"Segoe UI\",sans-serif}"
        "main{max-width:720px;margin:0 auto;padding:24px 16px}h1{font-size:20px;font-weight:500;margin:0 0 4px}"
        "p.sub{color:var(--text-secondary);margin:0 0 16px}</style></head><body><main>"
        f"<h1>{html.escape(clean['title'])}</h1><p class=\"sub\">{html.escape(project)} - flow page "
        f"<code>flows/{html.escape(clean['flow'])}.md</code>. Click an arrow or a number.</p>"
        f"{fragment(clean)}</main></body></html>\n"
    )
