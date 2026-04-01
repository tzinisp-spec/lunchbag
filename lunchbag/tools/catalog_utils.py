import json
import os
import re
import threading
from pathlib import Path
from datetime import datetime

BASE_DIR = Path("asset_library/images")


def _get_catalog_path() -> Path:
    shoot_folder = os.getenv("SHOOT_FOLDER", "")
    if shoot_folder:
        return BASE_DIR / shoot_folder / "catalog.json"
    return Path("asset_library/catalog.json")


def sync_catalog():
    """
    Scans the current shoot folder (or all of asset_library/images
    if SHOOT_FOLDER is not set) and writes catalog.json into the
    shoot folder.
    """
    images = []
    shoot_folder = os.getenv("SHOOT_FOLDER", "")
    scan_dir = (
        BASE_DIR / shoot_folder if shoot_folder else BASE_DIR
    )

    if not scan_dir.exists():
        return []

    # Walk through all files in the scan directory
    for f in sorted(scan_dir.rglob("*")):
        if f.is_file() and f.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            # Extract month and shoot from parent folders
            parts = f.parts
            month = ""
            shoot = ""
            try:
                idx = parts.index("images")
                if len(parts) > idx + 1:
                    month = parts[idx+1]
                if len(parts) > idx + 2:
                    shoot = parts[idx+2]
            except (ValueError, IndexError):
                pass
            
            # Identify ref_code (strip Needs Review- etc)
            name = f.name
            ref_code = name.replace("Needs Review-", "").replace("Art Review-", "")
            ref_code = Path(ref_code).stem
            
            # Sprint ID extraction
            sprint_id = "UNKNOWN"
            sprint_match = re.search(
                r"([a-zA-Z]+-[A-Z]+-\d+-\d+-\d+)", name
            )
            if sprint_match:
                sprint_id = sprint_match.group(1)

            images.append({
                "id": f.stem,
                "ref_code": ref_code,
                "filename": f.name,
                "path": str(f),
                "month": month,
                "shoot": shoot,
                "sprint": sprint_id,
                "status": "pending" if "Needs Review" in f.name else "approved",
                "added_at": datetime.now().isoformat()
            })

    catalog = {
        "generated": datetime.now().isoformat(),
        "images": images,
        "meta": {
            "total": len(images)
        }
    }

    catalog_path = _get_catalog_path()
    catalog_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write — prevents the webapp reading a half-written file
    tmp = catalog_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(catalog, indent=2, ensure_ascii=False))
    tmp.rename(catalog_path)
    return images


_EXTS = {".png", ".jpg", ".jpeg"}


class CatalogSyncWatcher:
    """
    Background thread that keeps catalog.json up-to-date in real time.

    Polls the shoot folder every `interval` seconds. If any image file
    has been added, removed, or renamed since the last check, it calls
    sync_catalog() so the webapp can show the change immediately.

    Usage in main.py:
        watcher = CatalogSyncWatcher()
        watcher.start()
        ...  # image generation + photo editor runs
        watcher.stop()
    """

    def __init__(self, interval: float = 4.0):
        self._interval = interval
        self._stop     = threading.Event()
        self._thread   = None
        self._snapshot: dict = {}   # {str(path): mtime}

    def start(self) -> None:
        self._stop.clear()
        self._snapshot = self._scan()   # baseline before first write
        self._thread   = threading.Thread(
            target=self._run, name="catalog-sync-watcher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)
        # Final sync on exit so the catalog is always current when the
        # main thread moves on (e.g. to CatalogWriterTool).
        try:
            sync_catalog()
        except Exception:
            pass

    # ── Internal ──────────────────────────────────────────────────────────────

    def _run(self) -> None:
        while not self._stop.wait(timeout=self._interval):
            try:
                current = self._scan()
                if current != self._snapshot:
                    self._snapshot = current
                    sync_catalog()
            except Exception:
                pass

    def _scan(self) -> dict:
        """Return {path_str: mtime} for every image in the shoot folder."""
        shoot_folder = os.getenv("SHOOT_FOLDER", "")
        if not shoot_folder:
            return {}
        scan_dir = BASE_DIR / shoot_folder
        if not scan_dir.exists():
            return {}
        result = {}
        for f in scan_dir.rglob("*"):
            if f.is_file() and f.suffix.lower() in _EXTS:
                try:
                    result[str(f)] = f.stat().st_mtime
                except OSError:
                    pass
        return result
