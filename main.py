import os
import re
import sys
import json
import time
import threading
import calendar as cal_module
from pathlib import Path
from datetime import date, datetime
from dotenv import load_dotenv
from lunchbag.crew import LunchbagCrew
from lunchbag.trend_crew import LunchbagTrendCrew
from lunchbag.tools.image_generator_tool import ImageGeneratorTool
from lunchbag.tools.film_processor_tool import FilmProcessorTool
from lunchbag.tools.photo_editor_tool import PhotoEditorTool
from lunchbag.tools.catalog_writer_tool import CatalogWriterTool
from lunchbag.tools.sprint_reporter_tool import SprintReporterTool
from lunchbag.tools.progress_tracker import ProgressTracker
from lunchbag.tools.run_logger import RunLogger
from lunchbag.tools.catalog_utils import CatalogSyncWatcher

load_dotenv()

TOTAL_SETS = 3
IMAGE_DISTRIBUTION = {1: 17, 2: 17, 3: 16}
MAX_STEP_ATTEMPTS  = 3
RETRY_DELAY        = 10   # seconds between step retries

# Milestones in run order — passed to ProgressTracker.start_run()
PHASE1_MILESTONES = [
    {"id": "creative_brief",      "label": "Creative Brief",             "agent": "strategist"},
    {"id": "style_bible",         "label": "Style Bible + Shot List",    "agent": "director"},
    {"id": "image_gen_set_1",     "label": "Image Generation — Set 1",   "agent": "photographer"},
    {"id": "photo_editor_set_1",  "label": "Photo Editor Review — Set 1","agent": "photo_editor"},
    {"id": "image_gen_set_2",     "label": "Image Generation — Set 2",   "agent": "photographer"},
    {"id": "photo_editor_set_2",  "label": "Photo Editor Review — Set 2","agent": "photo_editor"},
    {"id": "image_gen_set_3",     "label": "Image Generation — Set 3",   "agent": "photographer"},
    {"id": "photo_editor_set_3",  "label": "Photo Editor Review — Set 3","agent": "photo_editor"},
    {"id": "sprint_report",       "label": "Sprint Report",              "agent": "orchestrator"},
]

INPUTS = {
    "brand_name":        "The Lunchbags",
    "current_season":    "Spring 2026",
    "client_code":       "lunchbag",
    "shoot_month":       "03",
    "shoot_day":         "20",
    "product_focus":     "Original thermal lunch bag — cotton exterior, waterproof interior, Thermo Hot&Cold mechanism, H21cm x W16cm x D24cm, various prints and colours",
    "product_materials": "Cotton exterior, waterproof interior lining, thermal insulation, fabric straps. Surface has a soft textile feel — not leather, not plastic, not glossy. Bold graphic prints on cotton.",
    "target_audience":   "Women and men 25-45, Greece and Europe, active lifestyle, health-conscious, daily commuters, parents, office workers, anyone who carries food on the go",
    "content_mix":       "35% bag in use — carried or held by model, 25% product only — bag on surface, 20% detail close-up — print texture and materials, 15% lifestyle context — food preparation or outdoor setting, 5% flat lay — bag open showing interior",
    "posts_per_week":    "5",
    "images_per_sprint": "50",
    "shoot_dont_list":   "No artificial clinical lighting, no white studio backgrounds, no images that make the bag look cheap or disposable",
    "imagen_style_anchor": "High-end lifestyle photography, 8k resolution, photorealistic, cinematic lighting.",
    "current_date":      date.today().strftime("%B %d, %Y"),
}


# ── Monitor ──────────────────────────────────────────────

FATAL_EXCEPTION_TYPES = (
    AttributeError,
    TypeError,
    ImportError,
    ModuleNotFoundError,
    SyntaxError,
    NotImplementedError,
)


def _is_quota_exhausted(result: str) -> bool:
    return "DAILY_QUOTA_EXHAUSTED" in result


def _is_fatal_error(result: str) -> bool:
    return "FATAL_ERROR:" in result


def _error_snippet(result: str) -> str:
    """Extract a short readable error from a result string."""
    for prefix in ("EXCEPTION: ", "FATAL_ERROR: "):
        if result.startswith(prefix):
            return result[len(prefix):][:100]
    if "503" in result:
        return "503 service unavailable"
    if "quota" in result.lower():
        return "API quota exceeded"
    return result[:100] if result else "unknown error"


def _run_step_with_retry(
    step_name: str,
    step_fn,
    success_check,
    max_attempts: int = MAX_STEP_ATTEMPTS,
    tracker: ProgressTracker = None,
    mid: str = None,
) -> tuple[bool, str]:
    """
    Run a pipeline step with automatic retry.
    - Retries up to max_attempts on transient failures.
    - Hard-stops immediately on daily quota exhaustion.
    - Hard-stops immediately on fatal errors (code bugs,
      missing attributes, bad imports) that will never
      resolve on retry.
    - Optionally updates a ProgressTracker milestone.
    - Returns (success, last_result).
    """
    last_result = ""
    for attempt in range(1, max_attempts + 1):
        print(
            f"\n[Monitor] ── {step_name} "
            f"(attempt {attempt}/{max_attempts}) ──"
        )
        if tracker and mid:
            tracker.milestone_start(mid, attempt)

        try:
            last_result = step_fn()
        except FATAL_EXCEPTION_TYPES as e:
            last_result = f"FATAL_ERROR: {type(e).__name__}: {e}"
        except Exception as e:
            last_result = f"EXCEPTION: {e}"

        print(last_result)

        if _is_quota_exhausted(last_result):
            print(
                f"\n[Monitor] ✗ DAILY API QUOTA EXHAUSTED\n"
                f"  Pipeline stopped. "
                f"Resume tomorrow.\n"
            )
            if tracker and mid:
                tracker.milestone_fail(mid, "Daily API quota exhausted", final=True)
                tracker.finish_run("failed")
            sys.exit(1)

        if _is_fatal_error(last_result):
            print(
                f"\n[Monitor] ✗ FATAL ERROR — retrying will not help.\n"
                f"  Fix the underlying issue and re-run.\n"
                f"  {last_result}\n"
            )
            if tracker and mid:
                tracker.milestone_fail(mid, _error_snippet(last_result), final=True)
                tracker.finish_run("failed")
            sys.exit(1)

        if success_check(last_result):
            print(f"[Monitor] ✓ {step_name} — OK")
            if tracker and mid:
                tracker.milestone_done(mid)
            return True, last_result

        print(
            f"[Monitor] ✗ {step_name} failed "
            f"(attempt {attempt}/{max_attempts})"
        )
        if tracker and mid:
            is_final = (attempt == max_attempts)
            tracker.milestone_fail(mid, _error_snippet(last_result), final=is_final)

        if attempt < max_attempts:
            print(
                f"[Monitor] Retrying in {RETRY_DELAY}s..."
            )
            time.sleep(RETRY_DELAY)

    print(
        f"[Monitor] ✗ {step_name} — "
        f"all {max_attempts} attempts failed. "
        f"Continuing pipeline with warning."
    )
    return False, last_result


def _check_style_bible() -> bool:
    """Style bible exists, has SET DNA blocks and shot refs."""
    path = Path("outputs/style_bible_and_shot_list.md")
    if not path.exists():
        return False
    content = path.read_text()
    has_dna   = "SET DNA PROMPT BLOCK" in content
    has_shots = bool(re.search(r"\[SHOOT-", content))
    return has_dna and has_shots


def _check_image_gen(result: str, expected: int) -> bool:
    """All expected images generated successfully."""
    return f"{expected}/{expected} successful" in result


def _check_film_processor(result: str) -> bool:
    """All images processed without error."""
    return "All images processed successfully" in result


def _check_photo_editor(result: str) -> bool:
    """
    Photo editor ran to completion.
    Flagged images are expected — they are not failures.
    Failure = crash, server disconnect, or TOOL_ERROR.
    """
    if "TOOL_ERROR" in result:
        return False
    if "Server disconnected" in result:
        return False
    if "EXCEPTION" in result:
        return False
    # Must contain at least one review result
    return (
        "PASS" in result
        or "FIXED" in result
        or "FLAGGED" in result
        or "REGEN_NEEDED" in result
    )


def _check_catalog(result: str) -> bool:
    """Catalog written successfully."""
    return "SUCCESS" in result


# ── Crew file watcher ────────────────────────────────────

def _watch_crew_files(
    tracker: ProgressTracker,
    run_start: float,
    stop: threading.Event,
) -> None:
    """
    Background thread.
    Polls for creative_brief.md and style_bible_and_shot_list.md.
    When each appears (with mtime > run_start) it advances the
    corresponding milestone, giving live sub-task visibility
    inside the crew's otherwise opaque run.
    """
    brief_path = Path("outputs/creative_brief.md")
    bible_path = Path("outputs/style_bible_and_shot_list.md")
    brief_seen = 0.0
    bible_seen = 0.0

    while not stop.is_set():
        try:
            bm = brief_path.stat().st_mtime if brief_path.exists() else 0
            if bm > run_start and bm > brief_seen:
                brief_seen = bm
                m = tracker.get_milestone("creative_brief")
                if m and m["status"] == "in_progress":
                    tracker.milestone_done("creative_brief")
                    sm = tracker.get_milestone("style_bible")
                    if sm and sm["status"] == "pending":
                        tracker.milestone_start("style_bible", 1)
        except Exception:
            pass

        try:
            sm = bible_path.stat().st_mtime if bible_path.exists() else 0
            if sm > run_start and sm > bible_seen:
                bible_seen = sm
                m = tracker.get_milestone("style_bible")
                if m and m["status"] == "in_progress":
                    tracker.milestone_done("style_bible")
        except Exception:
            pass

        stop.wait(timeout=3)


def _finalize_crew_milestones(tracker: ProgressTracker, success: bool) -> None:
    """Ensure creative_brief and style_bible end in a terminal state."""
    for mid in ("creative_brief", "style_bible"):
        m = tracker.get_milestone(mid)
        if not m:
            continue
        if success and m["status"] != "completed":
            tracker.milestone_done(mid)
        elif not success and m["status"] in ("pending", "in_progress"):
            tracker.milestone_fail(mid, "Creative planning failed", final=True)


# ── Shoot folder ─────────────────────────────────────────

def create_shoot_folder() -> tuple[str, str]:
    """
    Create the next ShootXX folder under the current month
    directory. Numbering resets each month (Shoot01, …).
    Sets SHOOT_FOLDER env var.
    Returns (shoot_folder, shoot_name).
    """
    month_num    = int(INPUTS.get("shoot_month", str(date.today().month)))
    season       = INPUTS.get("current_season", "")
    year         = season.split()[-1] if season else str(date.today().year)
    month_name   = cal_module.month_name[month_num]
    month_folder = f"{month_name}{year}"

    base_dir = Path("asset_library/images") / month_folder
    base_dir.mkdir(parents=True, exist_ok=True)

    existing = sorted([
        d for d in base_dir.iterdir()
        if d.is_dir() and d.name.startswith("Shoot")
    ])
    next_num   = len(existing) + 1
    shoot_name = f"Shoot{next_num:02d}"
    (base_dir / shoot_name).mkdir(exist_ok=True)

    shoot_folder = f"{month_folder}/{shoot_name}"
    os.environ["SHOOT_FOLDER"] = shoot_folder
    os.environ["CURRENT_SET"]  = "0"
    return shoot_folder, shoot_name


def get_images_per_set(
    total: int, sets: int, set_num: int
) -> int:
    if sets == 3:
        return IMAGE_DISTRIBUTION.get(set_num, 17)
    base      = total // sets
    remainder = total % sets
    if set_num == sets:
        return base + remainder
    return base


# ── Regen pass ───────────────────────────────────────────

def _run_regen_pass(set_num: int) -> None:
    """
    After photo editor, find any Regen- files (structural
    failures), regenerate those specific shots, run film
    processing and QC on them, then update the catalog.
    Limited to 1 regen round to avoid infinite loops.
    """
    shoot_folder = os.environ.get("SHOOT_FOLDER", "")
    asset_dir = (
        Path("asset_library/images")
        / shoot_folder
        / f"Set{set_num}"
    )
    regen_files = sorted([
        f for f in asset_dir.iterdir()
        if f.name.startswith("Regen-")
    ])
    if not regen_files:
        return

    print(
        f"\n[Monitor] Found {len(regen_files)} structural "
        f"failure(s) → auto-regenerating..."
    )

    # Extract shot codes from filenames
    # e.g. Regen-lunchbag-SPRING-26-03-20-Shoot11-S1-006.png
    shot_codes = []
    clean_names = []
    for f in regen_files:
        m = re.search(r"-(S\d+-\d+)\.png$", f.name)
        if m:
            shot_codes.append(m.group(1))
        clean = f.name[len("Regen-"):]
        clean_names.append(clean)
        f.rename(f.parent / clean)

    if not shot_codes:
        print("[Monitor] ⚠ Could not extract shot codes — skipping regen.")
        return

    print(f"[Monitor] Regenerating: {', '.join(shot_codes)}")

    # Regenerate specific shots
    os.environ["REGEN_SHOTS"] = ",".join(shot_codes)
    ok, _ = _run_step_with_retry(
        f"Set {set_num} — Regen Generation ({len(shot_codes)} shots)",
        lambda: ImageGeneratorTool()._run(""),
        lambda r: "successful" in r,
    )
    os.environ.pop("REGEN_SHOTS", None)

    if not ok:
        print("[Monitor] ⚠ Regen generation failed — skipping QC.")
        return

    # Film processing for regenerated shots only
    _run_step_with_retry(
        f"Set {set_num} — Regen Film Processing",
        lambda: FilmProcessorTool()._run(""),
        _check_film_processor,
    )

    # QC on regenerated shots only
    os.environ["REGEN_FILES"] = ",".join(clean_names)
    _run_step_with_retry(
        f"Set {set_num} — Regen QC ({len(clean_names)} shots)",
        lambda: PhotoEditorTool()._run(""),
        _check_photo_editor,
    )
    os.environ.pop("REGEN_FILES", None)

    # Update catalog with any newly approved shots
    _run_step_with_retry(
        f"Set {set_num} — Regen Catalog Update",
        lambda: CatalogWriterTool()._run(""),
        _check_catalog,
    )


# ── Set pipeline ─────────────────────────────────────────

def run_set(
    set_num: int,
    images_this_set: int,
    tracker: ProgressTracker = None,
) -> dict:
    """Run all steps for one set. Returns timing dict."""
    os.environ["CURRENT_SET"]     = str(set_num)
    os.environ["IMAGES_THIS_SET"] = str(images_this_set)

    set_start = time.time()
    step_times = {}

    # Step 1 — Image Generation
    t0 = time.time()
    _run_step_with_retry(
        f"Set {set_num} — Image Generation",
        lambda: ImageGeneratorTool()._run(""),
        lambda r: _check_image_gen(r, images_this_set),
        tracker=tracker,
        mid=f"image_gen_set_{set_num}",
    )
    step_times["image_generation"] = int(time.time() - t0)

    # Step 2 — Film Processing (internal, not a top-level milestone)
    t0 = time.time()
    _run_step_with_retry(
        f"Set {set_num} — Film Processing",
        lambda: FilmProcessorTool()._run(""),
        _check_film_processor,
    )
    step_times["film_processing"] = int(time.time() - t0)

    # Step 3 — Photo Editor
    t0 = time.time()
    _run_step_with_retry(
        f"Set {set_num} — Photo Editor",
        lambda: PhotoEditorTool()._run(""),
        _check_photo_editor,
        tracker=tracker,
        mid=f"photo_editor_set_{set_num}",
    )
    step_times["photo_editor"] = int(time.time() - t0)

    # Step 3b — Auto-regen structural failures
    _run_regen_pass(set_num)

    # Step 4 — Catalog (internal, not a top-level milestone)
    t0 = time.time()
    _run_step_with_retry(
        f"Set {set_num} — Catalog",
        lambda: CatalogWriterTool()._run(""),
        _check_catalog,
    )
    step_times["catalog"] = int(time.time() - t0)

    return {
        "set":        set_num,
        "images":     images_this_set,
        "start_ts":   set_start,
        "end_ts":     time.time(),
        "duration_s": int(time.time() - set_start),
        "steps":      step_times,
    }


# ── Trend scout ──────────────────────────────────────────

def run_trend_scout():
    """Run the Trend Scout only — once per month."""
    os.makedirs("trends", exist_ok=True)
    print("\n" + "="*60)
    print("  THE LUNCHBAGS — TREND SCOUT")
    print("="*60 + "\n")

    LunchbagTrendCrew().crew().kickoff(inputs=INPUTS)

    print("\n" + "="*60)
    print("  DONE: trends/latest_trends.md")
    print("="*60 + "\n")


# ── Main run ─────────────────────────────────────────────

def run():
    """Run the monthly creative sprint."""
    os.makedirs("outputs",              exist_ok=True)
    os.makedirs("memory",               exist_ok=True)
    os.makedirs("asset_library/images", exist_ok=True)
    os.makedirs("references",           exist_ok=True)

    # ── Create shoot folder ──────────────────────────
    shoot_folder, shoot_name = create_shoot_folder()
    print(
        f"[Phase 1] Shoot folder: "
        f"asset_library/images/{shoot_folder}"
    )

    # ── Compute shoot ID ─────────────────────────────
    season_code = INPUTS.get(
        "current_season", "SPR-26"
    ).replace(" ", "-").upper()[:6]
    client = INPUTS.get("client_code", "client")
    month  = INPUTS.get("shoot_month", "01")
    day    = INPUTS.get("shoot_day", "01")
    year   = INPUTS.get(
        "current_season", "2026"
    ).split()[-1][2:]

    shoot_id = (
        f"{client}-{season_code}-{year}-{month}-{day}"
        f"-{shoot_name}"
    )
    INPUTS["shoot_id"] = shoot_id
    os.environ["SHOOT_ID"] = shoot_id
    print(f"Shoot ID: {shoot_id}")

    # ── Start logger + progress tracker ──────────────
    logger = RunLogger()
    logger.start()

    tracker = ProgressTracker()
    tracker.start_run(shoot_id, PHASE1_MILESTONES)
    tracker.set_meta(
        shoot_folder=shoot_folder,
        set_expected=IMAGE_DISTRIBUTION,   # {1: 17, 2: 17, 3: 16}
    )

    # ── Reset API counters for this sprint ───────────
    _counters_path = Path("outputs/api_counters.json")
    _counters_path.write_text(json.dumps({
        "image_gen_calls":   0,
        "preflight_calls":   0,
        "fix_calls":         0,
        "review_calls":      0,
        "batch_check_calls": 0,
        "text_calls":        0,
    }, indent=2))

    # ── Check references ─────────────────────────────
    ref_dir    = Path("references")
    ref_images = []
    if ref_dir.exists():
        ref_images = [
            f for f in ref_dir.iterdir()
            if f.suffix.lower() in {".png", ".jpg", ".jpeg"}
        ]
    for set_name in ["Set1", "Set2", "Set3"]:
        set_path = ref_dir / set_name
        if set_path.exists():
            ref_images += [
                f for f in set_path.iterdir()
                if f.suffix.lower() in {".png", ".jpg", ".jpeg"}
            ]
    if not ref_images:
        print("=" * 60)
        print("  ⚠  MISSING: No reference images found")
        print("  Add images to references/ or references/Set1/")
        sys.exit(1)
    print(f"  ✓ References: {len(ref_images)} image(s) found")

    # ── Phase 1 — Creative Planning ──────────────────
    print("\n" + "="*60)
    print("  THE LUNCHBAGS — PHASE 1: CREATIVE PLANNING")
    print("="*60 + "\n")

    def _run_crew():
        LunchbagCrew().run_with_report(phase=1, inputs=INPUTS)
        return "crew_complete"

    # Start crew with file watcher tracking brief + bible in background
    crew_start_ts = time.time()
    tracker.milestone_start("creative_brief")
    _crew_stop  = threading.Event()
    _crew_watch = threading.Thread(
        target=_watch_crew_files,
        args=(tracker, crew_start_ts, _crew_stop),
        daemon=True,
    )
    _crew_watch.start()

    crew_ok, _ = _run_step_with_retry(
        "Phase 1 — Creative Planning Crew",
        _run_crew,
        lambda _: _check_style_bible(),
    )

    _crew_stop.set()
    _crew_watch.join(timeout=5)
    _finalize_crew_milestones(tracker, crew_ok)

    if not _check_style_bible():
        print(
            "\n[Monitor] ✗ Style bible missing or incomplete "
            "after all retries.\n"
            "  Cannot proceed to image generation "
            "without creative direction.\n"
            "  Exiting."
        )
        sys.exit(1)

    print("\n" + "="*60)
    print("  CREATIVE PLANNING COMPLETE")
    print("  Style Bible: outputs/style_bible_and_shot_list.md")
    print("="*60 + "\n")

    # ── Phase 1b — Generate all sets ─────────────────
    total_images   = int(INPUTS.get("images_per_sprint", "50"))
    shoot_start    = time.time()
    phase1_end     = time.time()   # creative planning just finished
    set_timings    = []

    # Write timing file immediately so the webapp shows a live run
    try:
        _timing_path = Path("outputs/shoot_timing.json")
        _timing_path.write_text(json.dumps({
            "sprint_id":   os.environ.get("SHOOT_ID", "UNKNOWN"),
            "shoot_start": shoot_start,
            "started_at":  datetime.fromtimestamp(shoot_start).isoformat(),
            "set_timings": [],
        }, indent=2))
    except Exception:
        pass

    # Start catalog watcher — keeps catalog.json live as images are
    # generated and as the photo editor renames files.
    _catalog_watcher = CatalogSyncWatcher()
    _catalog_watcher.start()

    for set_num in range(1, TOTAL_SETS + 1):
        print("\n" + "="*60)
        print(
            f"  THE LUNCHBAGS — "
            f"SET {set_num} of {TOTAL_SETS}"
        )
        print("="*60 + "\n")

        images_this_set = get_images_per_set(
            total_images, TOTAL_SETS, set_num
        )
        set_result = run_set(set_num, images_this_set, tracker=tracker)
        set_timings.append(set_result)

        # Update live timing file after each set so webapp tracks progress
        try:
            _timing_path.write_text(json.dumps({
                "sprint_id":   os.environ.get("SHOOT_ID", "UNKNOWN"),
                "shoot_start": shoot_start,
                "started_at":  datetime.fromtimestamp(shoot_start).isoformat(),
                "set_timings": set_timings,
            }, indent=2))
        except Exception:
            pass

        print("\n" + "="*60)
        if set_num < TOTAL_SETS:
            print(f"  SET {set_num} COMPLETE")
        else:
            print(f"  ALL {TOTAL_SETS} SETS COMPLETE")
            print(
                f"  Shoot: "
                f"asset_library/images/{shoot_folder}"
            )
            print(f"  Run main_phase2.py when ready")
        print("="*60 + "\n")

    os.environ["CURRENT_SET"] = "0"

    # Stop watcher — does a final sync before returning
    _catalog_watcher.stop()

    # ── Save timing for sprint reporter ──────────────
    shoot_end = time.time()
    try:
        timing_data = {
            "sprint_id":       os.environ.get("SHOOT_ID", "UNKNOWN"),
            "shoot_start":     shoot_start,
            "phase1_end":      phase1_end,
            "phase1_duration": int(phase1_end - shoot_start),
            "set_timings":     set_timings,
            "shoot_end":       shoot_end,
            "total_duration":  int(shoot_end - shoot_start),
            "started_at":      datetime.fromtimestamp(
                                   shoot_start
                               ).isoformat(),
        }
        timing_path = Path("outputs/shoot_timing.json")
        timing_path.write_text(json.dumps(timing_data, indent=2))
    except Exception as e:
        print(f"\n[Monitor] ⚠ Could not save timing data: {e}")
        timing_data = {}

    # ── Sprint Report ─────────────────────────────────
    print("\n" + "="*60)
    print("  GENERATING SPRINT REPORT")
    print("="*60 + "\n")
    try:
        _run_step_with_retry(
            "Sprint Report",
            lambda: SprintReporterTool()._run(json.dumps(timing_data)),
            lambda r: "Sprint Report saved to" in r,
            tracker=tracker,
            mid="sprint_report",
        )
    except Exception as e:
        print(
            f"\n[Monitor] ⚠ Sprint report failed: {e}\n"
            f"  All {TOTAL_SETS} sets completed successfully.\n"
            f"  Timing data: outputs/shoot_timing.json\n"
            f"  Run SprintReporterTool manually if needed.\n"
        )

    tracker.finish_run("completed")
    logger.stop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--trends":
        run_trend_scout()
    else:
        run()
