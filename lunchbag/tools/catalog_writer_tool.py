import os
import json
import re
from pathlib import Path
from datetime import datetime
from crewai.tools import BaseTool

def _get_asset_dir() -> Path:
    shoot_folder = os.getenv("SHOOT_FOLDER", "")
    current_set  = int(os.getenv("CURRENT_SET", "0"))
    base_dir     = Path("asset_library/images")
    if shoot_folder:
        path = base_dir / shoot_folder
        if current_set > 0:
            path = path / f"Set{current_set}"
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
SUPPORTED   = {".jpg", ".jpeg", ".png"}


def _get_catalog_path() -> Path:
    shoot_folder = os.getenv("SHOOT_FOLDER", "")
    if shoot_folder:
        return (
            Path("asset_library/images")
            / shoot_folder
            / "catalog.json"
        )
    return Path("asset_library/catalog.json")


def _parse_photo_editor_report() -> dict:
    report_path = OUTPUTS_DIR / "photo_editor_latest.md"
    if not report_path.exists():
        return {}
    content  = report_path.read_text()
    statuses = {}
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        # Match lines like: ✓ PASS | SHOOT-SPR26-001.png
        match = re.match(
            r"[✓✗]\s+(PASS|FIXED|FLAGGED(?:_BATCH)?)"
            r"\s+\|\s+(.+?)(?:\s+\||$)",
            line,
        )
        if match:
            raw    = match.group(1).upper()
            fname  = match.group(2).strip()
            status = (
                "passed" if raw == "PASS"
                else "fixed" if raw == "FIXED"
                else "flagged"
            )
            statuses[fname] = status
    return statuses


def _load_existing_catalog() -> dict:
    catalog_path = _get_catalog_path()
    if catalog_path.exists():
        try:
            return json.loads(catalog_path.read_text())
        except Exception:
            pass
    return {
        "meta": {
            "last_updated": "",
            "total_images":  0,
            "sprints":       [],
        },
        "images": [],
    }


class CatalogWriterTool(BaseTool):
    name: str        = "The Lunchbags Catalog Writer"
    description: str = """
        Writes a JSON catalog of all approved images
        after the Photo Editor review completes.
        Skips any file with Needs Review- or Art Review-
        prefix. Merges with existing catalog across
        sprints. No input required — call with empty string.
    """

    def _run(self, _: str = "") -> str:
        try:
            statuses = _parse_photo_editor_report()
            catalog  = _load_existing_catalog()
            
            # Find all images currently in asset library
            current_files = [
                f for f in _get_asset_dir().iterdir()
                if f.is_file()
                and f.suffix.lower() in SUPPORTED
                and "TEST-" not in f.name
            ]

            new_images = []
            # Deduplicate on path (includes shoot folder),
            # not on id (filename stem which repeats across shoots).
            seen_paths = {img["path"] for img in catalog["images"]}

            for f in current_files:
                # Skip flagged files
                if "Needs Review-" in f.name or "Art Review-" in f.name:
                    continue

                if str(f) in seen_paths:
                    continue

                # Extract ID (e.g. lunchbag-SPRING-26-03-20-S1-001)
                img_id = f.stem
                
                status = statuses.get(f.name, "unknown")
                
                # Sprint ID extraction from new format
                sprint_id = "UNKNOWN"
                # Match lunchbag-SPRING-26-03-20
                match = re.search(
                    r"([a-zA-Z]+-[A-Z]+-\d+-\d+-\d+)",
                    f.name,
                )
                if match:
                    sprint_id = match.group(1)

                # Metadata
                new_images.append({
                    "id":         img_id,
                    "filename":   f.name,
                    "path":       str(f),
                    "status":     status,
                    "added_at":   datetime.now().isoformat(),
                    "sprint":     sprint_id
                })

            catalog["images"].extend(new_images)
            
            # Update meta
            meta = catalog.get("meta", {})
            meta["last_updated"] = datetime.now().isoformat()
            meta["total_images"]  = len(catalog["images"])
            
            sprints = {img["sprint"] for img in catalog["images"]}
            meta["sprints"] = sorted(list(sprints))
            
            catalog["meta"] = meta

            catalog_path = _get_catalog_path()
            catalog_path.parent.mkdir(parents=True, exist_ok=True)
            catalog_path.write_text(json.dumps(catalog, indent=2))

            return (
                f"SUCCESS | Catalog updated at {catalog_path} | "
                f"Total images: {len(catalog['images'])} | "
                f"Added this run: {len(new_images)}"
            )

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
