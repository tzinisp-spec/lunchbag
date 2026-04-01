"""
Lunchbag Webapp — Flask API
Serves data from the pipeline's output files.
"""

import json
import os
import queue
import re
from functools import wraps
from pathlib import Path
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / '.env')
except ImportError:
    pass  # dotenv not installed — env vars must be set manually
from datetime import datetime
from flask import Flask, jsonify, send_file, request, abort, Response, stream_with_context, session
from flask_cors import CORS
from process_manager import process_manager, process_manager_p2

app = Flask(__name__)
CORS(app, supports_credentials=True)

# ── Auth config ───────────────────────────────────────────────────────────────
# Set SECRET_KEY, ADMIN_USER, ADMIN_PASS, CLIENT_USER, CLIENT_PASS in env.
app.secret_key = os.getenv('SECRET_KEY', 'dev-secret-change-in-production')

_CREDENTIALS = {
    os.getenv('ADMIN_USER',  'admin'):  {'password': os.getenv('ADMIN_PASS',  'admin'),  'role': 'admin'},
    os.getenv('CLIENT_USER', 'client'): {'password': os.getenv('CLIENT_PASS', 'client'), 'role': 'client'},
}

# Routes the client role is NOT allowed to call
_CLIENT_BLOCKED = (
    '/api/dashboard', '/api/activity', '/api/logs',
    '/api/run',       '/api/p2',       '/api/agents',
    '/api/photoshoot-report', '/api/content-plan-report',
    '/api/brand',     '/api/concept',  '/api/products',
    '/api/org',
)

@app.before_request
def _check_auth():
    # Auth endpoints and image proxy are always public
    if request.path.startswith('/api/auth/') or request.path == '/api/image':
        return None
    if not request.path.startswith('/api/'):
        return None
    # Must be logged in for all other API routes
    if 'role' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    # Client role: block admin-only prefixes
    if session['role'] == 'client':
        for prefix in _CLIENT_BLOCKED:
            if request.path.startswith(prefix):
                return jsonify({'error': 'Forbidden'}), 403

# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.route('/api/auth/login', methods=['POST'])
def auth_login():
    data     = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')
    user     = _CREDENTIALS.get(username)
    if not user or user['password'] != password:
        return jsonify({'error': 'Invalid credentials'}), 401
    session['user'] = username
    session['role'] = user['role']
    return jsonify({'user': username, 'role': user['role']})

@app.route('/api/auth/me')
def auth_me():
    if 'user' not in session:
        return jsonify({'user': None, 'role': None})
    return jsonify({'user': session['user'], 'role': session['role']})

@app.route('/api/auth/logout', methods=['POST'])
def auth_logout():
    session.clear()
    return jsonify({'ok': True})

ROOT         = Path(__file__).parent.parent
ASSET_DIR    = ROOT / "asset_library" / "images"
REPORTS_DIR  = ROOT / "outputs" / "sprint_reports"
OUTPUTS_DIR  = ROOT / "outputs"
BRAND_DIR    = ROOT / "brand"
AGENTS_YAML  = ROOT / "lunchbag" / "config" / "agents.yaml"
CONCEPT_PATH      = ROOT / "concept.md"
SHOOT_CONFIG_PATH = ROOT / "lunchbag" / "config" / "shoot_config.json"

_SHOOT_CONFIG_DEFAULTS = {
    "images_per_sprint": "50",
    "product_focus":     "Original thermal lunch bag — cotton exterior, waterproof interior, Thermo Hot&Cold mechanism, H21cm x W16cm x D24cm, various prints and colours",
    "product_materials": "Cotton exterior, waterproof interior lining, thermal insulation, fabric straps. Surface has a soft textile feel — not leather, not plastic, not glossy. Bold graphic prints on cotton.",
    "target_audience":   "Women and men 25-45, Greece and Europe, active lifestyle, health-conscious, daily commuters, parents, office workers, anyone who carries food on the go",
}
PRODUCTS_DIR = ROOT / "products"

# Maps agents.yaml keys → frontend agent IDs
_YAML_ID = {
    'content_orchestrator': 'orchestrator',
    'trend_scout':          'trend_scout',
    'content_strategist':   'strategist',
    'visual_director':      'director',
    'photographer':         'photographer',
    'qc_inspector':         'photo_editor',
}

_AGENTS_FALLBACK = [
    {
        "id":   "orchestrator",
        "name": "Content Orchestrator",
        "role": "Coordinates the full sprint",
        "description": "Senior creative operations manager. Briefs every agent, monitors progress, retries failures, and delivers the final image catalog to the brand owner. Nothing moves without its sign-off.",
    },
    {
        "id":   "trend_scout",
        "name": "Trend Scout",
        "role": "Instagram trend research",
        "description": "Tracks trending formats, hashtags, and competitor moves on Instagram every sprint. Scores each trend by relevance to the brand and flags urgent opportunities before the Strategist starts planning.",
    },
    {
        "id":   "strategist",
        "name": "Content Strategist",
        "role": "Creative brief & visual world extraction",
        "description": "Reads the reference images and campaign concept, then extracts the visual world precisely — setting, lighting, props, mood, and composition style. Produces a brief specific enough for the Director to execute without a follow-up question.",
    },
    {
        "id":   "director",
        "name": "Visual Director",
        "role": "Style Bible & Shot List",
        "description": "Designs 3 complete shoot sets that match the world of the reference images. Writes a DNA Prompt Block per set to lock the lighting and aesthetic, then writes a Shot List of 50 compositions — product variant, model presence, angle, and distance for every frame.",
    },
    {
        "id":   "photographer",
        "name": "Photographer",
        "role": "Image generation",
        "description": "Executes the full Shot List in one continuous run using multimodal prompts — product refs, style refs, and the DNA block for each set. Runs 3 concurrent workers for ~3× throughput. Hard constraints prevent structural errors from being generated.",
    },
    {
        "id":   "photo_editor",
        "name": "Photo Editor",
        "role": "QC review, fixing & regen flagging",
        "description": "Reviews every generated image against product references. Approves clean images, applies targeted fixes for minor issues, and flags structural failures (wrong strap, wrong model) for full regeneration. Saves a checkpoint after each image so a disconnection never loses progress.",
    },
]


def _load_agents() -> list[dict]:
    """Return agents list sourced from agents.yaml, falling back to _AGENTS_FALLBACK."""
    if not AGENTS_YAML.exists():
        return _AGENTS_FALLBACK
    try:
        import yaml

        with AGENTS_YAML.open() as fh:
            raw = yaml.safe_load(fh) or {}

        # Brand name for template substitution
        brand_name = "The Lunchbags"
        strategy = BRAND_DIR / "copy_strategy.md"
        if strategy.exists():
            m = re.match(r'^#\s+([^—\n]+)', strategy.read_text())
            if m:
                brand_name = m.group(1).strip()

        def sub(text: str) -> str:
            if not text:
                return ""
            text = text.replace("{brand_name}", brand_name)
            text = re.sub(r"\{[^}]+\}", "", text)
            return " ".join(text.split())

        # Build a per-id lookup from yaml
        yaml_by_id: dict[str, dict] = {}
        for yaml_key, data in raw.items():
            agent_id = _YAML_ID.get(yaml_key, yaml_key)
            yaml_by_id[agent_id] = {
                "role":        sub(data.get("role", "")),
                "goal":        sub(data.get("goal", "")),
                "description": sub(data.get("backstory", "")),
            }

        # Merge: fallback provides name/id, yaml provides role/goal/description
        merged = []
        seen: set[str] = set()
        for agent in _AGENTS_FALLBACK:
            a = dict(agent)
            yd = yaml_by_id.get(agent["id"], {})
            if yd.get("role"):        a["role"]        = yd["role"]
            if yd.get("goal"):        a["goal"]        = yd["goal"]
            if yd.get("description"): a["description"] = yd["description"]
            merged.append(a)
            seen.add(agent["id"])

        # Agents that exist in yaml but not in the fallback list
        for yaml_key, data in raw.items():
            agent_id = _YAML_ID.get(yaml_key, yaml_key)
            if agent_id not in seen:
                merged.append({
                    "id":          agent_id,
                    "name":        sub(data.get("role", yaml_key)).split(" for ")[0].strip(),
                    "role":        sub(data.get("role", "")),
                    "description": sub(data.get("backstory", "")),
                })
                seen.add(agent_id)

        return merged
    except Exception:
        return _AGENTS_FALLBACK


def _parse_concept(text: str) -> dict:
    """Parse concept.md into structured data."""
    result: dict = {"title": "", "narrative": "", "sets": [], "visual_direction": []}

    m = re.match(r"CAMPAIGN CONCEPT:\s*(.+)", text)
    if m:
        result["title"] = m.group(1).strip()

    sections = re.split(r"\n(?=SET \d+:|VISUAL DIRECTION:)", text)

    # Narrative: everything after title line, before first SET
    narrative_lines = [l.strip() for l in sections[0].split("\n")[1:] if l.strip()]
    result["narrative"] = " ".join(narrative_lines)

    for section in sections[1:]:
        section = section.strip()

        if section.startswith("SET "):
            sm = re.match(r"SET (\d+):\s*(.+)", section)
            if not sm:
                continue
            body = section[sm.end():].strip()
            loc = props = energy = ""
            for line in body.split("\n"):
                line = line.strip()
                if   line.startswith("Location:"): loc    = line[9:].strip()
                elif line.startswith("Props:"):     props  = line[6:].strip()
                elif line.startswith("Energy:"):    energy = line[7:].strip()
            result["sets"].append({
                "number":   int(sm.group(1)),
                "name":     sm.group(2).strip(),
                "location": loc,
                "props":    props,
                "energy":   energy,
            })

        elif section.startswith("VISUAL DIRECTION:"):
            body = section[len("VISUAL DIRECTION:"):].strip()
            result["visual_direction"] = [
                l.lstrip("- ").strip()
                for l in body.split("\n")
                if l.strip().startswith("-")
            ]

    return result


# ── Helpers ────────────────────────────────────────────────────────────────

def _parse_table_value(text: str, label: str) -> str | None:
    """Extract a value from a markdown table row by label."""
    escaped = re.escape(label)
    m = re.search(rf'\|\s*\*{{0,2}}{escaped}\*{{0,2}}\s*\|\s*\*{{0,2}}(.+?)\*{{0,2}}\s*\|', text)
    return m.group(1).strip() if m else None


def _parse_sprint_report(path: Path) -> dict:
    """Parse a markdown sprint report into a structured dict."""
    try:
        text = path.read_text()
        r: dict = {}

        # ── Summary ──────────────────────────────────────────
        r["runtime"]      = _parse_table_value(text, "Total runtime")
        r["pass_rate"]    = _parse_table_value(text, "First-pass approval rate")
        r["needs_review"] = _parse_table_value(text, "Needs manual review")
        r["errors"]       = _parse_table_value(text, "Errors") or "0"

        # ── Step timings ─────────────────────────────────────
        r["time_brief"]       = _parse_table_value(text, "Creative Brief")
        r["time_style_bible"] = _parse_table_value(text, "Style Bible + Shot List")
        r["time_generation"]  = _parse_table_value(text, "Image Generation")
        r["time_photo_editor"]= _parse_table_value(text, "Photo Editor Review")

        # ── Error / fix breakdown ────────────────────────────
        r["errors_fixed"]   = _parse_table_value(text, "Fixed by editing") or "0"
        r["errors_flagged"] = _parse_table_value(text, "Flagged for manual review") or "0"
        try:
            r["errors_total"] = int(r["errors_fixed"]) + int(r["errors_flagged"])
        except ValueError:
            r["errors_total"] = 0

        # ── Per-model API calls & cost ────────────────────────
        def _model_row(label):
            m = re.search(
                rf'\|\s*{re.escape(label)}\s*\|\s*\*{{0,2}}(\d+)\*{{0,2}}\s*\|\s*\*{{0,2}}\$?([\d.]+)\*{{0,2}}',
                text
            )
            return (int(m.group(1)), float(m.group(2))) if m else (0, 0.0)

        img_calls, img_cost = _model_row("Image generation model")
        txt_calls, txt_cost = _model_row("Text/vision model")
        r["calls_image_model"] = img_calls
        r["cost_image_model"]  = img_cost
        r["calls_text_model"]  = txt_calls
        r["cost_text_model"]   = txt_cost

        # Model names from section headers
        m = re.search(r'###\s*(gemini[^\n]*image[^\n]*)', text, re.IGNORECASE)
        r["image_model_name"] = m.group(1).strip() if m else "Image model"
        m = re.search(r'###\s*(gemini-2\.[^\n]+)', text, re.IGNORECASE)
        r["text_model_name"]  = m.group(1).strip() if m else "Text model"

        # ── Totals ───────────────────────────────────────────
        m = re.search(
            r'\*\*Total\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*\$?([\d.]+)\*\*',
            text
        )
        r["total_calls"] = int(m.group(1))  if m else img_calls + txt_calls
        r["total_cost"]  = float(m.group(2)) if m else round(img_cost + txt_cost, 2)

        return r
    except Exception:
        return {}


def _set_num(ref_code: str) -> int:
    """Extract set number from ref_code like '...S2-014'. Returns 0 if unknown."""
    m = re.search(r'-S(\d+)-', ref_code)
    return int(m.group(1)) if m else 0


def _load_shoot(month_dir: Path, shoot_dir: Path) -> dict:
    """Build a shoot summary dict from its catalog and sprint report."""
    shoot_id = f"{month_dir.name}__{shoot_dir.name}"

    # ── Catalog ──────────────────────────────────────────────
    catalog_path = shoot_dir / "catalog.json"
    catalog_meta = {}
    images = []
    sprint_id = None

    if catalog_path.exists():
        try:
            catalog_meta = json.loads(catalog_path.read_text())
            images = catalog_meta.get("images", [])
            if images:
                sprint_id = images[0].get("sprint")
        except Exception:
            pass

    total_images  = len(images)
    approved      = sum(1 for img in images if img.get("status") == "approved")
    needs_review  = sum(1 for img in images
                        if "Needs Review" in img.get("filename", ""))
    regen         = sum(1 for img in images
                        if img.get("filename", "").startswith("Regen-"))

    # ── Date ────────────────────────────────────────────────
    generated_at = catalog_meta.get("generated", "")
    date_str = ""
    if generated_at:
        try:
            dt = datetime.fromisoformat(generated_at)
            date_str = dt.strftime("%B %d, %Y")
        except Exception:
            pass

    # ── Sprint report ────────────────────────────────────────
    report = {}
    if sprint_id and REPORTS_DIR.exists():
        # Sort by embedded date, not alphabetically (avoid '_' > '-' trap).
        # Prefer shoot-specific report (shoot_dir.name in filename) over
        # campaign-level reports that share the same sprint_id prefix.
        candidates = sorted(
            [f for f in REPORTS_DIR.iterdir()
             if f.name.endswith(".md") and shoot_dir.name in f.name],
            key=lambda p: _file_dt(p.name) or "",
            reverse=True,
        )
        if candidates:
            report = _parse_sprint_report(candidates[0])

    # ── Status ───────────────────────────────────────────────
    # Check shoot_timing.json first — independent of catalog contents so that
    # a run starting with 0 cataloged images still returns "in_progress".
    status = "empty"
    timing_path = OUTPUTS_DIR / "shoot_timing.json"
    if timing_path.exists():
        try:
            t = json.loads(timing_path.read_text())
            if shoot_dir.name in t.get("sprint_id", "") and not t.get("shoot_end"):
                status = "in_progress"
        except Exception:
            pass
    if status == "empty" and total_images > 0:
        status = "complete"

    return {
        "id":           shoot_id,
        "name":         shoot_dir.name,
        "month":        month_dir.name,
        "date":         date_str,
        "total_images": total_images,
        "approved":     approved,
        "needs_review": needs_review,
        "regen":        regen,
        "status":       status,
        "sprint_id":    sprint_id or "UNKNOWN",
        "runtime":           report.get("runtime", "—"),
        "pass_rate":         report.get("pass_rate", "—"),
        "total_calls":       report.get("total_calls", 0),
        "total_cost":        report.get("total_cost", 0.0),
        "errors":            report.get("errors", "0"),
        # Step timings
        "time_brief":        report.get("time_brief"),
        "time_style_bible":  report.get("time_style_bible"),
        "time_generation":   report.get("time_generation"),
        "time_photo_editor": report.get("time_photo_editor"),
        # Error breakdown
        "errors_fixed":      report.get("errors_fixed", "0"),
        "errors_flagged":    report.get("errors_flagged", "0"),
        "errors_total":      report.get("errors_total", 0),
        # Per-model API
        "calls_image_model": report.get("calls_image_model", 0),
        "cost_image_model":  report.get("cost_image_model", 0.0),
        "calls_text_model":  report.get("calls_text_model", 0),
        "cost_text_model":   report.get("cost_text_model", 0.0),
        "image_model_name":  report.get("image_model_name", "Image model"),
        "text_model_name":   report.get("text_model_name", "Text model"),
    }


def _all_shoots() -> list[dict]:
    """Return all shoots sorted newest-first."""
    shoots = []
    if not ASSET_DIR.exists():
        return shoots
    for month_dir in sorted(ASSET_DIR.iterdir(), reverse=True):
        if not month_dir.is_dir():
            continue
        for shoot_dir in sorted(month_dir.iterdir(), reverse=True):
            if shoot_dir.is_dir() and shoot_dir.name.startswith("Shoot"):
                shoots.append(_load_shoot(month_dir, shoot_dir))
    return shoots


def _aggregate_shoots(shoots: list[dict]) -> dict:
    """Sum numeric stats across a list of shoots into one overview dict."""
    active = [s for s in shoots if s["status"] != "empty"]
    if not active:
        return {}

    def _int(val):
        try: return int(val)
        except: return 0

    first = next((s for s in active if s.get("image_model_name")), active[0])

    return {
        "total_images":      sum(s["total_images"]  for s in active),
        "approved":          sum(s["approved"]       for s in active),
        "needs_review":      sum(s["needs_review"]   for s in active),
        "regen":             sum(s.get("regen", 0)   for s in active),
        "total_calls":       sum(s["total_calls"]    for s in active),
        "total_cost":        round(sum(s["total_cost"] for s in active), 2),
        "calls_image_model": sum(s.get("calls_image_model", 0) for s in active),
        "calls_text_model":  sum(s.get("calls_text_model",  0) for s in active),
        "cost_image_model":  round(sum(s.get("cost_image_model", 0.0) for s in active), 2),
        "cost_text_model":   round(sum(s.get("cost_text_model",  0.0) for s in active), 2),
        "errors_total":      sum(s.get("errors_total", 0) for s in active),
        "errors_fixed":      str(sum(_int(s.get("errors_fixed",   0)) for s in active)),
        "errors_flagged":    str(sum(_int(s.get("errors_flagged", 0)) for s in active)),
        "errors":            str(sum(_int(s.get("errors", 0)) for s in active)),
        # Timings don't aggregate meaningfully — omit
        "runtime":           "—",
        "time_brief":        None,
        "time_style_bible":  None,
        "time_generation":   None,
        "time_photo_editor": None,
        # Model names from first shoot that has them
        "image_model_name":  first.get("image_model_name", "Image model"),
        "text_model_name":   first.get("text_model_name",  "Text model"),
        "shoot_count":       len(active),
    }


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.route("/api/dashboard")
def dashboard():
    shoots = _all_shoots()
    active = [s for s in shoots if s["status"] != "empty"]

    # Group by month
    by_month: dict[str, list] = {}
    for s in active:
        by_month.setdefault(s["month"], []).append(s)

    # Decide what to show as "Latest Run" in the Overview tiles.
    # Phase 2 (content planning) runs independently — if its progress file is
    # newer than Phase 1's, or if it is currently live, show Phase 2 stats.
    progress    = _read_progress()
    progress_p2 = _read_progress_p2()

    if progress and progress.get("status") in ("in_progress", "paused") and process_manager.state == 'idle':
        _mark_progress_stopped(PROGRESS_PATH)
        progress = _read_progress()
    if progress_p2 and progress_p2.get("status") in ("in_progress", "paused") and process_manager_p2.state == 'idle':
        _mark_progress_stopped(PROGRESS_P2_PATH)
        progress_p2 = _read_progress_p2()

    p1_is_live = bool(progress    and progress.get("status")    == "in_progress")
    p2_is_live = bool(progress_p2 and progress_p2.get("status") == "in_progress")

    # Use Phase 2 stats if it is live, or if its file is newer than Phase 1's
    use_p2 = False
    if progress_p2:
        if p2_is_live:
            use_p2 = True
        elif PROGRESS_P2_PATH.exists() and (
            not PROGRESS_PATH.exists()
            or PROGRESS_P2_PATH.stat().st_mtime > PROGRESS_PATH.stat().st_mtime
        ):
            use_p2 = True

    is_live = p1_is_live or p2_is_live

    if use_p2:
        latest_shoot = _p2_stats(progress_p2)
    elif p1_is_live:
        latest_shoot = _live_stats(progress)
    else:
        latest_shoot = active[0] if active else {}

    return jsonify({
        "agents":            len(_load_agents()),
        "shoots":            len(active),
        "recent_shoots":     shoots[:5],
        "is_live":           is_live,
        # Overview tiles data
        "latest":            latest_shoot,
        "all_time":          _aggregate_shoots(active),
        "by_month":          {m: _aggregate_shoots(s) for m, s in by_month.items()},
        "available_months":  sorted(by_month.keys(), reverse=True),
    })


@app.route("/api/shoots")
def shoots_list():
    return jsonify(_all_shoots())


def _require_admin():
    """Return a 403 response if the current session is not admin, else None."""
    if session.get('role') != 'admin':
        return jsonify({'error': 'Forbidden'}), 403
    return None


@app.route("/api/shoots/<path:shoot_id>/rename", methods=["PATCH"])
def rename_shoot(shoot_id):
    err = _require_admin()
    if err: return err

    parts = shoot_id.split("__")
    if len(parts) != 2:
        abort(400)
    month_name, shoot_name = parts
    shoot_dir = ASSET_DIR / month_name / shoot_name
    if not shoot_dir.exists():
        abort(404)

    data     = request.get_json() or {}
    new_name = data.get("name", "").strip()
    if not new_name:
        return jsonify({"error": "Name cannot be empty"}), 400
    if not re.match(r'^[\w\-]+$', new_name):
        return jsonify({"error": "Name can only contain letters, numbers, hyphens and underscores"}), 400
    if new_name == shoot_name:
        return jsonify({"id": shoot_id, "name": shoot_name})

    new_shoot_dir = ASSET_DIR / month_name / new_name
    if new_shoot_dir.exists():
        return jsonify({"error": f"A shoot named '{new_name}' already exists in {month_name}"}), 409

    # Update catalog.json paths before renaming the folder
    catalog_path = shoot_dir / "catalog.json"
    if catalog_path.exists():
        try:
            catalog = json.loads(catalog_path.read_text())
            for img in catalog.get("images", []):
                if img.get("shoot") == shoot_name:
                    img["shoot"] = new_name
                if "path" in img:
                    img["path"] = img["path"].replace(f"/{shoot_name}/", f"/{new_name}/")
            catalog_path.write_text(json.dumps(catalog, indent=2))
        except Exception as e:
            return jsonify({"error": f"Failed to update catalog: {e}"}), 500

    shoot_dir.rename(new_shoot_dir)
    return jsonify({"id": f"{month_name}__{new_name}", "name": new_name})


@app.route("/api/shoots", methods=["DELETE"])
def delete_shoots():
    err = _require_admin()
    if err: return err

    import shutil
    data      = request.get_json() or {}
    shoot_ids = data.get("shoot_ids", [])
    if not shoot_ids:
        return jsonify({"error": "No shoot_ids provided"}), 400

    deleted, errors = [], []
    for shoot_id in shoot_ids:
        parts = shoot_id.split("__")
        if len(parts) != 2:
            errors.append({"id": shoot_id, "error": "Invalid ID"}); continue
        month_name, shoot_name = parts
        shoot_dir = ASSET_DIR / month_name / shoot_name
        if not shoot_dir.exists():
            errors.append({"id": shoot_id, "error": "Not found"}); continue
        try:
            shutil.rmtree(shoot_dir)
            deleted.append(shoot_id)
        except Exception as e:
            errors.append({"id": shoot_id, "error": str(e)})

    return jsonify({"deleted": deleted, "errors": errors})


def _load_shoot_detail(month_dir: Path, shoot_dir: Path) -> dict:
    """Full shoot detail: summary + annotated image list + sets dict."""
    summary = _load_shoot(month_dir, shoot_dir)

    def _display(filename: str, set_num: int = 0, catalog_status: str = "") -> str:
        """Map filename to display_status. The photo editor only renames bad files,
        so anything without a problem prefix is a clean/approved image."""
        if filename.startswith("Regen-"):
            return "regen"
        if "Needs Review" in filename:
            return "needs_review"
        return "approved"

    catalog_path = shoot_dir / "catalog.json"
    images: list[dict] = []
    if catalog_path.exists():
        try:
            catalog = json.loads(catalog_path.read_text())
            for img in catalog.get("images", []):
                filename = img.get("filename", "")
                ref_code = img.get("ref_code", "")
                set_num  = _set_num(ref_code) or _set_num(filename)
                images.append({
                    **img,
                    "set":            set_num,
                    "display_status": _display(filename, set_num, img.get("status", "")),
                })
        except Exception:
            pass

    # When a run is active, also scan disk for images not yet in catalog
    # (matches the live overview tile which counts files directly from disk).
    if summary["status"] == "in_progress":
        cataloged = {img["filename"] for img in images}
        for f in sorted(shoot_dir.rglob("*.png")):
            if f.name in cataloged:
                continue
            ref_code = re.sub(r'^(Needs Review-|Regen-)', '', f.stem)
            set_num  = _set_num(ref_code) or _set_num(f.name)
            images.append({
                "filename":       f.name,
                "path":           str(f.relative_to(ROOT)),
                "ref_code":       ref_code,
                "set":            set_num,
                "display_status": _display(f.name, set_num),
            })

    sets: dict = {}
    for img in images:
        sets.setdefault(img["set"], []).append(img)

    return {**summary, "images": images, "sets": sets}


@app.route("/api/shoots/<path:shoot_id>")
def shoot_detail(shoot_id):
    parts = shoot_id.split("__")
    if len(parts) != 2:
        abort(404)
    month_name, shoot_name = parts
    shoot_dir = ASSET_DIR / month_name / shoot_name
    if not shoot_dir.exists():
        abort(404)
    return jsonify(_load_shoot_detail(ASSET_DIR / month_name, shoot_dir))


def _shoot_dir_from_id(shoot_id: str):
    """Return (month_dir, shoot_dir) or raise 404."""
    parts = shoot_id.split("__")
    if len(parts) != 2:
        abort(404)
    month_name, shoot_name = parts
    shoot_dir = ASSET_DIR / month_name / shoot_name
    if not shoot_dir.exists():
        abort(404)
    return ASSET_DIR / month_name, shoot_dir


def _load_catalog(shoot_dir: Path):
    """Return (catalog_dict, images_list). Raises 404 if missing."""
    p = shoot_dir / "catalog.json"
    if not p.exists():
        abort(404)
    catalog = json.loads(p.read_text())
    return catalog, catalog.get("images", [])


def _save_catalog(shoot_dir: Path, catalog: dict):
    (shoot_dir / "catalog.json").write_text(json.dumps(catalog, indent=2))


def _strip_prefix(filename: str) -> str:
    for prefix in ("Needs Review-", "Regen-"):
        if filename.startswith(prefix):
            return filename[len(prefix):]
    return filename


@app.route("/api/shoots/<path:shoot_id>/images/approve", methods=["POST"])
def approve_images(shoot_id):
    """Rename Needs-Review/Regen files → clean names, update catalog."""
    month_dir, shoot_dir = _shoot_dir_from_id(shoot_id)
    filenames = (request.get_json() or {}).get("filenames", [])
    if not filenames:
        abort(400)

    catalog, images = _load_catalog(shoot_dir)

    failed = []
    for filename in filenames:
        img = next((i for i in images if i["filename"] == filename), None)
        if not img:
            continue

        new_name = _strip_prefix(filename)

        # No prefix to strip — just mark approved in catalog
        if new_name == filename:
            img["status"] = "approved"
            continue

        src = (ROOT / img["path"]).resolve()
        if not src.exists():
            # File already gone from expected path — skip rename but keep catalog clean
            img["status"]   = "approved"
            img["filename"] = new_name
            img["id"]       = Path(new_name).stem
            img["ref_code"] = Path(new_name).stem
            continue

        dest = src.parent / new_name
        if dest.exists() and dest != src:
            dest = src.parent / f"approved-{new_name}"

        try:
            src.rename(dest)
        except Exception as e:
            failed.append(f"{filename}: {e}")
            continue  # rename failed — do NOT update catalog for this file

        img["filename"] = dest.name
        img["path"]     = str(dest.relative_to(ROOT))
        img["id"]       = dest.stem
        img["ref_code"] = dest.stem
        img["status"]   = "approved"

    if failed:
        return jsonify({"error": "Some files could not be renamed", "details": failed}), 500

    _save_catalog(shoot_dir, catalog)
    return jsonify(_load_shoot_detail(month_dir, shoot_dir))


@app.route("/api/shoots/<path:shoot_id>/images/delete", methods=["POST"])
def delete_images(shoot_id):
    """Delete image files from disk and remove them from the catalog."""
    month_dir, shoot_dir = _shoot_dir_from_id(shoot_id)
    filenames = (request.get_json() or {}).get("filenames", [])
    if not filenames:
        abort(400)

    catalog, images = _load_catalog(shoot_dir)
    filename_set = set(filenames)

    for img in list(images):
        if img["filename"] not in filename_set:
            continue
        file_path = (ROOT / img["path"]).resolve()
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass
        images.remove(img)

    catalog["images"] = images
    _save_catalog(shoot_dir, catalog)
    return jsonify(_load_shoot_detail(month_dir, shoot_dir))


@app.route("/api/image")
def serve_image():
    rel_path = request.args.get("path", "")
    if not rel_path:
        abort(400)
    # Sanitise — no path traversal
    resolved = (ROOT / rel_path).resolve()
    if not str(resolved).startswith(str(ROOT.resolve())):
        abort(403)
    if not resolved.exists():
        abort(404)
    return send_file(resolved)


@app.route("/api/agents")
def agents():
    return jsonify(_load_agents())


@app.route("/api/concept", methods=["GET"])
def concept_get():
    if not CONCEPT_PATH.exists():
        return jsonify({"text": ""})
    return jsonify({"text": CONCEPT_PATH.read_text()})

@app.route("/api/concept", methods=["POST"])
def concept_save():
    body = request.get_json(silent=True) or {}
    text = body.get("text", "")
    CONCEPT_PATH.write_text(text)
    return jsonify({"ok": True})


@app.route("/api/run/config", methods=["GET"])
def run_config_get():
    config = dict(_SHOOT_CONFIG_DEFAULTS)
    if SHOOT_CONFIG_PATH.exists():
        try:
            config.update(json.loads(SHOOT_CONFIG_PATH.read_text()))
        except Exception:
            pass
    return jsonify(config)


@app.route("/api/run/config", methods=["POST"])
def run_config_save():
    body = request.get_json(silent=True) or {}
    # Merge with existing, only update known keys
    config = dict(_SHOOT_CONFIG_DEFAULTS)
    if SHOOT_CONFIG_PATH.exists():
        try:
            config.update(json.loads(SHOOT_CONFIG_PATH.read_text()))
        except Exception:
            pass
    for key in _SHOOT_CONFIG_DEFAULTS:
        if key in body:
            config[key] = body[key]
    SHOOT_CONFIG_PATH.write_text(json.dumps(config, indent=2))
    return jsonify({"ok": True})


@app.route("/api/products")
def products():
    if not PRODUCTS_DIR.exists():
        return jsonify([])
    exts = {".jpg", ".jpeg", ".png", ".webp"}
    items = [
        {"filename": f.name, "name": f.stem, "path": str(f.relative_to(ROOT))}
        for f in sorted(PRODUCTS_DIR.iterdir())
        if f.suffix.lower() in exts
    ]
    return jsonify(items)


# ── Activity feed ────────────────────────────────────────────────────────────

STEP_AGENTS = {
    "Creative Brief":          "strategist",
    "Style Bible + Shot List": "director",
    "Image Generation":        "photographer",
    "Photo Editor Review":     "photo_editor",
}


def _file_dt(filename: str) -> str | None:
    """Extract ISO datetime string from filenames like *_YYYYMMDD_HHMM.md"""
    m = re.search(r'_(\d{8})_(\d{4})(?:\.md)?$', filename)
    if not m:
        return None
    d, t = m.group(1), m.group(2)
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}T{t[:2]}:{t[2:]}"


def _fmt_dt(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%b %d · %H:%M")
    except Exception:
        return iso


ALL_STEPS = [
    ("Creative Brief",          "strategist"),
    ("Style Bible + Shot List", "director"),
    ("Image Generation",        "photographer"),
    ("Photo Editor Review",     "photo_editor"),
    ("Catalog Writer",          "orchestrator"),
    ("Art Director Review",     "director"),
    ("Final Approval",          "orchestrator"),
]

# Regex to match per-image result lines in photo editor reports
# e.g.  ✓ FIXED | filename.png | attempts: 3
#       ✓ PASS | filename.png
#       ✗ FLAGGED_BATCH | filename.png | attempts: 1
#       ✗ REGEN | filename.png
_IMAGE_LINE_RE = re.compile(
    r'^([✓✗⚠])\s+(PASS|FIXED|FLAGGED(?:_BATCH)?|REGEN|NEEDS[_\s]REVIEW)\s*\|\s*(.+?)(?:\s*\|\s*attempts:\s*(\d+))?$',
    re.MULTILINE
)

def _short_ref(filename: str) -> str:
    """lunchbag-SPRING-26-03-20-Shoot11-S3-035.png → S3-035"""
    m = re.search(r'(S\d+-\d+)', filename)
    return m.group(1) if m else filename.split('/')[-1].replace('.png','')

def _first_cell(row: str, col: int) -> str:
    """Return the Nth pipe-delimited cell from a markdown table row (0-indexed)."""
    parts = [p.strip() for p in row.split("|")]
    # rows start/end with empty strings from leading/trailing pipes
    cells = [p for p in parts if p != ""]
    return cells[col].strip("`").strip() if col < len(cells) else ""


def _sprint_image_events(text: str, ts: str, sprint_id: str) -> list[dict]:
    """Parse per-image review events from sprint report section 6b."""
    events: list[dict] = []

    section_m = re.search(r'## 6b\. PER-IMAGE QUALITY REPORT(.+?)(?=\n## \d|\Z)', text, re.DOTALL)
    if not section_m:
        return events
    section = section_m.group(1)

    # ── First-pass approvals (bullet list) ───────────────────────────────────
    pass_m = re.search(r'### [^\n]*Approved \(First Pass\)(.*?)(?=###|\Z)', section, re.DOTALL)
    if pass_m:
        for filename in re.findall(r'`([^`]+\.png)`', pass_m.group(1)):
            ref = _short_ref(filename)
            events.append({
                "id": f"img-{sprint_id}-{ref}", "type": "image",
                "agent": "photo_editor", "outcome": "pass",
                "ref": ref, "filename": filename,
                "detail": "", "fail_reason": "", "timestamp": ts,
            })

    # ── Fixed after automated edit (table: Image | PE Failures | Fix | Attempts)
    fixed_m = re.search(r'### [^\n]*Approved \(After Automated Fix\)(.*?)(?=###|\Z)', section, re.DOTALL)
    if fixed_m:
        for row in fixed_m.group(1).splitlines():
            if not row.strip().startswith("|") or "|---|" in row:
                continue
            filename = _first_cell(row, 0)
            if not filename.endswith(".png"):
                continue
            failures = _first_cell(row, 1)
            attempts = _first_cell(row, 3)
            fail_reason = "" if failures in ("None", "—", "") else failures[:80] + ("…" if len(failures) > 80 else "")
            ref = _short_ref(filename)
            events.append({
                "id": f"img-{sprint_id}-{ref}", "type": "image",
                "agent": "photo_editor", "outcome": "fixed",
                "ref": ref, "filename": filename,
                "detail": f"attempts: {attempts}" if attempts and attempts not in ("0", "—") else "",
                "fail_reason": fail_reason, "timestamp": ts,
            })

    # ── Flagged for manual review (table: Image | Final PE Failure | Fix Attempted)
    flagged_m = re.search(r'### [^\n]*Flagged for Manual Review(.*?)(?=###|\Z)', section, re.DOTALL)
    if flagged_m:
        for row in flagged_m.group(1).splitlines():
            if not row.strip().startswith("|") or "|---|" in row:
                continue
            filename = _first_cell(row, 0)
            if not filename.endswith(".png"):
                continue
            failures = _first_cell(row, 1)
            fail_reason = "" if failures in ("N/A", "—", "") else failures[:80] + ("…" if len(failures) > 80 else "")
            ref = _short_ref(filename)
            events.append({
                "id": f"img-{sprint_id}-{ref}", "type": "image",
                "agent": "photo_editor", "outcome": "flagged",
                "ref": ref, "filename": filename,
                "detail": "", "fail_reason": fail_reason, "timestamp": ts,
            })

    return events


def _first_fail(block: str) -> str:
    """Extract the first FAIL criterion description from an image review block."""
    m = re.search(r'\d+\.\s+[\w\s]+:\s+FAIL\s+[—–-]\s+(.+?)(?:\n|$)', block)
    if m:
        txt = m.group(1).strip()
        return txt[:80] + ('…' if len(txt) > 80 else '')
    return ""

CHECKPOINT_PATH = OUTPUTS_DIR / "photo_editor_checkpoint.json"
TIMING_PATH     = OUTPUTS_DIR / "shoot_timing.json"
_LIVE_WINDOW_S  = 600   # checkpoint younger than 10 min = live run


def _read_live_state() -> dict:
    """Return current pipeline state from live files, or empty dict if idle."""
    import time as _time
    result: dict = {"active": False, "phase": None, "checkpoint": None, "timing": None}

    # ── Timing file: primary signal for run state ─────────────────────────────
    timing: dict = {}
    if TIMING_PATH.exists():
        try:
            timing = json.loads(TIMING_PATH.read_text())
            result["timing"] = timing
        except Exception:
            pass

    # If shoot_end is present the run finished — never show as live
    run_finished = bool(timing.get("shoot_end"))

    if not run_finished and timing.get("shoot_start"):
        result["active"] = True
        result["phase"]  = "generation"

    # ── Checkpoint: only valid while the run hasn't finished ──────────────────
    if not run_finished and CHECKPOINT_PATH.exists():
        try:
            age = _time.time() - CHECKPOINT_PATH.stat().st_mtime
            if age < _LIVE_WINDOW_S:
                ckpt = json.loads(CHECKPOINT_PATH.read_text())
                result["checkpoint"] = ckpt
                result["active"]     = True
                result["phase"]      = "photo_editor"
        except Exception:
            pass

    return result


def _checkpoint_events(ckpt: dict) -> list[dict]:
    """Convert photo_editor_checkpoint image_results to activity events."""
    _STATUS = {
        "PASS":         "pass",
        "FIXED":        "fixed",
        "FLAGGED":      "flagged",
        "FLAGGED_BATCH":"flagged",
        "REGEN_NEEDED": "regen",
    }
    now_iso = datetime.now().isoformat(timespec="seconds")
    events  = []
    for r in ckpt.get("image_results", []):
        filename = r.get("file", "")
        status   = r.get("status", "")
        outcome  = _STATUS.get(status, "pass")
        ref      = _short_ref(filename)
        fail_reason = _first_fail(r.get("review", "")) if outcome not in ("pass",) else ""
        attempts = r.get("attempts")
        events.append({
            "id":          f"live-{filename}",
            "type":        "image",
            "agent":       "photo_editor",
            "outcome":     outcome,
            "ref":         ref,
            "filename":    filename,
            "detail":      f"attempts: {attempts}" if attempts and attempts != 0 else "",
            "fail_reason": fail_reason,
            "concept":     "",
            "timestamp":   now_iso,
            "live":        True,
        })
    # Prepend a "running" banner
    set_num  = ckpt.get("set", "?")
    reviewed = len(ckpt.get("image_results", []))
    passed   = ckpt.get("passed_first", 0) + ckpt.get("fixed", 0)
    flagged  = ckpt.get("flagged", 0)
    events.insert(0, {
        "id":        "live-banner",
        "type":      "live_banner",
        "agent":     "photo_editor",
        "outcome":   "summary",
        "ref":       f"Set {set_num}",
        "detail":    f"{reviewed} reviewed · {passed} approved · {flagged} flagged",
        "timestamp": now_iso,
        "live":      True,
    })
    return events


PROGRESS_PATH    = OUTPUTS_DIR / "run_progress.json"
PROGRESS_P2_PATH = OUTPUTS_DIR / "run_progress_p2.json"


def _mark_progress_stopped(path: Path) -> None:
    """Mark a progress file as stopped so is_live clears immediately after a manual stop."""
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
        if data.get("status") in ("in_progress", "paused"):
            data["status"] = "stopped"
            data["completed_at"] = datetime.utcnow().isoformat()
            path.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _mark_progress_paused(path: Path) -> None:
    """Mark a progress file as paused so live indicators dim immediately."""
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
        if data.get("status") == "in_progress":
            data["status"] = "paused"
            path.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _mark_progress_resumed(path: Path) -> None:
    """Mark a progress file as in_progress again after a resume."""
    if not path.exists():
        return
    try:
        data = json.loads(path.read_text())
        if data.get("status") == "paused":
            data["status"] = "in_progress"
            data.pop("completed_at", None)
            path.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


def _read_progress() -> dict | None:
    """Read run_progress.json if it exists."""
    if PROGRESS_PATH.exists():
        try:
            return json.loads(PROGRESS_PATH.read_text())
        except Exception:
            return None
    return None


def _read_progress_p2() -> dict | None:
    """Read run_progress_p2.json if it exists."""
    if PROGRESS_P2_PATH.exists():
        try:
            return json.loads(PROGRESS_P2_PATH.read_text())
        except Exception:
            return None
    return None


def _progress_fmt(seconds) -> str:
    """Format duration_s to a readable string."""
    if not seconds:
        return "—"
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m = s // 60
    if m < 60:
        return f"{m}'"
    h, rem = divmod(m, 60)
    return f"{h}h {rem}'" if rem else f"{h}h"


def _checkpoint_children(set_num: str) -> list[dict]:
    """
    Read photo_editor_checkpoint.json and return per-image review results
    as child event dicts for the live-count event.
    """
    _OUTCOME = {
        "PASS":          "pass",
        "FIXED":         "fixed",
        "FLAGGED":       "flagged",
        "FLAGGED_BATCH": "flagged_batch",
        "REGEN_NEEDED":  "regen",
    }
    children = []
    if not CHECKPOINT_PATH.exists():
        return children
    try:
        ckpt = json.loads(CHECKPOINT_PATH.read_text())
        # Only use checkpoint if it matches the current set
        if str(ckpt.get("set", "")) != str(set_num):
            return children

        for r in ckpt.get("image_results", []):
            status   = r.get("status", "PASS")
            outcome  = _OUTCOME.get(status, "pass")
            ref      = _short_ref(r.get("file", ""))
            attempts = r.get("attempts")
            fix      = r.get("fix", "")

            # Build the detail line
            if outcome == "pass":
                detail = "passed"
            elif outcome == "fixed":
                detail = f"fixed on attempt {attempts}"
                if fix:
                    detail += f" — {fix[:80]}{'…' if len(fix) > 80 else ''}"
            elif outcome == "flagged_batch":
                # Batch reason stored as "\nFAILED BATCH CHECK: reason" in review
                review = r.get("review", "")
                m = re.search(r"FAILED BATCH CHECK:\s*(.+)", review)
                detail = m.group(1).strip()[:100] if m else "failed batch check"
                detail = "batch: " + detail
            elif outcome in ("flagged", "regen"):
                detail = _first_fail(r.get("review", "")) or fix[:80] or "flagged"
            else:
                detail = status.lower()

            children.append({
                "ref":      ref,
                "outcome":  outcome,
                "detail":   detail,
                "attempts": attempts,
            })
    except Exception:
        pass
    return children


def _progress_current_label(progress: dict) -> str:
    """Return the label of the currently running milestone."""
    for m in progress.get("milestones", []):
        if m["status"] == "in_progress":
            return m["label"]
    return "Running…"


COUNTERS_PATH = OUTPUTS_DIR / "api_counters.json"


def _live_stats(progress: dict) -> dict:
    """
    Build a stats dict for the currently running shoot from live sources:
    run_progress.json milestones, disk image counts, and api_counters.json.
    Shape matches _load_shoot() so Dashboard tiles work unchanged.
    """
    import time as _time

    shoot_folder  = progress.get("shoot_folder", "")
    run_id        = progress.get("run_id", "Live Run")
    started_at    = progress.get("started_at", "")
    milestones    = {m["id"]: m for m in progress.get("milestones", [])}

    # ── Elapsed runtime ───────────────────────────────────────────────────────
    runtime = "—"
    if started_at:
        try:
            elapsed = _time.time() - datetime.fromisoformat(started_at).timestamp()
            runtime = _progress_fmt(int(elapsed))
        except Exception:
            pass

    # ── Step timings — completed = recorded duration, in_progress = live elapsed
    def _ms_dur(mid: str):
        m = milestones.get(mid)
        if not m:
            return None
        if m.get("duration_s"):
            return _progress_fmt(m["duration_s"])
        if m.get("status") == "in_progress" and m.get("started_at"):
            try:
                elapsed = _time.time() - datetime.fromisoformat(m["started_at"]).timestamp()
                return _progress_fmt(int(elapsed)) + "…"
            except Exception:
                pass
        return None

    def _sum_dur(*mids):
        total       = 0
        live        = False
        for mid in mids:
            m = milestones.get(mid)
            if not m:
                continue
            if m.get("duration_s"):
                total += m["duration_s"]
            elif m.get("status") == "in_progress" and m.get("started_at"):
                try:
                    elapsed = _time.time() - datetime.fromisoformat(m["started_at"]).timestamp()
                    total  += int(elapsed)
                    live    = True
                except Exception:
                    pass
        if not total:
            return None
        return _progress_fmt(total) + ("…" if live else "")

    time_brief            = _ms_dur("creative_brief")
    time_style_bible      = _ms_dur("style_bible")
    time_generation       = _sum_dur("image_gen_set_1", "image_gen_set_2", "image_gen_set_3")
    time_photo_editor     = _sum_dur("photo_editor_set_1", "photo_editor_set_2", "photo_editor_set_3")
    time_copywriter       = _ms_dur("copywriter")
    time_content_planner  = _ms_dur("content_planner")
    time_review_generator = _ms_dur("review_generator")

    # ── Image counts from disk ────────────────────────────────────────────────
    total_images = approved = needs_review = regen = 0
    if shoot_folder:
        shoot_dir = ROOT / "asset_library" / "images" / shoot_folder
        if shoot_dir.exists():
            for f in shoot_dir.rglob("*.png"):
                total_images += 1
                name = f.name
                if name.startswith("Regen-"):
                    regen += 1
                elif "Needs Review" in name:
                    needs_review += 1
                else:
                    approved += 1

    # ── API counters ──────────────────────────────────────────────────────────
    calls_image = calls_text = 0
    if COUNTERS_PATH.exists():
        try:
            c = json.loads(COUNTERS_PATH.read_text())
            calls_image = c.get("image_gen_calls", 0)
            calls_text  = (c.get("text_calls", 0)
                           + c.get("review_calls", 0)
                           + c.get("fix_calls", 0)
                           + c.get("batch_check_calls", 0)
                           + c.get("preflight_calls", 0))
        except Exception:
            pass

    # ── Error counts from log ─────────────────────────────────────────────────
    errors_fixed = errors_flagged = 0
    for entry in progress.get("log", []):
        if entry.get("type") == "retry":
            errors_fixed += 1       # rough proxy — retries that resolved
        elif entry.get("type") == "fail":
            errors_flagged += 1

    return {
        "id":                shoot_folder.replace("/", "__") if shoot_folder else "live",
        "name":              shoot_folder.split("/")[-1] if shoot_folder else run_id,
        "month":             shoot_folder.split("/")[0]  if "/" in shoot_folder else "",
        "date":              "",
        "status":            "in_progress",
        "sprint_id":         run_id,
        # Image counts
        "total_images":      total_images,
        "approved":          approved,
        "needs_review":      needs_review,
        "regen":             regen,
        # Timings
        "runtime":               runtime,
        "time_brief":            time_brief,
        "time_style_bible":      time_style_bible,
        "time_generation":       time_generation,
        "time_photo_editor":     time_photo_editor,
        "time_copywriter":       time_copywriter,
        "time_content_planner":  time_content_planner,
        "time_review_generator": time_review_generator,
        # API
        "total_calls":       calls_image + calls_text,
        "calls_image_model": calls_image,
        "calls_text_model":  calls_text,
        "total_cost":        0.0,
        "cost_image_model":  0.0,
        "cost_text_model":   0.0,
        "image_model_name":  "Image model",
        "text_model_name":   "Text model",
        # Errors (rough live estimates)
        "errors":            str(errors_fixed + errors_flagged),
        "errors_fixed":      str(errors_fixed),
        "errors_flagged":    str(errors_flagged),
        "errors_total":      errors_fixed + errors_flagged,
        "pass_rate":         "—",
    }


def _p2_stats(progress: dict) -> dict:
    """
    Build dashboard-tile stats from a Phase 2 run_progress_p2.json.
    Uses the same shape as _live_stats / _load_shoot so tiles render unchanged,
    but repurposes the 'images' tile for content-plan post counts.
    """
    import time as _time

    started_at  = progress.get("started_at", "")
    milestones  = {m["id"]: m for m in progress.get("milestones", [])}
    is_live     = progress.get("status") == "in_progress"

    # ── Runtime ──────────────────────────────────────────────────────────────
    runtime = "—"
    if started_at:
        try:
            completed_at = progress.get("completed_at")
            if completed_at:
                elapsed = (datetime.fromisoformat(completed_at)
                           - datetime.fromisoformat(started_at)).total_seconds()
            else:
                elapsed = _time.time() - datetime.fromisoformat(started_at).timestamp()
            runtime = _progress_fmt(int(elapsed)) + ("…" if is_live and not completed_at else "")
        except Exception:
            pass

    # ── Step timings ─────────────────────────────────────────────────────────
    def _dur(mid: str):
        m = milestones.get(mid)
        if not m:
            return None
        if m.get("duration_s"):
            return _progress_fmt(m["duration_s"])
        if m.get("status") == "in_progress" and m.get("started_at"):
            try:
                elapsed = _time.time() - datetime.fromisoformat(m["started_at"]).timestamp()
                return _progress_fmt(int(elapsed)) + "…"
            except Exception:
                pass
        return None

    # ── Post counts + plan label from monthly_calendar.json ──────────────────
    total_posts = single_posts = carousel_posts = 0
    plan_label  = ""
    calendar_path = CONTENT_DIR / "monthly_calendar.json"
    if not calendar_path.exists():
        calendar_path = CONTENT_DIR / "weekly_calendar.json"
    if calendar_path.exists():
        try:
            cal = json.loads(calendar_path.read_text())
            plan_label = cal.get("month_of", "")
            for p in cal.get("posts", []):
                total_posts += 1
                if p.get("type") == "carousel":
                    carousel_posts += 1
                else:
                    single_posts += 1
        except Exception:
            pass

    # ── API counters ──────────────────────────────────────────────────────────
    calls_text = 0
    if COUNTERS_PATH.exists():
        try:
            c = json.loads(COUNTERS_PATH.read_text())
            calls_text = (c.get("text_calls", 0)
                          + c.get("review_calls", 0)
                          + c.get("fix_calls", 0)
                          + c.get("batch_check_calls", 0)
                          + c.get("preflight_calls", 0))
        except Exception:
            pass

    return {
        "phase":             "content_planning",
        "id":                "content_plan_latest",
        "name":              progress.get("run_id", "Content Plan"),
        "status":            progress.get("status", "completed"),
        # Repurposed "images" tile → content plan post counts
        "total_images":      total_posts,
        "approved":          single_posts,
        "needs_review":      carousel_posts,
        "regen":             0,
        # Timings — Phase 2 only
        "runtime":               runtime,
        "time_brief":            None,
        "time_generation":       None,
        "time_photo_editor":     None,
        "time_copywriter":       _dur("copywriter"),
        "time_content_planner":  _dur("content_planner"),
        "time_review_generator": _dur("review_generator"),
        # API
        "total_calls":       calls_text,
        "calls_image_model": 0,
        "calls_text_model":  calls_text,
        "image_model_name":  None,
        "text_model_name":   "Text model",
        "total_cost":        0.0,
        "cost_image_model":  0.0,
        "cost_text_model":   0.0,
        # Errors
        "errors":            "0",
        "errors_fixed":      "0",
        "errors_flagged":    "0",
        "errors_total":      0,
        "pass_rate":         "—",
        "plan_label":        plan_label,
    }


@app.route("/api/activity")
def activity():
    events: list[dict] = []
    tasks:  list[dict] = []

    # ── Progress tracker file (primary source) ────────────────────────────────
    progress = _read_progress()
    is_live  = bool(progress and progress.get("status") == "in_progress")

    if progress:
        run_id       = progress.get("run_id", "")
        shoot_folder = progress.get("shoot_folder", "")

        # Build shoot_id from shoot_folder ("2025-03/Shoot01" → "2025-03__Shoot01")
        _sf_parts = shoot_folder.replace("\\", "/").split("/") if shoot_folder else []
        shoot_id  = f"{_sf_parts[0]}__{_sf_parts[1]}" if len(_sf_parts) == 2 else None

        # Tasks come from milestones
        for m in progress.get("milestones", []):
            task_entry = {
                "agent":        m.get("agent", ""),
                "task":         m["label"],
                "duration":     _progress_fmt(m.get("duration_s")),
                "sprint_id":    run_id,
                "timestamp":    m.get("started_at") or progress.get("started_at", ""),
                "status":       m["status"],
                "milestone_id": m["id"],
            }
            mid = m["id"]
            if mid.startswith("image_gen_set_"):
                set_num = mid.split("_")[-1]
                if shoot_id and shoot_folder:
                    set_dir = ASSET_DIR / shoot_folder / f"Set{set_num}"
                    if set_dir.exists():
                        task_entry["shoot_link"] = f"/photoshoots/{shoot_id}"
                        task_entry["shoot_set"]  = int(set_num)
            elif mid == "sprint_report" and m["status"] == "completed":
                if _latest_report("photoshoot_"):
                    task_entry["report_ready"] = True
                    task_entry["report_type"]  = "photoshoot"
            elif mid == "sprint_report_p2" and m["status"] == "completed":
                if _latest_report("content_plan_"):
                    task_entry["report_ready"] = True
                    task_entry["report_type"]  = "content_plan"
            tasks.append(task_entry)

        # Live banner pinned at top when active
        if is_live:
            events.append({
                "id":     "live-banner",
                "type":   "live_banner",
                "live":   True,
                "ref":    run_id,
                "detail": _progress_current_label(progress),
            })

        # Image-count events — one per set milestone that has started.
        # In-progress: shows live disk count. Completed: shows final count.
        # These persist in the feed; nothing is removed when a set finishes.
        shoot_folder  = progress.get("shoot_folder", "")
        set_expected  = progress.get("set_expected", {})
        for m in progress.get("milestones", []):
            if m["status"] not in ("in_progress", "completed"):
                continue
            mid  = m["id"]
            live = m["status"] == "in_progress"
            # image_gen_set_N  or  photo_editor_set_N
            if not (mid.startswith("image_gen_set_") or mid.startswith("photo_editor_set_")):
                continue
            set_num = mid.split("_")[-1]          # "1", "2", "3"
            if not shoot_folder:
                continue
            set_dir = ROOT / "asset_library" / "images" / shoot_folder / f"Set{set_num}"
            total   = (set_expected.get(set_num)
                       or set_expected.get(int(set_num), "?")) if set_expected else "?"
            action  = "generated" if mid.startswith("image_gen") else "reviewed"

            disk_count = len(list(set_dir.glob("*.png"))) if set_dir.exists() else 0
            count      = disk_count if live or set_dir.exists() else total

            # For photo_editor: attach per-image review results as children
            children = []
            if mid.startswith("photo_editor_set_"):
                children = _checkpoint_children(set_num)
                reviewed = len(children)
                action   = f"reviewed ({reviewed}/{total})" if children else "queued for review"

            events.append({
                "id":            f"live-count-set-{set_num}-{'gen' if mid.startswith('image_gen') else 'pe'}",
                "type":          "progress",
                "progress_type": "update" if live else "complete",
                "live":          live,
                "ref":           mid,
                "detail":        f"Set {set_num}: {count}/{total} images {action}",
                "timestamp":     m.get("completed_at") if not live else None,
                "children":      children,
            })

        # Milestone log events (newest-first)
        for entry in reversed(progress.get("log", [])):
            events.append({
                "id":            f"prog-{entry['ts']}-{entry.get('milestone', '')}",
                "type":          "progress",
                "progress_type": entry["type"],          # start|retry|complete|fail
                "agent":         "",
                "ref":           entry.get("milestone", ""),
                "detail":        entry["message"],
                "timestamp":     entry["ts"],
            })

    # ── Sprint reports → per-image QC events + summary ───────────────────────
    # Skip sprint reports while a run is active — the progress log is the live
    # source of truth and historical reports from previous runs would pollute it.
    if not is_live and REPORTS_DIR.exists():
        for f in sorted(
            (f for f in REPORTS_DIR.iterdir() if f.name.endswith(".md")),
            key=lambda p: _file_dt(p.name) or "",
            reverse=True,
        ):
            try:
                text      = f.read_text()
                ts        = _file_dt(f.name)
                sprint_id = _parse_table_value(text, "Sprint ID") or f.stem
                images_gen = _parse_table_value(text, "Images generated") or "?"
                approved   = _parse_table_value(text, "Images approved")  or "?"
                runtime    = _parse_table_value(text, "Total runtime")    or ""

                events.append({
                    "id":        f"sprint-{f.name}",
                    "type":      "sprint",
                    "agent":     "orchestrator",
                    "outcome":   "summary",
                    "ref":       sprint_id,
                    "detail":    f"{images_gen} generated · {approved} approved"
                                 + (f" · {runtime}" if runtime else ""),
                    "timestamp": ts,
                    "status":    "success",
                })

                img_events = _sprint_image_events(text, ts, sprint_id)
                if img_events:
                    total_rev = _parse_table_value(text, "Total reviewed") or str(len(img_events))
                    approval  = _parse_table_value(text, "Final approval rate") or "?"
                    events.append({
                        "id":        f"review-summary-{f.name}",
                        "type":      "review_summary",
                        "agent":     "photo_editor",
                        "outcome":   "summary",
                        "ref":       "",
                        "detail":    f"{total_rev} images reviewed · {approval} approved",
                        "timestamp": ts,
                        "status":    "success",
                    })
                    events.extend(img_events)

                # Fall back to sprint-report tasks if no progress file
                if not tasks:
                    for step_label, agent_id in ALL_STEPS:
                        val = _parse_table_value(text, step_label)
                        ran = val and val not in ("0s", "0m 0s", "—", "0")
                        tasks.append({
                            "agent":     agent_id,
                            "task":      step_label,
                            "duration":  val if ran else "—",
                            "sprint_id": sprint_id,
                            "timestamp": ts,
                            "status":    "completed" if ran else "pending",
                        })

            except Exception:
                pass

    # ── Sort: live banner first, then newest-first ────────────────────────────
    live_pinned = [e for e in events if e.get("live")]
    historical  = [e for e in events if not e.get("live")]
    historical.sort(key=lambda e: (e.get("timestamp") or "", e.get("id", "")), reverse=True)
    events = live_pinned + historical

    return jsonify({
        "events":  events[:100],
        "tasks":   tasks,
        "is_live": is_live,
    })


@app.route("/api/status")
def app_status():
    """Lightweight polling endpoint for nav badges and run lifecycle toasts."""
    shoots            = _all_shoots()
    needs_review_count = sum(s.get("needs_review", 0) for s in shoots if s["status"] != "empty")

    progress     = _read_progress()
    p1_actually_running = process_manager.state != 'idle'
    if progress and progress.get("status") in ("in_progress", "paused") and not p1_actually_running:
        _mark_progress_stopped(PROGRESS_PATH)
        progress = _read_progress()
    is_live      = bool(progress and progress.get("status") == "in_progress")
    run_id       = progress.get("run_id")    if progress else None
    run_status   = progress.get("status")    if progress else None
    failed_step  = None
    sprint_ready = False

    if progress:
        for m in progress.get("milestones", []):
            if m["status"] == "failed" and not failed_step:
                failed_step = m["label"]
            if m["id"] == "sprint_report" and m["status"] == "completed":
                sprint_ready = bool(_latest_report("photoshoot_"))

    completed_summary = None
    if run_status == "completed" and progress:
        shoot_folder = progress.get("shoot_folder", "")
        total = 0
        if shoot_folder:
            sd = ROOT / "asset_library" / "images" / shoot_folder
            if sd.exists():
                total = len(list(sd.rglob("*.png")))
        started   = progress.get("started_at", "")
        completed = progress.get("completed_at", "")
        runtime   = ""
        if started and completed:
            try:
                elapsed = (datetime.fromisoformat(completed).timestamp()
                           - datetime.fromisoformat(started).timestamp())
                runtime = _progress_fmt(int(elapsed))
            except Exception:
                pass
        completed_summary = {"total_images": total, "runtime": runtime}

    has_log_errors = False
    if LOG_PATH.exists():
        try:
            lines = LOG_PATH.read_text().splitlines()[-300:]
            has_log_errors = any('"level": "ERROR"' in ln for ln in lines)
        except Exception:
            pass

    # Find which agent is currently active (in_progress milestone)
    active_agent = None
    if progress and is_live:
        for m in progress.get("milestones", []):
            if m.get("status") == "in_progress":
                active_agent = m.get("agent")
                break
    if not active_agent:
        progress_p2 = _read_progress_p2()
    if not active_agent and progress_p2 and progress_p2.get("status") == "in_progress":
        for m in progress_p2.get("milestones", []):
            if m.get("status") == "in_progress":
                active_agent = m.get("agent")
                break

    return jsonify({
        "is_live":           is_live,
        "p1_live":           process_manager.state    != 'idle',
        "p2_live":           process_manager_p2.state != 'idle',
        "needs_review":      needs_review_count,
        "has_log_errors":    has_log_errors,
        "run_id":            run_id,
        "run_status":        run_status,
        "failed_step":       failed_step,
        "sprint_ready":      sprint_ready,
        "sprint_ready_p2":   bool(_latest_report("content_plan_")),
        "completed_summary": completed_summary,
        "active_agent":      active_agent,
    })


# ── Run log ──────────────────────────────────────────────────────────────────

LOG_PATH = OUTPUTS_DIR / "run.log"


def _parse_sprint_report_full(path: Path) -> dict:
    """Deep parse of a sprint report markdown for the SprintReport page."""
    try:
        text = path.read_text()
        r: dict = {}

        # Header
        m = re.search(r'Sprint:\s*(.+)', text)
        r["sprint_id"] = m.group(1).strip() if m else ""
        m = re.search(r'Date:\s*(.+)', text)
        r["date"] = m.group(1).strip() if m else ""

        def val(label):
            return _parse_table_value(text, label) or ""

        r["started"]           = val("Started")
        r["completed"]         = val("Completed")
        r["runtime"]           = val("Total runtime")
        r["images_generated"]  = val("Images generated")
        r["images_approved"]   = val("Images approved")
        r["pass_rate"]         = val("First-pass approval rate")
        r["needs_review"]      = val("Needs manual review")
        r["errors"]            = val("Errors") or "0"

        # Step timing
        steps = []
        sec = re.search(r'## 2\. STEP TIMING.*?(?=\n## |\Z)', text, re.DOTALL)
        if sec:
            for row in re.finditer(
                r'^\|\s*([^|*\-][^|]*?)\s*\|\s*([^|*\-][^|]*?)\s*\|',
                sec.group(), re.MULTILINE
            ):
                label, dur = row.group(1).strip(), row.group(2).strip()
                if label.lower() != "step" and label:
                    steps.append({"name": label, "duration": dur})
        r["steps"] = steps

        # Image quality (Photo Editor)
        r["quality"] = {
            "total_reviewed": val("Total reviewed"),
            "first_pass":     val("First-pass approval"),
            "fixed":          val("Fixed by editing"),
            "final_rate":     val("Final approval rate"),
            "flagged":        val("Flagged for manual review"),
            "flagged_batch":  val("Flagged by batch check"),
        }

        # Fix attempt distribution
        attempts = []
        sec = re.search(r'Fix Attempt Distribution.*?(?=\n###|\n##|\Z)', text, re.DOTALL)
        if sec:
            for row in re.finditer(
                r'^\|\s*([^|\-*][^|]*?)\s*\|\s*(\d+)\s*\|',
                sec.group(), re.MULTILINE
            ):
                attempts.append({"label": row.group(1).strip(), "count": int(row.group(2))})
        r["fix_attempts"] = attempts

        # Per-image breakdown (section 6b)
        images: dict = {"approved_first": [], "approved_fixed": [], "flagged": []}

        sec = re.search(r'Approved \(First Pass\)(.*?)(?=###|\n##|\Z)', text, re.DOTALL)
        if sec:
            images["approved_first"] = re.findall(r'`([^`]+)`', sec.group(1))

        sec = re.search(r'Approved \(After Automated Fix\)(.*?)(?=### ✗|### Flagged|\n##|\Z)', text, re.DOTALL)
        if sec:
            for row in re.finditer(
                r'^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(\d+)\s*\|',
                sec.group(1), re.MULTILINE
            ):
                images["approved_fixed"].append({
                    "image":    row.group(1).strip().lstrip("Needs Review-"),
                    "failures": row.group(2).strip()[:200],
                    "fix":      row.group(3).strip()[:200],
                    "attempts": int(row.group(4)),
                })

        sec = re.search(r'Flagged for Manual Review(.*?)(?=\n===|\n##|\Z)', text, re.DOTALL)
        if sec:
            for row in re.finditer(
                r'^\|\s*`([^`]+)`\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|',
                sec.group(1), re.MULTILINE
            ):
                fname = row.group(1).strip()
                images["flagged"].append({
                    "image":         re.sub(r'^Needs Review-', '', fname),
                    "failure":       row.group(2).strip()[:300],
                    "fix_attempted": row.group(3).strip(),
                })
        r["images"] = images

        # API usage
        def model_row(label):
            m = re.search(
                rf'\|\s*{re.escape(label)}\s*\|\s*\*{{0,2}}(\d+)\*{{0,2}}\s*\|\s*\*{{0,2}}\$?([\d.]+)\*{{0,2}}',
                text
            )
            return (int(m.group(1)), float(m.group(2))) if m else (0, 0.0)

        img_calls, img_cost = model_row("Image generation model")
        txt_calls, txt_cost = model_row("Text/vision model")
        m = re.search(r'###\s*(gemini[^\n]*image[^\n]*)', text, re.IGNORECASE)
        img_model = m.group(1).strip() if m else "Image model"
        m = re.search(r'###\s*(gemini-2\.[^\n]+)', text, re.IGNORECASE)
        txt_model = m.group(1).strip() if m else "Text model"
        m = re.search(r'\*\*Total\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*\$?([\d.]+)\*\*', text)
        total_calls = int(m.group(1))  if m else img_calls + txt_calls
        total_cost  = float(m.group(2)) if m else round(img_cost + txt_cost, 2)

        r["api"] = {
            "image_model": {"name": img_model, "calls": img_calls, "cost": img_cost},
            "text_model":  {"name": txt_model, "calls": txt_calls, "cost": txt_cost},
            "total_calls": total_calls,
            "total_cost":  total_cost,
        }

        # Recommendations
        recs = []
        sec = re.search(r'## 10\. RECOMMENDATIONS.*', text, re.DOTALL)
        if sec:
            recs = [ln.strip().lstrip("- ").strip()
                    for ln in re.findall(r'^- .+', sec.group(), re.MULTILINE)]
        r["recommendations"] = recs

        r["filename"]     = path.name
        r["generated_at"] = _file_dt(path.name) or ""
        return r
    except Exception as e:
        return {"error": str(e)}


def _latest_report(prefix: str):
    """Return the most recent report file matching the given prefix, or None."""
    if not REPORTS_DIR.exists():
        return None
    files = sorted(
        [f for f in REPORTS_DIR.iterdir() if f.name.startswith(prefix) and f.name.endswith(".md")],
        key=lambda p: _file_dt(p.name) or "",
        reverse=True,
    )
    return files[0] if files else None


@app.route("/api/photoshoot-report")
def photoshoot_report_endpoint():
    report = _latest_report("photoshoot_")
    if not report:
        return jsonify({"error": "No photoshoot report found"}), 404
    return jsonify(_parse_sprint_report_full(report))


@app.route("/api/content-plan-report")
def content_plan_report_endpoint():
    report = _latest_report("content_plan_")
    if not report:
        return jsonify({"error": "No content plan report found"}), 404
    return jsonify(_parse_sprint_report_full(report))


# ── Search ───────────────────────────────────────────────────────────────────

@app.route("/api/search")
def search():
    q = request.args.get("q", "").strip().lower()
    if len(q) < 2:
        return jsonify({"shoots": [], "images": [], "posts": []})

    out = {"shoots": [], "images": [], "posts": []}

    # Shoots + images
    if ASSET_DIR.exists():
        for month_dir in sorted(ASSET_DIR.iterdir(), reverse=True):
            if not month_dir.is_dir():
                continue
            for shoot_dir in sorted(month_dir.iterdir(), reverse=True):
                if not shoot_dir.is_dir():
                    continue
                shoot_name = shoot_dir.name
                month_name = month_dir.name
                shoot_id   = f"{month_name}__{shoot_name}"

                if q in shoot_name.lower() or q in month_name.lower():
                    out["shoots"].append({
                        "id":    shoot_id,
                        "name":  shoot_name,
                        "month": month_name,
                        "url":   f"/photoshoots/{shoot_id}",
                    })

                catalog_path = shoot_dir / "catalog.json"
                if catalog_path.exists() and len(out["images"]) < 20:
                    try:
                        catalog = json.loads(catalog_path.read_text())
                        for img in catalog.get("images", []):
                            fname = img.get("filename", "")
                            ref   = img.get("ref_code", "")
                            set_  = img.get("path", "").split("/")[-2] if "/" in img.get("path", "") else ""
                            if q in fname.lower() or q in ref.lower() or q in set_.lower():
                                out["images"].append({
                                    "filename": fname,
                                    "path":     img.get("path", ""),
                                    "shoot_id": shoot_id,
                                    "shoot":    shoot_name,
                                    "month":    month_name,
                                    "status":   img.get("status", ""),
                                    "url":      f"/photoshoots/{shoot_id}",
                                })
                                if len(out["images"]) >= 20:
                                    break
                    except Exception:
                        pass

    out["shoots"] = out["shoots"][:10]

    # Posts
    calendar_path = CONTENT_DIR / "monthly_calendar.json"
    if not calendar_path.exists():
        calendar_path = CONTENT_DIR / "weekly_calendar.json"
    if calendar_path.exists():
        try:
            cal = json.loads(calendar_path.read_text())
            for post in cal.get("posts", []):
                caption  = post.get("caption", "")
                tags     = " ".join(post.get("hashtags", []))
                date_str = post.get("date", "")
                if q in caption.lower() or q in tags.lower() or q in date_str:
                    out["posts"].append({
                        "slot":    post.get("slot", ""),
                        "date":    date_str,
                        "type":    post.get("type", ""),
                        "caption": caption[:120],
                        "url":     "/content-planning",
                    })
                    if len(out["posts"]) >= 10:
                        break
        except Exception:
            pass

    return jsonify(out)


# ── Run log ──────────────────────────────────────────────────────────────────

@app.route("/api/logs")
def run_logs():
    lines = int(request.args.get("lines", 500))
    if not LOG_PATH.exists():
        return jsonify({"entries": [], "is_live": False})

    progress = _read_progress()
    is_live  = bool(progress and progress.get("status") == "in_progress")

    try:
        raw = LOG_PATH.read_text().splitlines()
    except Exception:
        return jsonify({"entries": [], "is_live": is_live})

    entries = []
    for line in raw[-lines:]:
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except Exception:
            # Plain text fallback
            entries.append({"ts": "", "level": "INFO", "src": "pipeline", "msg": line})

    return jsonify({"entries": entries, "is_live": is_live})


# ── Content Planning ────────────────────────────────────────────────────────

CONTENT_DIR = OUTPUTS_DIR


def _build_ref_index() -> dict:
    """Walk all catalog.json files and build ref_code → path lookup."""
    index = {}
    if not ASSET_DIR.exists():
        return index
    for catalog_path in ASSET_DIR.rglob("catalog.json"):
        try:
            data = json.loads(catalog_path.read_text())
            for img in data.get("images", []):
                rc = img.get("ref_code") or img.get("id")
                if rc and img.get("path"):
                    index[rc] = img["path"]
        except Exception:
            pass
    return index


def _resolve_image(filename: str, ref_code: str, ref_index: dict) -> str | None:
    """Return a relative path for an image, or None if not found."""
    # 1. Try catalog index
    if ref_code and ref_code in ref_index:
        return ref_index[ref_code]
    # 2. Scan asset_library for filename
    if filename:
        matches = list(ASSET_DIR.rglob(filename))
        if matches:
            return str(matches[0].relative_to(ROOT))
    return None


def _post_status(date_str: str, time_str: str) -> str:
    if not date_str:
        return "pending"
    try:
        dt = datetime.fromisoformat(f"{date_str}T{time_str or '00:00'}")
        return "published" if dt < datetime.now() else "scheduled"
    except Exception:
        return "pending"


@app.route("/api/content/posts")
def content_posts():
    """Return planned posts from monthly_calendar.json enriched with copy data."""
    calendar_path = CONTENT_DIR / "monthly_calendar.json"
    if not calendar_path.exists():
        calendar_path = CONTENT_DIR / "weekly_calendar.json"
    if not calendar_path.exists():
        return jsonify([])

    try:
        calendar = json.loads(calendar_path.read_text())
    except Exception:
        return jsonify([])

    # Build copy lookup: ref_code → copy entry
    copy_index: dict = {}
    copy_path = CONTENT_DIR / "copy_latest.json"
    if copy_path.exists():
        try:
            copy_data = json.loads(copy_path.read_text())
            for entry in copy_data.get("copy", []):
                rc = entry.get("ref_code", "")
                if rc:
                    copy_index[rc] = entry
        except Exception:
            pass

    ref_index = _build_ref_index()

    posts = []
    for post in calendar.get("posts", []):
        post_type  = post.get("type", "single")
        date_str   = post.get("date", "")
        time_str   = post.get("time", "")
        caption    = post.get("caption", "")
        hashtags   = post.get("hashtags", [])
        status     = _post_status(date_str, time_str)

        # Format scheduled datetime
        scheduled_display = ""
        if date_str:
            try:
                dt = datetime.fromisoformat(f"{date_str}T{time_str or '00:00'}")
                scheduled_display = dt.strftime("%b %d, %Y · %H:%M")
            except Exception:
                scheduled_display = date_str

        if post_type == "carousel":
            slides = post.get("slides", [])
            images_out = []
            for slide in slides:
                rc  = slide.get("ref_code", "")
                fn  = slide.get("filename", "")
                path = _resolve_image(fn, rc, ref_index)
                copy = copy_index.get(rc, {})
                images_out.append({
                    "ref_code": rc,
                    "filename": fn,
                    "path":     path,
                    "pillar":   copy.get("pillar", ""),
                    "mood":     copy.get("mood", ""),
                    "details":  copy.get("details", ""),
                    "copy_angle": copy.get("copy_angle", ""),
                })
            # Use first slide's copy for the post-level pillar/mood if no caption
            lead_copy = copy_index.get(slides[0]["ref_code"], {}) if slides else {}
            posts.append({
                "id":                f"post-{post.get('slot', len(posts))}",
                "slot":              post.get("slot"),
                "type":              "carousel",
                "date":              date_str,
                "time":              time_str,
                "scheduled_display": scheduled_display,
                "status":            status,
                "pillar":            lead_copy.get("pillar", ""),
                "caption":           caption,
                "hashtags":          hashtags,
                "images":            images_out,
                "cover_path":        images_out[0]["path"] if images_out else None,
            })
        else:
            rc    = post.get("ref_code", "")
            fn    = post.get("filename", "")
            path  = _resolve_image(fn, rc, ref_index)
            copy  = copy_index.get(rc, {})
            posts.append({
                "id":                f"post-{post.get('slot', len(posts))}",
                "slot":              post.get("slot"),
                "type":              "single",
                "date":              date_str,
                "time":              time_str,
                "scheduled_display": scheduled_display,
                "status":            status,
                "pillar":            copy.get("pillar", post.get("pillar", "")),
                "mood":              copy.get("mood", ""),
                "details":           copy.get("details", ""),
                "copy_angle":        copy.get("copy_angle", ""),
                "caption":           caption,
                "hashtags":          hashtags,
                "images":            [{
                    "ref_code": rc,
                    "filename": fn,
                    "path":     path,
                    "pillar":   copy.get("pillar", ""),
                    "mood":     copy.get("mood", ""),
                    "details":  copy.get("details", ""),
                    "copy_angle": copy.get("copy_angle", ""),
                }],
                "cover_path":        path,
            })

    return jsonify({
        "sprint":    calendar.get("sprint", ""),
        "month_of":  calendar.get("month_of", calendar.get("week_of", "")),
        "total":     len(posts),
        "posts":     posts,
    })


@app.route("/api/content/posts/<int:slot>", methods=["PATCH"])
def update_content_post(slot):
    """Update caption and/or hashtags for a post by slot in monthly_calendar.json."""
    calendar_path = CONTENT_DIR / "monthly_calendar.json"
    if not calendar_path.exists():
        calendar_path = CONTENT_DIR / "weekly_calendar.json"
    if not calendar_path.exists():
        return jsonify({"error": "No calendar file found"}), 404

    body = request.get_json(force=True) or {}

    try:
        calendar = json.loads(calendar_path.read_text())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    post = next((p for p in calendar.get("posts", []) if p.get("slot") == slot), None)
    if post is None:
        return jsonify({"error": f"Post with slot {slot} not found"}), 404

    if "caption" in body:
        post["caption"] = body["caption"]
    if "hashtags" in body:
        ht = body["hashtags"]
        if isinstance(ht, str):
            ht = [t.strip() for t in ht.replace(",", " ").split() if t.strip()]
        post["hashtags"] = ht

    try:
        calendar_path.write_text(json.dumps(calendar, indent=2, ensure_ascii=False))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": True, "slot": slot})


@app.route("/api/content/posts", methods=["DELETE"])
def delete_content_posts():
    """Delete one or more posts by slot from monthly_calendar.json."""
    slots = set((request.get_json(force=True) or {}).get("slots", []))
    if not slots:
        return jsonify({"error": "No slots provided"}), 400

    calendar_path = CONTENT_DIR / "monthly_calendar.json"
    if not calendar_path.exists():
        calendar_path = CONTENT_DIR / "weekly_calendar.json"
    if not calendar_path.exists():
        return jsonify({"error": "No calendar file found"}), 404

    try:
        calendar = json.loads(calendar_path.read_text())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    before = len(calendar.get("posts", []))
    calendar["posts"] = [p for p in calendar.get("posts", []) if p.get("slot") not in slots]
    removed = before - len(calendar["posts"])

    try:
        calendar_path.write_text(json.dumps(calendar, indent=2, ensure_ascii=False))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"ok": True, "removed": removed})


# ── Brand / Org ──────────────────────────────────────────────────────────────

def _parse_copy_strategy(text: str) -> dict:
    """Parse copy_strategy.md into structured data."""
    raw = re.split(r'\n##\s+', '\n' + text)
    sections: dict[str, str] = {}
    for s in raw[1:]:
        nl = s.index('\n') if '\n' in s else len(s)
        sections[s[:nl].strip()] = s[nl + 1:].strip()

    def bullets(key: str) -> list[str]:
        return [
            l.lstrip('- ').strip()
            for l in sections.get(key, '').split('\n')
            if l.strip().startswith('- ')
        ]

    def clean(key: str) -> str:
        return ' '.join(sections.get(key, '').split())

    # Content pillars
    pillars_text = sections.get('Content Pillars', '')
    pillar_re    = re.compile(
        r'([A-Z][A-Z/ ]+)\((\d+)%\)\n(.*?)(?=\n[A-Z][A-Z/ ]+\(\d+%\)|\Z)',
        re.DOTALL,
    )
    pillars = []
    for m in pillar_re.finditer(pillars_text):
        name = m.group(1).strip().title()
        pct  = int(m.group(2))
        body = m.group(3).strip()
        goal = tone = ''
        desc_lines: list[str] = []
        for line in body.split('\n'):
            line = line.strip()
            if line.startswith('Goal:'):
                goal = line[5:].strip()
            elif line.startswith('Tone:'):
                tone = line[5:].strip()
            elif line and not line.startswith('Example:'):
                desc_lines.append(line)
        pillars.append({
            'name': name, 'pct': pct,
            'description': ' '.join(desc_lines),
            'goal': goal, 'tone': tone,
        })

    # Posting slots
    slots = []
    for line in sections.get('Posting Slots', '').split('\n'):
        line = line.strip().lstrip('- ')
        m = re.match(r'(\w+)\s+posts?:\s*(\d+:\d+)\s*\(([^)]+)\)', line)
        if m:
            slots.append({
                'label': m.group(1),
                'time':  m.group(2),
                'days':  [d.strip() for d in m.group(3).split(',')],
            })

    # Seasonal guide
    seasonal_blocks = re.split(r'\n(?=[A-Z]+(?:-[A-Z]+)?:)', sections.get('Seasonal Context Guide', ''))
    seasonal = []
    for block in seasonal_blocks:
        block = block.strip()
        m = re.match(r'^([A-Z]+(?:-[A-Z]+)?):\s*(.*)', block, re.DOTALL)
        if not m:
            continue
        months = m.group(1)
        desc   = ' '.join(m.group(2).split())
        tone_m = re.search(r'Tone:\s*([^.]+?)\.?\s*$', desc)
        tone   = tone_m.group(1).strip() if tone_m else ''
        context = re.sub(r'\s*Tone:[^.]*\.?', '', desc).strip()
        seasonal.append({'months': months, 'context': context, 'tone': tone})

    return {
        'who_we_are':     clean('Who We Are'),
        'who_we_talk_to': clean('Who We Talk To'),
        'brand_voice':    clean('Brand Voice'),
        'core_beliefs':   bullets('Core Beliefs (inform every caption)'),
        'caption_rules':  bullets('Caption Rules'),
        'caption_never':  bullets('What Captions NEVER Do'),
        'pillars':        pillars,
        'posting_slots':  slots,
        'seasonal':       seasonal,
    }


def _orthodox_easter(year: int):
    """Return Orthodox (Gregorian) Easter date for the given year."""
    from datetime import date, timedelta
    a = year % 4
    b = year % 7
    c = year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day   = ((d + e + 114) % 31) + 1
    return date(year, month, day) + timedelta(days=13)   # Julian → Gregorian


@app.route("/api/brand")
def brand():
    from datetime import date as _date, timedelta

    result: dict = {'files': [], 'voice': {}, 'calendar': {}, 'upcoming_events': []}

    strategy_path = BRAND_DIR / "copy_strategy.md"
    calendar_path = BRAND_DIR / "greek_calendar.json"

    for path in [strategy_path, calendar_path]:
        if path.exists():
            stat = path.stat()
            result['files'].append({
                'name':          path.name,
                'last_modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

    if strategy_path.exists():
        result['voice'] = _parse_copy_strategy(strategy_path.read_text())

    cal_data: dict = {}
    if calendar_path.exists():
        cal_data = json.loads(calendar_path.read_text())
    result['calendar'] = cal_data

    # Upcoming events — next 30 days
    today    = _date.today()
    upcoming: list[dict] = []

    for h in cal_data.get('holidays', []):
        mm, dd = h['date'].split('-')
        hdate  = _date(today.year, int(mm), int(dd))
        if hdate < today:
            hdate = _date(today.year + 1, int(mm), int(dd))
        days_until = (hdate - today).days
        if 0 <= days_until <= 30:
            upcoming.append({
                'name':       h['name'],
                'date':       hdate.isoformat(),
                'days_until': days_until,
                'type':       h.get('type', 'national'),
                'posting':    h.get('posting', 'normal'),
            })

    try:
        for year in [today.year, today.year + 1]:
            easter = _orthodox_easter(year)
            for feast in cal_data.get('moveable_feasts', []):
                fdate      = easter + timedelta(days=feast.get('offset_from_easter', 0))
                days_until = (fdate - today).days
                if 0 <= days_until <= 30:
                    upcoming.append({
                        'name':       feast['name'],
                        'date':       fdate.isoformat(),
                        'days_until': days_until,
                        'type':       feast.get('type', 'religious'),
                        'posting':    feast.get('posting', 'normal'),
                    })
    except Exception:
        pass

    upcoming.sort(key=lambda x: x['days_until'])
    result['upcoming_events'] = upcoming

    return jsonify(result)


REFS_DIR     = ROOT / "references"
_IMAGE_EXTS  = {'.jpg', '.jpeg', '.png', '.webp', '.gif'}


# ── Run management ────────────────────────────────────────────────────────────

@app.route("/api/run/status")
def run_status():
    return jsonify(process_manager.status())


@app.route("/api/run/start", methods=["POST"])
def run_start():
    body   = request.get_json(silent=True) or {}
    config = body.get("config") or None
    ok, info = process_manager.start(config)
    if not ok:
        return jsonify({"error": info}), 409
    return jsonify({"pid": info})


@app.route("/api/run/stop", methods=["POST"])
def run_stop():
    ok, msg = process_manager.stop()
    _mark_progress_stopped(PROGRESS_PATH)
    if not ok:
        return jsonify({"error": msg}), 409
    return jsonify({"ok": True})


@app.route("/api/run/pause", methods=["POST"])
def run_pause():
    ok, msg = process_manager.pause()
    _mark_progress_paused(PROGRESS_PATH)
    if not ok:
        return jsonify({"error": msg}), 409
    return jsonify({"ok": True})


@app.route("/api/run/resume", methods=["POST"])
def run_resume():
    ok, msg = process_manager.resume()
    _mark_progress_resumed(PROGRESS_PATH)
    if not ok:
        return jsonify({"error": msg}), 409
    return jsonify({"ok": True})


@app.route("/api/run/logs/stream")
def run_logs_stream():
    def generate():
        # Replay buffered lines first
        for line in process_manager.get_buffer():
            yield f"data: {json.dumps({'line': line})}\n\n"

        # If not running/paused, close after buffer
        if process_manager.state not in ('running', 'paused'):
            yield f"data: {json.dumps({'done': True})}\n\n"
            return

        q = queue.Queue()
        process_manager.subscribe(q)
        try:
            while True:
                try:
                    item = q.get(timeout=25)
                    if item is None:  # end-of-stream sentinel
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        return
                    yield f"data: {json.dumps({'line': item})}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            process_manager.unsubscribe(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ── Asset management ──────────────────────────────────────────────────────────

def _asset_url(path: Path) -> str:
    return f"/api/image?path={path}"


def _list_folder(folder: Path) -> list[dict]:
    if not folder.exists():
        return []
    return sorted(
        [
            {"filename": f.name, "path": str(f), "url": _asset_url(f)}
            for f in folder.iterdir()
            if f.is_file() and f.suffix.lower() in _IMAGE_EXTS
        ],
        key=lambda x: x["filename"],
    )


@app.route("/api/run/assets")
def run_assets():
    references = {}
    for s in [1, 2, 3]:
        references[str(s)] = _list_folder(REFS_DIR / f"Set{s}")
    # Also include root references/ (Set 0)
    root_refs = _list_folder(REFS_DIR)
    if root_refs:
        references["0"] = root_refs
    return jsonify({
        "references": references,
        "products":   _list_folder(PRODUCTS_DIR),
    })


@app.route("/api/run/upload", methods=["POST"])
def run_upload():
    target = request.form.get("target", "")  # "references_1", "references_2", "references_3", "products"
    files  = request.files.getlist("files")
    if not target or not files:
        return jsonify({"error": "target and files required"}), 400

    if target.startswith("references_"):
        set_num = target.split("_", 1)[1]
        dest = REFS_DIR / f"Set{set_num}"
    elif target == "products":
        dest = PRODUCTS_DIR
    else:
        return jsonify({"error": "unknown target"}), 400

    dest.mkdir(parents=True, exist_ok=True)
    saved = []
    for f in files:
        if not f.filename:
            continue
        name = Path(f.filename).name
        if Path(name).suffix.lower() not in _IMAGE_EXTS:
            continue
        out = dest / name
        f.save(out)
        saved.append({"filename": name, "path": str(out), "url": _asset_url(out)})

    return jsonify({"saved": saved})


@app.route("/api/run/delete-asset", methods=["POST"])
def run_delete_asset():
    body     = request.get_json(silent=True) or {}
    target   = body.get("target", "")
    filename = body.get("filename", "")
    if not target or not filename:
        return jsonify({"error": "target and filename required"}), 400

    if target.startswith("references_"):
        set_num = target.split("_", 1)[1]
        path = REFS_DIR / f"Set{set_num}" / filename
    elif target == "references_root":
        path = REFS_DIR / filename
    elif target == "products":
        path = PRODUCTS_DIR / filename
    else:
        return jsonify({"error": "unknown target"}), 400

    if not path.exists() or not path.is_file():
        return jsonify({"error": "file not found"}), 404

    # Safety check: must be within expected directory
    try:
        path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        abort(403)

    path.unlink()
    return jsonify({"ok": True})


@app.route("/api/run/validate-name")
def run_validate_name():
    name    = request.args.get("name", "").strip()
    season  = request.args.get("season", "").strip()
    if not name:
        return jsonify({"error": "name required"}), 400
    # Build the same month folder that main.py would use
    today   = datetime.today()
    year    = season.split()[-1] if season else str(today.year)
    import calendar as _cal
    month_name   = _cal.month_name[today.month]
    month_folder = ASSET_DIR / f"{month_name}{year}"
    exists = (month_folder / name).exists()
    # Suggest next shoot number by scanning ALL month folders globally
    nums = []
    if ASSET_DIR.exists():
        for mdir in ASSET_DIR.iterdir():
            if mdir.is_dir():
                for sdir in mdir.iterdir():
                    if sdir.is_dir() and sdir.name.startswith("Shoot") and sdir.name[5:].isdigit():
                        nums.append(int(sdir.name[5:]))
    next_num = max(nums) + 1 if nums else 1
    suggestion = f"Shoot{next_num:02d}"
    return jsonify({"exists": exists, "suggestion": suggestion})


# ── Phase 2 — Content Pipeline ────────────────────────────────────────────────

@app.route("/api/p2/shoots")
def p2_shoots():
    """List all available shoot folders, newest first (by mtime)."""
    if not ASSET_DIR.exists():
        return jsonify([])
    shoots = []
    for month_dir in ASSET_DIR.iterdir():
        if not month_dir.is_dir():
            continue
        for shoot_dir in month_dir.iterdir():
            if shoot_dir.is_dir() and shoot_dir.name.startswith("Shoot"):
                path_str = f"{month_dir.name}/{shoot_dir.name}"
                try:
                    mtime = shoot_dir.stat().st_mtime
                except OSError:
                    mtime = 0
                shoots.append({
                    "path":  path_str,
                    "name":  shoot_dir.name,
                    "month": month_dir.name,
                    "mtime": mtime,
                })
    shoots.sort(key=lambda s: s["mtime"], reverse=True)
    for i, s in enumerate(shoots):
        s["latest"] = (i == 0)
        del s["mtime"]
    return jsonify(shoots)


@app.route("/api/p2/status")
def p2_status():
    return jsonify(process_manager_p2.status())


@app.route("/api/p2/start", methods=["POST"])
def p2_start():
    body           = request.get_json(silent=True) or {}
    shoot_folder   = body.get("shoot_folder", "").strip()
    planning_month = body.get("planning_month", "").strip()   # "YYYY-MM"
    env_extra = {}
    if shoot_folder:
        env_extra["SHOOT_FOLDER"] = shoot_folder
    if planning_month:
        env_extra["PLANNING_MONTH"] = planning_month
    ok, info = process_manager_p2.start(script="main_phase2.py", env_extra=env_extra)
    if not ok:
        return jsonify({"error": info}), 409
    return jsonify({"pid": info})


@app.route("/api/p2/stop", methods=["POST"])
def p2_stop():
    ok, msg = process_manager_p2.stop()
    _mark_progress_stopped(PROGRESS_P2_PATH)
    if not ok:
        return jsonify({"error": msg}), 409
    return jsonify({"ok": True})


@app.route("/api/p2/pause", methods=["POST"])
def p2_pause():
    ok, msg = process_manager_p2.pause()
    _mark_progress_paused(PROGRESS_P2_PATH)
    if not ok:
        return jsonify({"error": msg}), 409
    return jsonify({"ok": True})


@app.route("/api/p2/resume", methods=["POST"])
def p2_resume():
    ok, msg = process_manager_p2.resume()
    _mark_progress_resumed(PROGRESS_P2_PATH)
    if not ok:
        return jsonify({"error": msg}), 409
    return jsonify({"ok": True})


@app.route("/api/p2/logs/stream")
def p2_logs_stream():
    def generate():
        for line in process_manager_p2.get_buffer():
            yield f"data: {json.dumps({'line': line})}\n\n"
        if process_manager_p2.state not in ('running', 'paused'):
            yield f"data: {json.dumps({'done': True})}\n\n"
            return
        q = queue.Queue()
        process_manager_p2.subscribe(q)
        try:
            while True:
                try:
                    item = q.get(timeout=25)
                    if item is None:
                        yield f"data: {json.dumps({'done': True})}\n\n"
                        return
                    yield f"data: {json.dumps({'line': item})}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            process_manager_p2.unsubscribe(q)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(port=5001, debug=True, use_reloader=False, threaded=True)
