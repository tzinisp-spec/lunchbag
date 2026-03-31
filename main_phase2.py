import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from lunchbag.tools.copywriter_tool import CopywriterTool
from lunchbag.tools.content_planner_tool import ContentPlannerTool
from lunchbag.tools.review_generator_tool import ReviewGeneratorTool
from lunchbag.tools.sprint_reporter_tool import SprintReporterTool
from lunchbag.tools.catalog_utils import sync_catalog
from lunchbag.tools.progress_tracker import ProgressTracker, PROGRESS_P2_PATH
from lunchbag.tools.run_logger import RunLogger

MAX_STEP_ATTEMPTS = 3
RETRY_DELAY       = 10   # seconds between step retries

PHASE2_MILESTONES = [
    {"id": "copywriter",         "label": "Copywriter",         "agent": "copywriter"},
    {"id": "content_planner",    "label": "Content Planner",    "agent": "planner"},
    {"id": "review_generator",   "label": "Review Generator",   "agent": "orchestrator"},
    {"id": "sprint_report_p2",   "label": "Sprint Report",      "agent": "orchestrator"},
]


# ── Shoot folder detection ────────────────────────────────

def get_latest_shoot() -> str:
    base = Path("asset_library/images")
    if not base.exists():
        return ""
    folders = []
    for month_dir in base.iterdir():
        if not month_dir.is_dir():
            continue
        for shoot_dir in month_dir.iterdir():
            if (shoot_dir.is_dir()
                    and shoot_dir.name.startswith("Shoot")):
                folders.append(
                    f"{month_dir.name}/{shoot_dir.name}"
                )
    return sorted(folders)[-1] if folders else ""


# ── Monitor ───────────────────────────────────────────────

def _is_quota_exhausted(result: str) -> bool:
    return "DAILY_QUOTA_EXHAUSTED" in result


def _error_snippet(result: str) -> str:
    if result.startswith("EXCEPTION: "):
        return result[len("EXCEPTION: "):][:100]
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
    - Retries up to max_attempts on failure.
    - Hard-stops immediately on daily quota exhaustion.
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


# ── Success checks ────────────────────────────────────────

def _check_copywriter(result: str) -> bool:
    return "COPY COMPLETE" in result


def _check_content_planner(result: str) -> bool:
    return "MONTHLY CALENDAR COMPLETE" in result


def _check_review_generator(result: str) -> bool:
    return "REVIEW GENERATED" in result


def _check_sprint_reporter(result: str) -> bool:
    return "Sprint Report saved to" in result


# ── Main run ──────────────────────────────────────────────

def run():
    SHOOT_FOLDER = (
        os.getenv("SHOOT_FOLDER")
        or get_latest_shoot()
    )
    os.environ["SHOOT_FOLDER"] = SHOOT_FOLDER
    os.environ["REPORT_TYPE"]  = "content_planning"
    print(f"[Phase 2] Using shoot: {SHOOT_FOLDER}")

    print("\n" + "="*60)
    print("  THE LUNCHBAGS — PHASE 2")
    print("  Content Pipeline")
    print("="*60 + "\n")

    # ── Logger + progress tracker ──────────────────
    logger = RunLogger()
    logger.start()

    tracker = ProgressTracker(path=PROGRESS_P2_PATH)
    tracker.start_run(f"Phase2-{SHOOT_FOLDER.replace('/', '_')}", PHASE2_MILESTONES)
    tracker.set_meta(shoot_folder=SHOOT_FOLDER, phase="content_planning")

    # ── Catalog resync ────────────────────────────
    # Rebuilds catalog.json from actual files on disk
    # so any deletions or manual review changes made
    # since Phase 1 are reflected before copy runs.
    print("[Phase 2] Resyncing catalog from disk...")
    images = sync_catalog()
    approved = sum(
        1 for img in images
        if img.get("status") == "approved"
    )
    pending = len(images) - approved
    print(
        f"[Phase 2] Catalog synced: "
        f"{len(images)} images "
        f"({approved} approved, {pending} pending)\n"
    )

    # Step 1 — Copywriter
    _run_step_with_retry(
        "Step 1 — Copywriter",
        lambda: CopywriterTool()._run(""),
        _check_copywriter,
        tracker=tracker,
        mid="copywriter",
    )

    # Step 2 — Content Planner
    _run_step_with_retry(
        "Step 2 — Content Planner",
        lambda: ContentPlannerTool()._run(""),
        _check_content_planner,
        tracker=tracker,
        mid="content_planner",
    )

    # Step 3 — Review Generator
    _run_step_with_retry(
        "Step 3 — Review Generator",
        lambda: ReviewGeneratorTool()._run(""),
        _check_review_generator,
        tracker=tracker,
        mid="review_generator",
    )

    # Step 4 — Sprint Report
    _run_step_with_retry(
        "Step 4 — Sprint Report",
        lambda: SprintReporterTool()._run("{}"),
        _check_sprint_reporter,
        tracker=tracker,
        mid="sprint_report_p2",
    )

    tracker.finish_run("completed")
    logger.stop()

    print("\n" + "="*60)
    print("  PHASE 2 COMPLETE")
    print("  Review: outputs/review.html")
    print("  Calendar: outputs/monthly_calendar.md")
    print("  Report: outputs/sprint_report_latest.md")
    print("="*60 + "\n")

    os.system("open outputs/review.html")


if __name__ == "__main__":
    run()
