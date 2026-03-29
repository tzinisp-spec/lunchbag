import json
import base64
import os
from pathlib import Path
from datetime import datetime
from crewai.tools import BaseTool
from lunchbag.tools.catalog_utils import sync_catalog

OUTPUTS_DIR = Path("outputs")

def load_json(filename: str) -> dict:
    path = Path(filename)
    if not path.exists(): path = OUTPUTS_DIR / filename
    if not path.exists(): return {}
    try: return json.loads(path.read_text())
    except: return {}

def load_image_info(filename: str) -> dict:
    if not filename: return {"src": "", "month": "", "shoot": ""}
    base_dir = Path("asset_library/images")
    stem = Path(filename).stem
    img_path = next((f for f in base_dir.rglob("*") if f.is_file() and stem in f.name and f.suffix.lower() in {".png", ".jpg", ".jpeg"}), None)
    if not img_path: return {"src": "", "month": "", "shoot": ""}
    parts = img_path.parts
    month, shoot = "", ""
    try:
        idx = parts.index("images")
        if len(parts) > idx + 1: month = parts[idx+1]
        if len(parts) > idx + 2: shoot = parts[idx+2]
    except: pass
    return {"src": f"../{img_path}", "month": month, "shoot": shoot}

def build_html(items: list, calendar: list, sprint: str, season: str) -> str:
    css = """
:root {
  --primary: #185fa5; --bg: #f8f8f7; --sidebar-bg: #ffffff; --text: #1a1a1a;
  --border: #e8e8e6; --accent: #e6f1fb; --danger: #d93025; --success: #188038;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, system-ui, sans-serif; background: var(--bg); color: var(--text); height: 100vh; overflow: hidden; display: flex; flex-direction: column; }
.app-container { display: flex; flex: 1; overflow: hidden; }
.sidebar { width: 280px; background: var(--sidebar-bg); border-right: 1px solid var(--border); display: flex; flex-direction: column; }
.sidebar-header { padding: 24px; border-bottom: 1px solid var(--border); }
.app-title { font-size: 16px; font-weight: 700; color: var(--text); letter-spacing: -0.02em; }
.app-subtitle { font-size: 11px; color: #888; text-transform: uppercase; letter-spacing: 0.05em; font-weight: 600; margin-top: 4px; }
.nav-section { padding: 16px 0; flex: 1; overflow-y: auto; }
.nav-tree { padding: 0 12px; }
.nav-link { padding: 10px 14px; font-size: 13px; color: #444; cursor: pointer; border-radius: 8px; display: flex; align-items: center; gap: 10px; transition: 0.2s; margin-bottom: 2px; }
.nav-link:hover { background: #f0f0ee; }
.nav-link.active { background: var(--accent); color: var(--primary); font-weight: 600; }
.nav-link i { font-style: normal; opacity: 0.6; width: 18px; text-align: center; }
.nav-children { padding-left: 16px; border-left: 1px solid #eee; margin-left: 20px; display: none; margin-top: 4px; }
.nav-node.expanded > .nav-children { display: block; }
.nav-toggle { cursor: pointer; width: 16px; height: 16px; display: flex; align-items: center; justify-content: center; font-size: 9px; transition: 0.2s; }
.nav-node.expanded > .nav-link .nav-toggle { transform: rotate(90deg); }
.main-content { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.top-bar { height: 64px; background: #fff; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; padding: 0 32px; }
.breadcrumb { font-size: 14px; color: #888; }
.breadcrumb b { color: var(--text); font-weight: 600; }
.content-area { flex: 1; overflow-y: auto; padding: 32px; }
.image-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 24px; }
.image-card { background: #fff; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; cursor: pointer; transition: 0.3s; position: relative; }
.image-card:hover { transform: translateY(-6px); box-shadow: 0 12px 30px rgba(0,0,0,0.1); }
.card-img-wrap { aspect-ratio: 4/5; background: #f5f5f3; overflow: hidden; }
.card-img-wrap img { width: 100%; height: 100%; object-fit: cover; }
.card-info { padding: 14px; }
.card-ref { font-family: ui-monospace, monospace; font-size: 11px; color: #888; margin-bottom: 6px; }
.card-pillar { font-size: 10px; font-weight: 700; color: var(--primary); background: var(--accent); padding: 3px 8px; border-radius: 4px; }

/* Google Style Calendar */
.calendar-container { background: #fff; border: 1px solid var(--border); border-radius: 12px; overflow: hidden; display: flex; flex-direction: column; }
.calendar-header { padding: 16px 24px; border-bottom: 1px solid var(--border); display: flex; align-items: center; justify-content: space-between; background: #fafafa; }
.calendar-month-title { font-size: 18px; font-weight: 700; color: var(--text); }
.calendar-grid { display: grid; grid-template-columns: repeat(7, 1fr); background: var(--border); gap: 1px; }
.cal-weekday { background: #fff; padding: 12px; text-align: center; font-size: 11px; font-weight: 700; color: #999; text-transform: uppercase; border-bottom: 1px solid var(--border); }
.cal-cell { background: #fff; min-height: 140px; padding: 8px; display: flex; flex-direction: column; gap: 4px; }
.cal-cell.other-month { background: #fcfcfc; }
.cal-date-num { font-size: 12px; font-weight: 600; color: #bbb; margin-bottom: 4px; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 50%; }
.cal-cell.today .cal-date-num { background: var(--primary); color: #fff; }
.cal-post-item { background: var(--accent); border-radius: 4px; padding: 4px 8px; font-size: 10px; font-weight: 600; color: var(--primary); cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: flex; align-items: center; gap: 6px; }
.cal-post-item:hover { background: #d0e5f7; }
.cal-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--primary); }

/* List View */
.schedule-list { display: flex; flex-direction: column; gap: 24px; max-width: 900px; margin: 0 auto; }
.list-card { background: #fff; border: 1px solid var(--border); border-radius: 16px; overflow: hidden; display: grid; grid-template-columns: 200px 1fr; }
.list-img { aspect-ratio: 1; background: #f5f5f3; border-right: 1px solid var(--border); }
.list-img img { width: 100%; height: 100%; object-fit: cover; }
.list-content { padding: 24px; display: flex; flex-direction: column; }
.list-meta { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
.list-date { font-weight: 700; font-size: 15px; }
.list-status { font-size: 10px; font-weight: 700; text-transform: uppercase; background: #eee; padding: 4px 10px; border-radius: 100px; }
.list-caption { font-size: 15px; color: #333; line-height: 1.6; margin-bottom: 16px; white-space: pre-wrap; }
.list-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 20px; }
.tag-badge { background: var(--accent); color: var(--primary); font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 6px; }
.list-actions { display: flex; gap: 12px; margin-top: auto; padding-top: 16px; border-top: 1px solid var(--border); }
.btn-copy { flex: 1; padding: 10px; border: 1px solid var(--border); background: #fff; border-radius: 8px; font-size: 12px; font-weight: 600; cursor: pointer; transition: 0.2s; }
.btn-copy:hover { background: #f5f5f3; }

.modal { position: fixed; inset: 0; background: rgba(255,255,255,0.98); z-index: 1000; display: none; }
.modal-close { position: absolute; top: 32px; right: 32px; font-size: 32px; cursor: pointer; background: #f5f5f3; width: 48px; height: 48px; display: flex; align-items: center; justify-content: center; border-radius: 50%; z-index: 10; }
.modal-content { width: 100%; height: 100%; padding: 64px; display: grid; grid-template-columns: 1fr 420px; gap: 48px; }
.modal-img-wrap { display: flex; align-items: center; justify-content: center; height: 100%; overflow: hidden; }
.modal-img-wrap img { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.1); }
.modal-side { background: #f8f8f7; padding: 40px; border-radius: 24px; overflow-y: auto; display: flex; flex-direction: column; }
.modal-label { font-size: 11px; font-weight: 700; color: #999; text-transform: uppercase; margin-bottom: 8px; }
.modal-title { font-family: monospace; font-size: 18px; font-weight: 700; margin-bottom: 24px; }
.modal-text { font-size: 16px; line-height: 1.8; margin-bottom: 32px; padding-left: 20px; border-left: 3px solid var(--primary); font-style: italic; }
.toast { position: fixed; bottom: 32px; left: 50%; transform: translateX(-50%); background: #1a1a1a; color: #fff; padding: 12px 24px; border-radius: 12px; display: none; z-index: 2000; }
"""
    js_template = """
const ITEMS = ITEMS_DATA;
const CAL = CAL_DATA;
let view = 'content', mode = 'list', filter = { month: null, shoot: null }, modalIdx = -1, filtered = [];

function init() { buildNav(); showContent(); document.addEventListener('keydown', e => { if (view==='content' && modalIdx !== -1) { if (e.key==='ArrowRight' && modalIdx < filtered.length-1) openModal(modalIdx+1); if (e.key==='ArrowLeft' && modalIdx > 0) openModal(modalIdx-1); if (e.key==='Escape') closeModal(); } }); }

function buildNav() {
  const tree = {}; ITEMS.forEach(i => { if (i.month) { if (!tree[i.month]) tree[i.month] = new Set(); if (i.shoot) tree[i.month].add(i.shoot); } });
  let html = `<div class="nav-node expanded" id="node-content"><div class="nav-link" onclick="showContent()"><i>📦</i> Content</div><div class="nav-children">`;
  Object.keys(tree).sort().forEach(m => {
    html += `<div class="nav-node" id="node-${m}"><div class="nav-link" onclick="toggleMonth('${m}')"><span class="nav-toggle">▶</span> <i>📁</i> ${m}</div><div class="nav-children">`;
    Array.from(tree[m]).sort().forEach(s => html += `<div class="nav-link" id="link-${m}-${s}" onclick="showShoot('${m}','${s}')"><i>📄</i> ${s}</div>`);
    html += `</div></div>`;
  });
  html += `</div></div><div class="nav-node expanded" style="margin-top:16px"><div class="nav-link" onclick="showSchedule('list')"><i>📅</i> Schedule</div><div class="nav-children">
    <div class="nav-link" id="link-sched-cal" onclick="showSchedule('cal')"><i>🗓️</i> Calendar</div>
    <div class="nav-link" id="link-sched-list" onclick="showSchedule('list')"><i>📝</i> List View</div>
  </div></div>`;
  document.getElementById('sidebar-nav').innerHTML = html;
}

function showContent() { view='content'; filter={month:null,shoot:null}; updateUI(); renderGrid(); }
function toggleMonth(m) { event.stopPropagation(); const n=document.getElementById(`node-${m}`); n.classList.toggle('expanded'); view='content'; filter={month:m,shoot:null}; updateUI(); renderGrid(); }
function showShoot(m,s) { event.stopPropagation(); view='content'; filter={month:m,shoot:s}; updateUI(); renderGrid(); }
function showSchedule(m) { view='schedule'; mode=m; updateUI(); if (m==='list') renderList(); else renderCalendar(); }

function updateUI() {
  document.getElementById('content-view').style.display = view==='content' ? 'block' : 'none';
  document.getElementById('schedule-view-container').style.display = view==='schedule' ? 'block' : 'none';
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  if (view==='content') {
    if (!filter.month) document.querySelector('#node-content > .nav-link').classList.add('active');
    else if (!filter.shoot) document.querySelector(`#node-${filter.month} > .nav-link`).classList.add('active');
    else document.getElementById(`link-${filter.month}-${filter.shoot}`).classList.add('active');
    document.getElementById('breadcrumb').innerHTML = `Content / ${filter.month || 'All Assets'} ${filter.shoot ? '/ <b>'+filter.shoot+'</b>' : ''}`;
  } else {
    document.getElementById(`link-sched-${mode}`).classList.add('active');
    document.getElementById('breadcrumb').innerHTML = `Schedule / <b>${mode==='cal' ? 'Calendar' : 'List'}</b>`;
  }
}

function renderGrid() {
  filtered = ITEMS.filter(i => (!filter.month || i.month===filter.month) && (!filter.shoot || i.shoot===filter.shoot));
  document.getElementById('image-grid').innerHTML = filtered.map((i, idx) => `
    <div class="image-card" onclick="openModal(${idx})">
      <div class="card-img-wrap">${i.img_src ? `<img src="${i.img_src}">` : ''}</div>
      <div class="card-info"><div class="card-ref">${i.ref_code}</div><div class="card-pillar">${i.pillar || 'General'}</div></div>
    </div>`).join('');
}

function renderList() {
  document.getElementById('schedule-view').innerHTML = `<div class="schedule-list">${CAL.map(p => {
    const item = ITEMS.find(i => i.ref_code === p.ref_code) || {};
    return `<div class="list-card"><div class="list-img"><img src="${item.img_src||''}"></div>
      <div class="list-content">
        <div class="list-meta"><div class="list-date">${p.day}, ${p.date} • ${p.time}</div><div class="list-status status-${p.status}">${p.status}</div></div>
        <div class="list-caption">${p.caption || 'No caption.'}</div>
        <div class="list-tags">${(p.hashtags || []).map(t => `<span class="tag-badge">${t}</span>`).join('')}</div>
        <div class="list-actions">
          <button class="btn-copy" onclick="copy('${p.caption.replace(/'/g,"\\\\'")}')">Copy Caption</button>
          <button class="btn-copy" onclick="copy('${(p.hashtags || []).join(' ')}')">Copy Tags</button>
        </div>
      </div></div>`;
  }).join('')}</div>`;
}

function renderCalendar() {
  if (!CAL.length) return;
  const first = new Date(CAL[0].date), y = first.getFullYear(), m = first.getMonth();
  const start = new Date(y, m, 1).getDay(), days = new Date(y, m + 1, 0).getDate();
  const monthName = first.toLocaleString('en-US', { month: 'long', year: 'numeric' });
  const weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  
  let html = `<div class="calendar-container"><div class="calendar-header"><div class="calendar-month-title">${monthName}</div></div><div class="calendar-grid">`;
  weekdays.forEach(w => html += `<div class="cal-weekday">${w}</div>`);
  for (let i = 0; i < start; i++) html += `<div class="cal-cell other-month"></div>`;
  for (let d = 1; d <= days; d++) {
    const cur = `${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    const posts = CAL.filter(p => p.date === cur);
    html += `<div class="cal-cell"><div class="cal-date-num">${d}</div>${posts.map(p => `<div class="cal-post-item" onclick="openPostModal('${p.ref_code}')"><span class="cal-dot"></span>${p.time}</div>`).join('')}</div>`;
  }
  document.getElementById('schedule-view').innerHTML = html + `</div></div>`;
}

function copy(t) { navigator.clipboard.writeText(t).then(() => { const s=document.getElementById('toast'); s.textContent="Copied!"; s.style.display="block"; setTimeout(()=>s.style.display="none",2000); }); }
function openModal(idx) { modalIdx=idx; const i=filtered[idx]; document.getElementById('modal-img').src=i.img_src; document.getElementById('modal-ref').textContent=i.ref_code; document.getElementById('modal-caption').textContent=i.caption||'No caption.'; document.getElementById('modal').style.display='flex'; }
function openPostModal(ref) { const i=ITEMS.find(it=>it.ref_code===ref); if(i) { filtered=[i]; openModal(0); } }
function closeModal() { document.getElementById('modal').style.display='none'; modalIdx=-1; }

window.onload = init;
"""
    js = js_template.replace("ITEMS_DATA", json.dumps(items, ensure_ascii=False)).replace("CAL_DATA", json.dumps(calendar, ensure_ascii=False))
    return f"""<!DOCTYPE html><html lang="el"><head><meta charset="UTF-8"><title>THE LUNCHBAGS — Content Management</title><style>{css}</style></head>
<body><div class="app-container"><div class="sidebar"><div class="sidebar-header"><div class="app-title">THE LUNCHBAGS</div><div class="app-subtitle">Asset Library</div></div>
<div class="nav-section"><div class="nav-tree" id="sidebar-nav"></div></div></div>
<div class="main-content"><div class="top-bar"><div class="breadcrumb" id="breadcrumb">Content / ...</div><div class="stats"><div class="stat">Total Assets: <b>{len(items)}</b></div></div></div>
<div class="content-area"><div id="content-view"><div class="image-grid" id="image-grid"></div></div><div id="schedule-view-container" style="display:none"><div id="schedule-view"></div></div></div></div></div>
<div id="modal" class="modal"><div class="modal-close" onclick="closeModal()">&times;</div><div class="modal-content"><div class="modal-img-wrap"><img id="modal-img" src=""></div>
<div class="modal-side"><div class="modal-label">Reference</div><div id="modal-ref" class="modal-title"></div><div class="modal-label">Caption</div><div id="modal-caption" class="modal-text"></div><button class="btn-copy" style="margin-top:auto" onclick="closeModal()">Close</button></div></div></div><div class="toast" id="toast"></div><script>{js}</script></body></html>"""

class ReviewGeneratorTool(BaseTool):
    name: str = "Review Generator"
    description: str = "Generates a standalone HTML review dashboard."
    def _run(self, _: str = "") -> str:
        try:
            sync_catalog()
            copy_data, cal_data = load_json("copy_latest.json"), load_json("weekly_calendar.json") or load_json("monthly_calendar.json")
            posts, copy_items = cal_data.get("posts", []), copy_data.get("copy", [])
            for p in posts:
                if "status" not in p: p["status"] = "planned"
            catalog_path = Path("asset_library/catalog.json")
            cat_imgs = json.loads(catalog_path.read_text())["images"] if catalog_path.exists() else []
            all_items = []
            for img in cat_imgs:
                ref = img.get("ref_code")
                cp = next((c for c in copy_items if c.get("ref_code") == ref), {})
                info = load_image_info(img.get("filename"))
                all_items.append({"ref_code":ref, "filename":img.get("filename"), "img_src":info["src"], "month":img.get("month"), "shoot":img.get("shoot"), "status":img.get("status"), "pillar":cp.get("pillar",""), "caption":cp.get("caption",""), "details":cp.get("details","")})
            (OUTPUTS_DIR / "review.html").write_text(build_html(all_items, posts, copy_data.get("sprint",""), copy_data.get("season","")), encoding="utf-8")
            return "REVIEW GENERATED\nURL: http://localhost:8000/outputs/review.html"
        except Exception as e: return f"TOOL_ERROR: {str(e)}"
