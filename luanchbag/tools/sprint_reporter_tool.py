import os
import re
import json
from pathlib import Path
from datetime import datetime
from crewai.tools import BaseTool

OUTPUTS_DIR  = Path("outputs")
ASSET_DIR    = Path("asset_library/images")
CATALOG_PATH = Path("asset_library/catalog.json")
REPORTS_DIR  = Path("outputs/sprint_reports")
SUPPORTED    = {".jpg", ".jpeg", ".png"}

# Approximate cost per API call (USD)
COST_PER_CALL = {
    "gemini-2.5-pro":           0.0035,
    "gemini-3-pro-image-preview": 0.040,
}


def _parse_photo_editor_report() -> dict:
    path = OUTPUTS_DIR / "photo_editor_latest.md"
    if not path.exists():
        return {}
    content = path.read_text()

    result = {
        "total":        0,
        "passed":       0,
        "fixed":        0,
        "flagged":      0,
        "batch_flagged": 0,
        "criteria_failures": {
            "product_accuracy":   0,
            "material_correctness": 0,
            "earring_size":       0,
            "earring_orientation": 0,
            "model_consistency":  0,
            "lighting_realism":   0,
            "composition_intent": 0,
            "anti_ai_check":      0,
        },
        "fix_attempts": {
            "1": 0,
            "2": 0,
            "3": 0,
        },
        "errors": [],
    }

    for line in content.splitlines():
        line = line.strip()

        if re.match(r"[✓✗]\s+PASS\s+\|", line):
            result["passed"] += 1
            result["total"]  += 1
        elif re.match(r"[✓✗]\s+FIXED\s+\|", line):
            result["fixed"] += 1
            result["total"] += 1
            attempts_match = re.search(r"attempts:\s*(\d)", line)
            if attempts_match:
                n = attempts_match.group(1)
                if n in result["fix_attempts"]:
                    result["fix_attempts"][n] += 1
        elif re.match(r"[✗]\s+FLAGGED", line):
            result["flagged"] += 1
            result["total"]   += 1
        elif "FAILED BATCH CHECK" in line.upper():
            result["batch_flagged"] += 1

        # Count criteria failures
        criteria_map = {
            "1. PRODUCT ACCURACY: FAIL":    "product_accuracy",
            "2. MATERIAL CORRECTNESS: FAIL": "material_correctness",
            "3. EARRING SIZE: FAIL":         "earring_size",
            "4. EARRING ORIENTATION: FAIL":  "earring_orientation",
            "5. MODEL CONSISTENCY: FAIL":    "model_consistency",
            "6. LIGHTING REALISM: FAIL":     "lighting_realism",
            "7. COMPOSITION INTENT: FAIL":   "composition_intent",
            "8. ANTI-AI CHECK: FAIL":        "anti_ai_check",
        }
        for key, field in criteria_map.items():
            if key in line.upper():
                result["criteria_failures"][field] += 1

        if "TOOL_ERROR" in line:
            result["errors"].append(line)

    return result


def _parse_art_director_report() -> dict:
    path = OUTPUTS_DIR / "art_director_latest.md"
    if not path.exists():
        return {}
    content = path.read_text()

    result = {
        "total":   0,
        "passed":  0,
        "flagged": 0,
        "drift_types": {
            "composition_drift": 0,
            "lighting_drift":    0,
            "mood_drift":        0,
        },
        "batch_observations": [],
        "errors": [],
    }

    for line in content.splitlines():
        line = line.strip()

        if re.search(r"[✓]\s+PASS\s+\|", line):
            result["passed"] += 1
            result["total"]  += 1
        elif re.search(r"[✗]\s+FLAGGED\s+\|", line):
            result["flagged"] += 1
            result["total"]  += 1

        if re.search(r"COMPOSITION DRIFT.*FLAG", line, re.IGNORECASE):
            result["drift_types"]["composition_drift"] += 1

        if re.search(r"LIGHTING DRIFT.*FLAG", line, re.IGNORECASE):
            result["drift_types"]["lighting_drift"] += 1

        if re.search(r"MOOD DRIFT.*FLAG", line, re.IGNORECASE):
            result["drift_types"]["mood_drift"] += 1

        if re.search(r"^-?\s*Batch\s+\d+:", line, re.IGNORECASE):
            result["batch_observations"].append(
                line.strip().lstrip("- ")
            )

        if "TOOL_ERROR" in line:
            result["errors"].append(line)

    return result


def _parse_catalog() -> dict:
    if not CATALOG_PATH.exists():
        return {}
    try:
        data = json.loads(CATALOG_PATH.read_text())
        return data.get("meta", {})
    except Exception:
        return {}


def _count_asset_library() -> dict:
    if not ASSET_DIR.exists():
        return {
            "total": 0, "approved": 0,
            "needs_review": 0, "art_review": 0,
        }
    files = [
        f for f in ASSET_DIR.iterdir()
        if f.is_file()
        and f.suffix.lower() in SUPPORTED
        and "TEST-" not in f.name
    ]

    # Live counts from file system
    live_needs_review = sum(
        1 for f in files
        if "Needs Review-" in f.name
    )
    live_art_review = sum(
        1 for f in files
        if "Art Review-" in f.name
    )

    # If no prefixed files found in live system
    # fall back to report-based counts
    # (files may have been fixed and renamed back)
    report_art_review = 0
    ad_path = OUTPUTS_DIR / "art_director_latest.md"
    if ad_path.exists() and live_art_review == 0:
        content = ad_path.read_text()
        match = re.search(
            r"Flagged for rework:\s*(\d+)",
            content,
            re.IGNORECASE,
        )
        if match:
            report_art_review = int(match.group(1))

    report_needs_review = 0
    pe_path = OUTPUTS_DIR / "photo_editor_latest.md"
    if pe_path.exists() and live_needs_review == 0:
        content = pe_path.read_text()
        match = re.search(
            r"Flagged for manual review:\s*(\d+)",
            content,
            re.IGNORECASE,
        )
        if match:
            report_needs_review = int(match.group(1))

    final_needs_review = (
        live_needs_review or report_needs_review
    )
    final_art_review = (
        live_art_review or report_art_review
    )

    approved = sum(
        1 for f in files
        if "Needs Review-" not in f.name
        and "Art Review-"   not in f.name
    )

    return {
        "total":        len(files),
        "approved":     approved,
        "needs_review": final_needs_review,
        "art_review":   final_art_review,
    }


def _estimate_costs(
    pe_data: dict,
    ad_data: dict,
    images_generated: int,
) -> dict:
    fixes_attempted = (
        pe_data.get("fixed", 0) * 2
        + pe_data.get("flagged", 0) * 3
    )

    nano_banana_calls = images_generated + fixes_attempted
    gemini_review_calls = (
        pe_data.get("total", 0) * 2
        + ad_data.get("total", 0)
    )

    nano_cost   = nano_banana_calls * COST_PER_CALL["gemini-3-pro-image-preview"]
    gemini_cost = gemini_review_calls * COST_PER_CALL["gemini-2.5-pro"]
    total_cost  = nano_cost + gemini_cost

    return {
        "nano_banana_calls":   nano_banana_calls,
        "gemini_review_calls": gemini_review_calls,
        "nano_cost_usd":       round(nano_cost, 3),
        "gemini_cost_usd":     round(gemini_cost, 3),
        "total_cost_usd":      round(total_cost, 3),
    }


class SprintReporterTool(BaseTool):
    name: str        = "Orpina Sprint Reporter"
    description: str = """
        Generates a comprehensive Markdown Sprint Report
        at the end of every sprint. Synthesises all sprint 
        outputs into a single report covering performance,
        quality, costs, and recommendations.
    """

    def _run(self, input_str: str = "") -> str:
        try:
            timing = {}
            try:
                timing = json.loads(input_str)
            except Exception:
                timing = {
                    "started_at":     datetime.now().isoformat(),
                    "steps":          {},
                    "images_planned": 0,
                    "errors":         [],
                }

            sprint_id      = timing.get("sprint_id", "UNKNOWN")
            started_at_str = timing.get("started_at", datetime.now().isoformat())
            steps = {
                k: max(0, int(v))
                for k, v in timing.get(
                    "steps", {}
                ).items()
            }
            images_planned = timing.get("images_planned", 0)
            input_errors   = timing.get("errors", [])

            try:
                started_at = datetime.fromisoformat(started_at_str)
            except Exception:
                started_at = datetime.now()

            now           = datetime.now()
            total_seconds = int((now - started_at).total_seconds())
            total_runtime = (
                f"{total_seconds // 3600}h "
                f"{(total_seconds % 3600) // 60}m "
                f"{total_seconds % 60}s"
            )

            pe_data    = _parse_photo_editor_report()
            ad_data    = _parse_art_director_report()
            assets     = _count_asset_library()
            images_gen = assets["total"]
            costs      = _estimate_costs(pe_data, ad_data, images_gen)

            all_errors = input_errors + pe_data.get("errors", []) + ad_data.get("errors", [])

            pe_total   = pe_data.get("total", 0)
            pe_passed  = pe_data.get("passed", 0)
            pe_fixed   = pe_data.get("fixed", 0)
            pe_flagged = pe_data.get("flagged", 0)
            
            first_pass_rate = round((pe_passed / pe_total) * 100) if pe_total else 0
            final_pass_rate = round(((pe_passed + pe_fixed) / pe_total) * 100) if pe_total else 0

            ad_total   = ad_data.get("total", 0)
            ad_flagged = ad_data.get("flagged", 0)
            ad_pass_rate = round(((ad_total - ad_flagged) / ad_total) * 100) if ad_total else 0

            criteria = pe_data.get("criteria_failures", {})
            sorted_criteria = sorted(criteria.items(), key=lambda x: x[1], reverse=True)
            top_criteria = [(k, v) for k, v in sorted_criteria if v > 0]

            drift = ad_data.get("drift_types", {})
            sorted_drift = sorted(drift.items(), key=lambda x: x[1], reverse=True)
            top_drift = [(k, v) for k, v in sorted_drift if v > 0]

            recommendations = []
            if first_pass_rate < 60:
                recommendations.append("First-pass approval rate is below 60% — strengthen the generation prompt.")
            if top_criteria:
                worst = top_criteria[0][0].replace("_", " ")
                recommendations.append(f"Most common failure: {worst}. Add more explicit instructions.")
            if drift.get("composition_drift", 0) > 3:
                recommendations.append("High composition drift detected.")
            if costs["total_cost_usd"] > 5.0:
                recommendations.append(f"Sprint cost was ${costs['total_cost_usd']} — consider optimizations.")
            if not recommendations:
                recommendations.append("Sprint performance looks healthy.")

            def fmt_seconds(s: int) -> str:
                if s < 60: return f"{s}s"
                return f"{s // 60}m {s % 60}s"

            step_labels = {
                "build_creative_brief": "Creative Brief",
                "create_style_bible": "Style Bible + Shot List",
                "build_image_generation_package": "Image Generation",
                "run_photo_editor": "Photo Editor Review",
                "write_catalog": "Catalog Writer",
                "run_art_director": "Art Director Review",
                "final_approval": "Final Approval",
            }

            report = (
                f"# SPRINT REPORT — ORPINA\n"
                f"Sprint: {sprint_id}\n"
                f"Date: {now.strftime('%Y-%m-%d')}\n\n"
                f"{'='*55}\n"
                f"## 1. SPRINT SUMMARY\n"
                f"{'='*55}\n\n"
                f"| Metric | Value |\n"
                f"|---|---|\n"
                f"| Sprint ID | {sprint_id} |\n"
                f"| Started | {started_at.strftime('%H:%M')} |\n"
                f"| Completed | {now.strftime('%H:%M')} |\n"
                f"| Total runtime | {total_runtime} |\n"
                f"| Images planned | {images_planned} |\n"
                f"| Images generated | {images_gen} |\n"
                f"| Images approved | {assets['approved']} |\n"
                f"| Needs manual review | "
                f"{assets['needs_review']} |\n"
                f"| Fixed by Art Director loop | "
                f"{assets['art_review']} |\n"
                f"| Errors | {len(all_errors)} |\n\n"
                f"{'='*55}\n"
                f"## 2. STEP TIMING\n"
                f"{'='*55}\n\n"
                f"| Step | Duration |\n"
                f"|---|---|\n"
            )

            for key, label in step_labels.items():
                secs = steps.get(key, 0)
                report += f"| {label} | {fmt_seconds(secs)} |\n"

            report += (
                f"| **Total** | **{total_runtime}** |\n\n"
                f"{'='*55}\n"
                f"## 3. GENERATION METRICS\n"
                f"{'='*55}\n\n"
                f"| Metric | Value |\n"
                f"|---|---|\n"
                f"| Planned | {images_planned} |\n"
                f"| Generated | {images_gen} |\n"
                f"| Approved (passed) | {pe_passed} |\n"
                f"| Approved (fixed) | {pe_fixed} |\n"
                f"| Needs Review | {assets['needs_review']} |\n"
                f"| Art Review | {assets['art_review']} |\n"
                f"| Drop rate | {round(((images_gen - assets['approved']) / images_gen) * 100) if images_gen else 0}% |\n\n"
                f"{'='*55}\n"
                f"## 4. IMAGE QUALITY METRICS\n"
                f"{'='*55}\n\n"
                f"### Photo Editor\n\n"
                f"| Metric | Value |\n"
                f"|---|---|\n"
                f"| Total reviewed | {pe_total} |\n"
                f"| First-pass approval | {pe_passed} ({first_pass_rate}%) |\n"
                f"| Fixed by editing | {pe_fixed} |\n"
                f"| Final approval rate | {final_pass_rate}% |\n"
                f"| Flagged for manual review | {pe_flagged} |\n"
                f"| Flagged by batch check | {pe_data.get('batch_flagged', 0)} |\n\n"
                f"### Fix Attempt Distribution\n\n"
                f"| Attempts needed | Images |\n"
                f"|---|---|\n"
                f"| Fixed on attempt 1 | {pe_data.get('fix_attempts', {}).get('1', 0)} |\n"
                f"| Fixed on attempt 2 | {pe_data.get('fix_attempts', {}).get('2', 0)} |\n"
                f"| Fixed on attempt 3 | {pe_data.get('fix_attempts', {}).get('3', 0)} |\n\n"
                f"{'='*55}\n"
                f"## 5. CRITERIA FAILURE BREAKDOWN\n"
                f"{'='*55}\n\n"
            )

            if top_criteria:
                report += "| Criterion | Failures |\n|---|---|\n"
                for criterion, count in sorted_criteria:
                    label = criterion.replace("_", " ").title()
                    report += f"| {label} | {count} {'█' * count} |\n"
            else:
                report += "No criteria failures recorded.\n"

            report += (
                f"\n{'='*55}\n"
                f"## 6. CREATIVE DRIFT BREAKDOWN\n"
                f"{'='*55}\n\n"
                f"### Art Director\n\n"
                f"| Metric | Value |\n"
                f"|---|---|\n"
                f"| Total reviewed | {ad_total} |\n"
                f"| Passed | {ad_total - ad_flagged} ({ad_pass_rate}%) |\n"
                f"| Flagged for rework | {ad_flagged} |\n\n"
            )

            if top_drift:
                report += "| Drift Type | Occurrences |\n|---|---|\n"
                for drift_type, count in sorted_drift:
                    label = drift_type.replace("_", " ").title()
                    report += f"| {label} | {count} {'█' * count} |\n"
            else:
                report += "No creative drift recorded.\n"

            report += (
                f"\n{'='*55}\n"
                f"## 7. API USAGE & ESTIMATED COST\n"
                f"{'='*55}\n\n"
                f"| Model | Calls | Est. Cost |\n"
                f"|---|---|---|\n"
                f"| Nano Banana (generation + fixes) | {costs['nano_banana_calls']} | ${costs['nano_cost_usd']} |\n"
                f"| Gemini 2.5 Pro (reviews) | {costs['gemini_review_calls']} | ${costs['gemini_cost_usd']} |\n"
                f"| **Total** | **{costs['nano_banana_calls'] + costs['gemini_review_calls']}** | **${costs['total_cost_usd']}** |\n\n"
                f"{'='*55}\n"
                f"## 8. ERRORS & WARNINGS\n"
                f"{'='*55}\n\n"
            )

            if all_errors:
                for err in all_errors: report += f"- {err}\n"
            else:
                report += "No errors recorded.\n"

            report += (
                f"\n{'='*55}\n"
                f"## 9. RECOMMENDATIONS FOR NEXT SPRINT\n"
                f"{'='*55}\n\n"
            )
            for rec in recommendations: report += f"- {rec}\n"

            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp   = now.strftime("%Y%m%d_%H%M")
            report_path = REPORTS_DIR / f"sprint_{sprint_id}_{timestamp}.md"
            report_path.write_text(report)
            (OUTPUTS_DIR / "sprint_report_latest.md").write_text(report)

            return f"Sprint Report saved to {report_path}"

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
