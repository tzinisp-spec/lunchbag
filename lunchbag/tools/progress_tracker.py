"""
ProgressTracker — writes outputs/run_progress.json as the pipeline runs.
The webapp reads this file live to power the dashboard activity feed.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

PROGRESS_PATH = Path("outputs/run_progress.json")
PROGRESS_P2_PATH = Path("outputs/run_progress_p2.json")


def _fmt(seconds) -> str:
    """Format duration in seconds to a human-readable string."""
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


class ProgressTracker:
    """
    Tracks pipeline milestone progress.

    Usage (main.py):
        tracker = ProgressTracker()
        tracker.start_run(run_id, MILESTONES)
        ...
        tracker.milestone_start("creative_brief")
        tracker.milestone_done("creative_brief")
        ...
        tracker.finish_run()

    Usage (main_phase2.py):
        tracker = ProgressTracker()
        tracker.resume_run(PHASE2_MILESTONES)
        ...
    """

    def __init__(self, path: Path | None = None):
        self._path: Path = Path(path) if path else PROGRESS_PATH
        self._data: dict = {}

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start_run(self, run_id: str, milestones: list[dict]) -> None:
        """Reset and write a fresh progress file. Call at the very start of main.py."""
        self._data = {
            "run_id":       run_id,
            "started_at":   datetime.now().isoformat(),
            "status":       "in_progress",
            "completed_at": None,
            "milestones": [
                {
                    "id":           m["id"],
                    "label":        m["label"],
                    "agent":        m.get("agent", ""),
                    "status":       "pending",
                    "started_at":   None,
                    "completed_at": None,
                    "duration_s":   None,
                    "attempts":     0,
                }
                for m in milestones
            ],
            "log": [],
        }
        self._save()

    def resume_run(self, milestones: list[dict]) -> None:
        """
        For Phase 2: read the existing progress file and append new milestones.
        If no file exists, starts a fresh run.
        """
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text())
                self._data["status"] = "in_progress"
                existing = {m["id"] for m in self._data["milestones"]}
                for m in milestones:
                    if m["id"] not in existing:
                        self._data["milestones"].append({
                            "id":           m["id"],
                            "label":        m["label"],
                            "agent":        m.get("agent", ""),
                            "status":       "pending",
                            "started_at":   None,
                            "completed_at": None,
                            "duration_s":   None,
                            "attempts":     0,
                        })
                self._save()
                return
            except Exception:
                pass
        self.start_run("unknown", milestones)

    def set_meta(self, **kwargs) -> None:
        """Store extra key/value pairs in the progress file (e.g. shoot_folder)."""
        self._data.update(kwargs)
        self._save()

    def finish_run(self, status: str = "completed") -> None:
        self._data["status"]       = status
        self._data["completed_at"] = datetime.now().isoformat()
        self._save()

    # ── Milestone state ───────────────────────────────────────────────────────

    def milestone_start(self, mid: str, attempt: int = 1) -> None:
        m = self._find(mid)
        if m:
            m["status"]   = "in_progress"
            m["attempts"] = attempt
            if attempt == 1 or not m["started_at"]:
                m["started_at"] = datetime.now().isoformat()
        label  = m["label"] if m else mid
        suffix = f" (attempt {attempt}/3)" if attempt > 1 else ""
        self._log("start", mid, f"{label} started{suffix}")
        self._save()

    def milestone_done(self, mid: str) -> None:
        m   = self._find(mid)
        now = datetime.now()
        if m:
            m["status"]       = "completed"
            m["completed_at"] = now.isoformat()
            if m["started_at"]:
                elapsed       = now - datetime.fromisoformat(m["started_at"])
                m["duration_s"] = int(elapsed.total_seconds())
        label = m["label"] if m else mid
        dur   = _fmt(m["duration_s"]) if m else ""
        self._log("complete", mid, f"{label} completed" + (f" in {dur}" if dur else ""))
        self._save()

    def milestone_fail(self, mid: str, error: str = "", final: bool = False) -> None:
        m     = self._find(mid)
        label = m["label"] if m else mid
        if final:
            if m:
                m["status"] = "failed"
                now = datetime.now()
                m["completed_at"] = now.isoformat()
                if m["started_at"]:
                    elapsed = now - datetime.fromisoformat(m["started_at"])
                    m["duration_s"] = int(elapsed.total_seconds())
            msg = f"{label} failed" + (f" — {error}" if error else "")
            self._log("fail", mid, msg)
        else:
            attempts = m["attempts"] if m else 1
            msg = f"{label} retrying (attempt {attempts}/3)" + (f" — {error}" if error else "")
            self._log("retry", mid, msg)
        self._save()

    # ── Queries ───────────────────────────────────────────────────────────────

    def get_milestone(self, mid: str) -> Optional[dict]:
        return self._find(mid)

    # ── Internal ─────────────────────────────────────────────────────────────

    def _find(self, mid: str) -> Optional[dict]:
        for m in self._data.get("milestones", []):
            if m["id"] == mid:
                return m
        return None

    def _log(self, type_: str, milestone: str, message: str) -> None:
        self._data.setdefault("log", []).append({
            "ts":        datetime.now().isoformat(),
            "type":      type_,
            "milestone": milestone,
            "message":   message,
        })

    def _save(self) -> None:
        """Atomic write — prevents the webapp reading a half-written file."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2))
        tmp.rename(self._path)
