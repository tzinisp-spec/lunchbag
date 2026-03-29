import os
import re
import json
from pathlib import Path
from datetime import datetime
from crewai.tools import BaseTool

def _get_asset_dir() -> Path:
    shoot_folder = os.getenv("SHOOT_FOLDER", "")
    base_dir     = Path("asset_library/images")
    if shoot_folder:
        path = base_dir / shoot_folder
        path.mkdir(parents=True, exist_ok=True)
        return path
    # Fallback to most recent shoot folder
    folders = []
    for month_dir in base_dir.iterdir():
        if not month_dir.is_dir():
            continue
        for shoot_dir in month_dir.iterdir():
            if (shoot_dir.is_dir()
                    and shoot_dir.name.startswith(
                        "Shoot"
                    )):
                folders.append(shoot_dir)
    if folders:
        return sorted(folders)[-1]
    return base_dir

OUTPUTS_DIR = Path("outputs")
REPORTS_DIR = Path("outputs/sprint_reports")


def _get_catalog_path() -> Path:
    shoot_folder = os.getenv("SHOOT_FOLDER", "")
    if shoot_folder:
        return (
            Path("asset_library/images")
            / shoot_folder
            / "catalog.json"
        )
    return Path("asset_library/catalog.json")
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
            "pattern_accuracy":    0,
            "fabric_quality":      0,
            "bag_size_scale":      0,
            "hardware_fidelity":   0,
            "model_consistency":   0,
            "lighting_realism":    0,
            "composition_intent":  0,
            "anti_ai_check":       0,
            "composition_reality": 0,
        },
        "fix_attempts": {"1": 0, "2": 0, "3": 0},
        "image_details": [],
        "errors": [],
    }

    # Try structured format first
    structured = False
    for line in content.splitlines():
        line = line.strip()
        img_match = re.search(r"([✓✗])\s+(PASS|FIXED|FLAGGED(?:_BATCH)?)", line)
        if img_match:
            structured = True
            if "PASS" in line:
                result["passed"] += 1
                result["total"]  += 1
            elif "FIXED" in line:
                result["fixed"] += 1
                result["total"] += 1
                m = re.search(r"attempts:\s*(\d)", line)
                if m and m.group(1) in result["fix_attempts"]:
                    result["fix_attempts"][m.group(1)] += 1
            elif "FLAGGED" in line:
                result["flagged"] += 1
                result["total"]   += 1

            # Fall back to prose format parsing

    if not structured:
        # Total reviewed
        m = re.search(
            r"Total images reviewed[:\s]+(\d+)",
            content, re.IGNORECASE
        )
        if m:
            result["total"] = int(m.group(1))

        # First pass
        m = re.search(
            r"First.pass approval rate[:\s]+\d+%\s*\((\d+)",
            content, re.IGNORECASE
        )
        if m:
            result["passed"] = int(m.group(1))

        # Fixed
        m = re.search(
            r"(?:successfully\s+)?fixed[:\s]+(\d+)",
            content, re.IGNORECASE
        )
        if m:
            result["fixed"] = int(m.group(1))

        # Flagged
        m = re.search(
            r"flagged for manual review[:\s]+(\d+)",
            content, re.IGNORECASE
        )
        if m:
            result["flagged"] = int(m.group(1))

        # Batch flagged
        m = re.search(
            r"batch consistency[^.]*?(\d+)",
            content, re.IGNORECASE
        )
        if m:
            result["batch_flagged"] = int(m.group(1))

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
        "image_details": [],
        "batch_observations": [],
        "errors": [],
    }

    # Try structured format first
    structured = False
    for line in content.splitlines():
        line = line.strip()
        if re.search(r"([✓✗])\s+(PASS|FLAGGED)\s+\|", line):
            structured = True
            if "PASS" in line:
                result["passed"] += 1
                result["total"]  += 1
            elif "FLAGGED" in line:
                result["flagged"] += 1
                result["total"]   += 1


        if re.search(
            r"COMPOSITION DRIFT.*FLAG", line, re.IGNORECASE
        ):
            result["drift_types"]["composition_drift"] += 1
        if re.search(
            r"LIGHTING DRIFT.*FLAG", line, re.IGNORECASE
        ):
            result["drift_types"]["lighting_drift"] += 1
        if re.search(
            r"MOOD DRIFT.*FLAG", line, re.IGNORECASE
        ):
            result["drift_types"]["mood_drift"] += 1

    # Fall back to prose format
    if not structured:
        m = re.search(
            r"Total images reviewed[:\s]+(\d+)",
            content, re.IGNORECASE
        )
        if m:
            result["total"] = int(m.group(1))

        m = re.search(
            r"Passed[^:]*[:\s]+(\d+)",
            content, re.IGNORECASE
        )
        if m:
            result["passed"] = int(m.group(1))

        m = re.search(
            r"Flagged for rework[:\s]+(\d+)",
            content, re.IGNORECASE
        )
        if m:
            result["flagged"] = int(m.group(1))

        # Detect drift types from prose
        if re.search(
            r"too compositionally similar|"
            r"composition.*repetitive|"
            r"same angle|same framing",
            content, re.IGNORECASE
        ):
            result["drift_types"]["composition_drift"] += (
                result["flagged"]
            )

        if re.search(
            r"lighting.*inconsistent|"
            r"different.*light|color temperature",
            content, re.IGNORECASE
        ):
            result["drift_types"]["lighting_drift"] += 1

        if re.search(
            r"mood.*different|tone.*off|"
            r"feel.*wrong|energy.*inconsistent",
            content, re.IGNORECASE
        ):
            result["drift_types"]["mood_drift"] += 1

    return result


def _parse_image_level_details() -> list[dict]:
    """
    Parse per-image details from Photo Editor
    and Art Director reports.
    Returns list of dicts with full per-image
    history including issues, fixes, and
    final status.
    """
    results = []
    pe_path = OUTPUTS_DIR / "photo_editor_latest.md"
    ad_path = OUTPUTS_DIR / "art_director_latest.md"

    if not pe_path.exists():
        return results

    pe_content = pe_path.read_text()
    ad_content = (
        ad_path.read_text()
        if ad_path.exists()
        else ""
    )

    # Parse Photo Editor per-image blocks
    # Each block starts with ✓ or ✗ and filename
    current_image = None

    # Prose list detection
    in_pe_flagged_list = False

    for line in pe_content.splitlines():
        line_s = line.strip()
        
        # Detect prose heading for flagged images
        if "IMAGES FLAGGED FOR MANUAL REVIEW:" in line_s.upper():
            in_pe_flagged_list = True
            continue
        
        if in_pe_flagged_list and line_s.startswith("- `"):
            # Match - `filename.png` (Issue: ...)
            m = re.search(r"- `(.+?)`\s*(?:\((.+?)\))?", line_s)
            if m:
                filename = m.group(1)
                issue = m.group(2) or "Failed review"
                results.append({
                    "filename":       filename,
                    "pe_status":      "FLAGGED",
                    "pe_failures":    [issue],
                    "pe_fix":         "",
                    "pe_fix_attempts": 0,
                    "ad_status":      "NOT_REVIEWED",
                    "ad_issues":      [],
                    "ad_regen_note":  "",
                    "final_status":   "NEEDS_MANUAL_REVIEW",
                })
            continue

        # Detect new image entry (structured)
        img_match = re.search(
            r"([✓✗])\s+(PASS|FIXED|FLAGGED(?:_BATCH)?)"
            r"\s+\|\s+(.+?)(?:\s+\||$)",
            line_s,
        )
        if img_match:
            # Save previous block
            if current_image:
                results.append(current_image)

            status    = img_match.group(2)
            filename  = img_match.group(3).strip()

            current_image = {
                "filename":       filename,
                "pe_status":      status,
                "pe_failures":    [],
                "pe_fix":         "",
                "pe_fix_attempts": 0,
                "ad_status":      "NOT_REVIEWED",
                "ad_issues":      [],
                "ad_regen_note":  "",
                "final_status":   "",
            }
            continue

        if current_image:
            # Parse criteria failures
            for crit in [
                "1. PATTERN ACCURACY",
                "2. FABRIC QUALITY",
                "3. BAG SIZE AND SCALE",
                "4. HARDWARE AND DETAIL FIDELITY",
                "5. MODEL CONSISTENCY",
                "6. LIGHTING REALISM",
                "7. COMPOSITION INTENT",
                "8. ANTI-AI CHECK",
                "9. COMPOSITION REALITY CHECK",
            ]:
                if (
                    crit in line.upper()
                    and "FAIL" in line.upper()
                ):
                    reason = (
                        line.split("—", 1)[-1].strip()
                        if "—" in line
                        else line
                    )
                    current_image["pe_failures"].append(
                        f"{crit}: {reason}"
                    )

            # Parse fix instruction
            if "FIX APPLIED:" in line.upper():
                current_image["pe_fix"] = (
                    line.split(":", 1)[-1].strip()
                )

            # Parse fix attempts
            attempts_match = re.search(
                r"attempts:\s*(\d)", line
            )
            if attempts_match:
                current_image["pe_fix_attempts"] = int(
                    attempts_match.group(1)
                )

            # Parse batch check failure
            if "FAILED BATCH CHECK:" in line.upper():
                current_image["pe_failures"].append(
                    line.strip()
                )

    # Save last block
    if current_image:
        results.append(current_image)

    # Parse Art Director per-image blocks
    if ad_content:
        ad_current = None
        in_ad_flagged_list = False

        for line in ad_content.splitlines():
            line_s = line.strip()

            # Prose list detection for AD
            if "IMAGES FLAGGED FOR REWORK:" in line_s.upper():
                in_ad_flagged_list = True
                continue

            if in_ad_flagged_list and line_s.startswith("- `") or (re.match(r"^\d+\.\s+\*\*`", line_s)):
                # Match 1. **`filename.png`** or - `filename.png`
                m = re.search(r"`(.+?)`", line_s)
                if m:
                    filename = m.group(1)
                    # Find or create result
                    found = False
                    for r in results:
                        if r["filename"] == filename or filename in r["filename"]:
                            r["ad_status"] = "FLAGGED"
                            r["final_status"] = "ART_REVIEW_FLAGGED"
                            found = True
                            break
                    if not found:
                        results.append({
                            "filename":       filename,
                            "pe_status":      "PASS",
                            "pe_failures":    [],
                            "pe_fix":         "",
                            "pe_fix_attempts": 0,
                            "ad_status":      "FLAGGED",
                            "ad_issues":      ["Art review flagged"],
                            "ad_regen_note":  "",
                            "final_status":   "ART_REVIEW_FLAGGED",
                        })
                continue

            ad_match = re.search(
                r"([✓✗])\s+(PASS|FLAGGED)\s+\|\s+(.+?)$",
                line_s,
            )

            if ad_match:
                ad_current = ad_match.group(3).strip()
                status     = ad_match.group(2)

                # Match to existing result
                for r in results:
                    pe_clean_name = r["filename"]
                    for prefix in ["Needs Review-", "Art Review-"]:
                        if pe_clean_name.startswith(prefix):
                            pe_clean_name = pe_clean_name[len(prefix):]
                    
                    ad_clean_name = ad_current
                    for prefix in ["Art Review-"]:
                        if ad_clean_name.startswith(prefix):
                            ad_clean_name = ad_clean_name[len(prefix):]

                    if (
                        r["filename"] == ad_current
                        or pe_clean_name == ad_clean_name
                    ):
                        r["ad_status"] = status
                        break

            # Parse drift issues
            if ad_current:
                for drift in [
                    "COMPOSITION DRIFT: FLAG",
                    "LIGHTING DRIFT: FLAG",
                    "MOOD DRIFT: FLAG",
                ]:
                    if drift in line.upper():
                        reason = (
                            line.split("—", 1)[-1].strip()
                            if "—" in line
                            else line
                        )
                        for r in results:
                            pe_clean_name = r["filename"]
                            for prefix in ["Needs Review-", "Art Review-"]:
                                if pe_clean_name.startswith(prefix):
                                    pe_clean_name = pe_clean_name[len(prefix):]
                            
                            ad_clean_name = ad_current
                            for prefix in ["Art Review-"]:
                                if ad_clean_name.startswith(prefix):
                                    ad_clean_name = ad_clean_name[len(prefix):]

                            if (
                                r["filename"] == ad_current
                                or pe_clean_name == ad_clean_name
                            ):
                                r["ad_issues"].append(
                                    f"{drift}: {reason}"
                                )
                                break

                if "REGENERATION NOTE:" in line.upper():
                    note = line.split(":", 1)[-1].strip()
                    for r in results:
                        pe_clean_name = r["filename"]
                        for prefix in ["Needs Review-", "Art Review-"]:
                            if pe_clean_name.startswith(prefix):
                                pe_clean_name = pe_clean_name[len(prefix):]
                        
                        ad_clean_name = ad_current
                        for prefix in ["Art Review-"]:
                            if ad_clean_name.startswith(prefix):
                                ad_clean_name = ad_clean_name[len(prefix):]

                        if (
                            r["filename"] == ad_current
                            or pe_clean_name == ad_clean_name
                        ):
                            r["ad_regen_note"] = note
                            break

    # Determine final status for each image
    for r in results:
        if r["pe_status"] == "PASS" and (
            r["ad_status"] in ("PASS", "NOT_REVIEWED")
        ):
            r["final_status"] = "APPROVED"
        elif r["pe_status"] == "FIXED" and (
            r["ad_status"] in ("PASS", "NOT_REVIEWED")
        ):
            r["final_status"] = "APPROVED_AFTER_FIX"
        elif "FLAGGED" in r["pe_status"]:
            r["final_status"] = "NEEDS_MANUAL_REVIEW"
        elif r["ad_status"] == "FLAGGED":
            r["final_status"] = "ART_REVIEW_FLAGGED"
        else:
            r["final_status"] = "UNKNOWN"

    return results


def _parse_catalog() -> dict:
    catalog_path = _get_catalog_path()
    if not catalog_path.exists():
        return {}
    try:
        data = json.loads(catalog_path.read_text())
        return data.get("meta", {})
    except Exception:
        return {}


def _count_asset_library() -> dict:
    if not _get_asset_dir().exists():
        return {
            "total": 0, "approved": 0,
            "needs_review": 0, "art_review": 0,
        }
    files = [
        f for f in _get_asset_dir().iterdir()
        if f.is_file()
        and f.suffix.lower() in SUPPORTED
        and "TEST-" not in f.name
    ]

    approved_files = [
        f for f in files
        if "Needs Review-" not in f.name
        and "Art Review-"   not in f.name
    ]

    sprint_id = "UNKNOWN"
    if approved_files:
        # Match lunchbag-SPRING-26-03-20
        match = re.search(
            r"([a-zA-Z]+-[A-Z]+-\d+-\d+-\d+)",
            approved_files[0].name,
        )
        if match:
            sprint_id = match.group(1)

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
        "sprint_id":    sprint_id,
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
    name: str        = "The Lunchbags Sprint Reporter"
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

            sprint_id_input = timing.get("sprint_id", "UNKNOWN")
            started_at_str  = timing.get("started_at", datetime.now().isoformat())
            input_errors    = timing.get("errors", [])

            # ── Parse image data first ──────────────────
            pe_data    = _parse_photo_editor_report()
            ad_data    = _parse_art_director_report()
            assets     = _count_asset_library()
            images_gen = assets["total"]
            
            sprint_id = sprint_id_input
            if sprint_id == "UNKNOWN":
                sprint_id = assets.get("sprint_id", "UNKNOWN")

            # Fix images_planned
            images_planned = int(timing.get("images_planned", 0))
            if images_planned == 0:
                # Try to read from outputs
                pkg_path = OUTPUTS_DIR / "image_generation_package.md"
                if pkg_path.exists():
                    content = pkg_path.read_text()
                    match = re.search(
                        r"(\d+)\s+images?\s+(?:total|planned|to generate)",
                        content,
                        re.IGNORECASE,
                    )
                    if match:
                        images_planned = int(match.group(1))
                # Final fallback — count files in asset dir
                if images_planned == 0:
                    images_planned = assets["total"]

            # Calculate timings from file mtimes
            def get_mtime(filename: str) -> float:
                p = OUTPUTS_DIR / filename
                return p.stat().st_mtime if p.exists() else 0

            brief_mtime   = get_mtime("creative_brief.md")
            bible_mtime   = get_mtime("style_bible_and_shot_list.md")
            package_mtime = get_mtime("image_generation_package.md")
            pe_mtime      = get_mtime("photo_editor_latest.md")
            ad_mtime      = get_mtime("art_director_latest.md")

            def safe_diff(a: float, b: float) -> int:
                diff = int(a - b)
                return max(0, diff)

            # Use sprint start from timing input
            # or earliest file mtime as fallback
            earliest = min(
                t for t in [
                    brief_mtime, bible_mtime,
                    package_mtime
                ] if t > 0
            ) if any([
                brief_mtime, bible_mtime, package_mtime
            ]) else 0

            step_timings = {
                "build_creative_brief":
                    safe_diff(bible_mtime, earliest),
                "create_style_bible":
                    safe_diff(package_mtime, bible_mtime),
                "build_image_generation_package":
                    safe_diff(pe_mtime, package_mtime),
                "run_photo_editor":
                    safe_diff(ad_mtime, pe_mtime),
                "write_catalog":              0,
                "run_art_director":           0,
                "final_approval":             0,
            }

            try:
                started_at = datetime.fromisoformat(started_at_str)
            except Exception:
                started_at = datetime.fromtimestamp(earliest) if earliest > 0 else datetime.now()

            now           = datetime.now()
            # If ad_mtime is earlier than start (older run), use now as end
            end_time      = ad_mtime if ad_mtime > earliest else now.timestamp()
            total_seconds = safe_diff(end_time, earliest) if earliest > 0 else int((now - started_at).total_seconds())
            total_runtime = (
                f"{total_seconds // 3600}h "
                f"{(total_seconds % 3600) // 60}m "
                f"{total_seconds % 60}s"
            )

            costs = _estimate_costs(pe_data, ad_data, images_gen)

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
                f"# SPRINT REPORT — THE LUNCHBAGS\n"
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
                f"| First-pass approval rate | "
                f"{pe_data.get('passed', 0)}/"
                f"{pe_data.get('total', 1) or 1} "
                f"({round(pe_data.get('passed', 0) / max(pe_data.get('total', 1), 1) * 100)}%) |\n"
                f"| Film processed | "
                f"{assets.get('approved', 0)} |\n"
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
                secs = step_timings.get(key, 0)
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

            # ── Parse image level details ─────────────
            image_details = _parse_image_level_details()

            report += (
                f"\n{'='*55}\n"
                f"## 6b. PER-IMAGE QUALITY REPORT\n"
                f"{'='*55}\n\n"
                f"Full history of every image reviewed "
                f"this sprint — issues found, fixes "
                f"applied, and final status.\n\n"
            )

            if not image_details:
                report += "No image details available.\n\n"
            else:
                # Group by final status
                approved      = [
                    r for r in image_details
                    if r["final_status"] == "APPROVED"
                ]
                approved_fix  = [
                    r for r in image_details
                    if r["final_status"] == "APPROVED_AFTER_FIX"
                ]
                manual_review = [
                    r for r in image_details
                    if r["final_status"] == "NEEDS_MANUAL_REVIEW"
                ]
                art_flagged   = [
                    r for r in image_details
                    if r["final_status"] == "ART_REVIEW_FLAGGED"
                ]

                if approved:
                    report += "### ✅ Approved (First Pass)\n"
                    for r in approved:
                        report += f"- `{r['filename']}`\n"
                    report += "\n"

                if approved_fix:
                    report += "### 🛠 Approved (After Automated Fix)\n"
                    report += "| Image | PE Failures | Fix Applied | Attempts |\n|---|---|---|---|\n"
                    for r in approved_fix:
                        fails = ", ".join(r["pe_failures"]) if r["pe_failures"] else "None"
                        report += f"| `{r['filename']}` | {fails} | {r['pe_fix']} | {r['pe_fix_attempts']} |\n"
                    report += "\n"

                if art_flagged:
                    report += "### 🎨 Art Director Flagged (Needs Rework)\n"
                    report += "| Image | Creative Issues | Regeneration Note |\n|---|---|---|\n"
                    for r in art_flagged:
                        issues = ", ".join(r["ad_issues"]) if r["ad_issues"] else "Mood/Lighting Drift"
                        report += f"| `{r['filename']}` | {issues} | {r['ad_regen_note']} |\n"
                    report += "\n"

                if manual_review:
                    report += "### ✗ Flagged for Manual Review\n"
                    report += "| Image | Final PE Failure | Fix Attempted |\n|---|---|---|\n"
                    for r in manual_review:
                        fails = ", ".join(r["pe_failures"]) if r["pe_failures"] else "Failed review"
                        report += f"| `{r['filename']}` | {fails} | {r['pe_fix'] or 'N/A'} |\n"
                    report += "\n"

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
                f"## 9. DETAILED IMAGE REVIEWS\n"
                f"{'='*55}\n\n"
                f"This section details specific issues found by the Photo Editor and Art Director reviewers.\n\n"
                f"| Image | Reviewer | Status | Issues Found | Fix / Instruction |\n"
                f"|---|---|---|---|---|\n"
            )

            all_details = pe_data.get("image_details", []) + ad_data.get("image_details", [])
            if all_details:
                for det in all_details:
                    issues = ", ".join(det.get("issues", [])) if det.get("issues") else "None"
                    fix = det.get("fix_instruction") or det.get("attempts", "")
                    if det["status"] == "FIXED":
                        fix = f"Fixed ({det['attempts']} attempts)"
                    elif not fix:
                        fix = "N/A"
                    
                    report += f"| {det['name']} | {det['reviewer']} | {det['status']} | {issues} | {fix} |\n"
            else:
                report += "No detailed image review data found.\n"

            report += (
                f"\n{'='*55}\n"
                f"## 10. RECOMMENDATIONS FOR NEXT SPRINT\n"
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
