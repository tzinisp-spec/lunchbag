"""
RunLogger — captures everything printed to stdout/stderr and writes it
to outputs/run.log as JSONL, one entry per line.

The webapp reads this file live via /api/logs to power the Logs page.
"""

import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_PATH = Path("outputs/run.log")


def _infer(line: str) -> tuple[str, str]:
    """Return (level, src) inferred from line content."""
    # Level
    if "✓" in line or "— OK" in line or "COMPLETE" in line or "saved to" in line.lower():
        level = "SUCCESS"
    elif "✗" in line or "FATAL" in line or "ERROR:" in line or "failed" in line.lower() and "[Monitor]" in line:
        level = "ERROR"
    elif "⚠" in line or "retrying" in line.lower() or "retry" in line.lower() or "attempt" in line.lower():
        level = "WARN"
    elif "exception" in line.lower() or "traceback" in line.lower():
        level = "ERROR"
    else:
        level = "INFO"

    # Source
    if "[Monitor]" in line:
        src = "monitor"
    elif "[Phase 1]" in line or "[Phase 2]" in line:
        src = "pipeline"
    elif "[Crew]" in line or "[Agent]" in line or "Agent:" in line:
        src = "crew"
    elif "ImageGenerator" in line or "image_gen" in line.lower() or "Generating" in line:
        src = "image_gen"
    elif "PhotoEditor" in line or "photo_editor" in line.lower():
        src = "photo_editor"
    elif "Copywriter" in line or "ContentPlanner" in line or "ReviewGenerator" in line:
        src = "crew"
    else:
        src = "pipeline"

    return level, src


class _TeeStream:
    """Wraps stdout or stderr; tees every line to the log file."""

    def __init__(self, original, logger: "RunLogger", stderr: bool = False):
        self._orig    = original
        self._logger  = logger
        self._stderr  = stderr
        self._buf     = ""

    def write(self, text: str) -> int:
        self._orig.write(text)
        self._buf += text
        while "\n" in self._buf:
            line, self._buf = self._buf.split("\n", 1)
            stripped = line.strip()
            if stripped:
                self._logger._write_line(stripped, stderr=self._stderr)
        return len(text)

    def flush(self):
        self._orig.flush()

    # Forward everything else (fileno, isatty, …) to the original
    def __getattr__(self, name):
        return getattr(self._orig, name)


class RunLogger:
    """
    Install/remove stdout+stderr tees and write every printed line to
    outputs/run.log as JSONL.

    Usage in main.py / main_phase2.py:
        logger = RunLogger()
        logger.start()
        ...
        logger.stop()
    """

    def __init__(self):
        self._orig_stdout = None
        self._orig_stderr = None
        self._active      = False

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Reset log file and install stdout/stderr tees."""
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOG_PATH.write_text("")          # truncate / create

        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr
        sys.stdout = _TeeStream(self._orig_stdout, self, stderr=False)
        sys.stderr = _TeeStream(self._orig_stderr, self, stderr=True)
        self._active = True

        self._write_line("=== run started ===", stderr=False, level="INFO", src="pipeline")

    def stop(self) -> None:
        """Flush any buffered lines and remove tees."""
        if not self._active:
            return
        self._write_line("=== run finished ===", stderr=False, level="INFO", src="pipeline")
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr
        self._active = False

    # ── Internal ──────────────────────────────────────────────────────────────

    def _write_line(
        self,
        line: str,
        stderr: bool = False,
        level: Optional[str] = None,
        src: Optional[str] = None,
    ) -> None:
        inferred_level, inferred_src = _infer(line)
        if level:
            final_level = level
        elif stderr and inferred_level == "INFO":
            final_level = "WARN"
        else:
            final_level = inferred_level
        entry = {
            "ts":    datetime.now().isoformat(timespec="milliseconds"),
            "level": final_level,
            "src":   src or inferred_src,
            "msg":   line,
        }
        try:
            with LOG_PATH.open("a") as fh:
                fh.write(json.dumps(entry) + "\n")
        except Exception:
            pass
