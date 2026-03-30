"""
Lunchbag Webapp — Flask API
Serves data from the pipeline's output files.
"""

import json
import re
from pathlib import Path
from datetime import datetime
from flask import Flask, jsonify, send_file, request, abort
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ROOT         = Path(__file__).parent.parent
ASSET_DIR    = ROOT / "asset_library" / "images"
REPORTS_DIR  = ROOT / "outputs" / "sprint_reports"
OUTPUTS_DIR  = ROOT / "outputs"

AGENTS = [
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
        r = {}

        r["runtime"]     = _parse_table_value(text, "Total runtime")
        r["approved"]    = _parse_table_value(text, "Images approved")
        r["generated"]   = _parse_table_value(text, "Images generated")
        r["pass_rate"]   = _parse_table_value(text, "First-pass approval rate")
        r["needs_review"] = _parse_table_value(text, "Needs manual review")
        r["errors"]      = _parse_table_value(text, "Errors") or "0"

        # Cost + total calls from summary table
        m = re.search(
            r'\*\*Total\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*\$?([\d.]+)\*\*',
            text
        )
        if m:
            r["total_calls"] = int(m.group(1))
            r["total_cost"]  = float(m.group(2))
        else:
            r["total_calls"] = 0
            r["total_cost"]  = 0.0

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
        candidates = sorted(
            [f for f in REPORTS_DIR.iterdir() if sprint_id in f.name],
            reverse=True
        )
        if candidates:
            report = _parse_sprint_report(candidates[0])

    # ── Status ───────────────────────────────────────────────
    status = "complete" if total_images > 0 else "empty"

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
        "runtime":      report.get("runtime", "—"),
        "pass_rate":    report.get("pass_rate", "—"),
        "total_calls":  report.get("total_calls", 0),
        "total_cost":   report.get("total_cost", 0.0),
        "errors":       report.get("errors", "0"),
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


# ── Endpoints ──────────────────────────────────────────────────────────────

@app.route("/api/dashboard")
def dashboard():
    shoots = _all_shoots()
    total_images   = sum(s["approved"] for s in shoots)
    total_calls    = sum(s["total_calls"] for s in shoots)
    total_cost     = sum(s["total_cost"] for s in shoots)
    total_shoots   = len([s for s in shoots if s["status"] != "empty"])
    return jsonify({
        "agents":       len(AGENTS),
        "shoots":       total_shoots,
        "total_images": total_images,
        "total_calls":  total_calls,
        "total_cost":   round(total_cost, 2),
        "recent_shoots": shoots[:5],
    })


@app.route("/api/shoots")
def shoots_list():
    return jsonify(_all_shoots())


@app.route("/api/shoots/<path:shoot_id>")
def shoot_detail(shoot_id):
    # shoot_id format: March2026__Shoot11
    parts = shoot_id.split("__")
    if len(parts) != 2:
        abort(404)
    month_name, shoot_name = parts
    shoot_dir = ASSET_DIR / month_name / shoot_name

    if not shoot_dir.exists():
        abort(404)

    month_dir = ASSET_DIR / month_name
    summary = _load_shoot(month_dir, shoot_dir)

    # Full image list with set breakdown
    catalog_path = shoot_dir / "catalog.json"
    images = []
    if catalog_path.exists():
        try:
            catalog = json.loads(catalog_path.read_text())
            raw = catalog.get("images", [])
            for img in raw:
                filename = img.get("filename", "")
                ref_code = img.get("ref_code", "")
                set_num  = _set_num(ref_code)
                # Determine display status
                if filename.startswith("Regen-"):
                    display_status = "regen"
                elif "Needs Review" in filename:
                    display_status = "needs_review"
                elif img.get("status") == "approved":
                    display_status = "approved"
                else:
                    display_status = "pending"
                images.append({
                    **img,
                    "set":            set_num,
                    "display_status": display_status,
                })
        except Exception:
            pass

    # Group by set
    sets = {}
    for img in images:
        s = img["set"]
        sets.setdefault(s, []).append(img)

    return jsonify({**summary, "images": images, "sets": sets})


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
    return jsonify(AGENTS)


if __name__ == "__main__":
    app.run(port=5001, debug=True)
