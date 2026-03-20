import os
import json
import re
from pathlib import Path
from datetime import datetime
from crewai.tools import BaseTool

def _get_asset_dir() -> Path:
    shoot_folder = os.getenv("SHOOT_FOLDER", "")
    if shoot_folder:
        return Path(
            f"asset_library/images/{shoot_folder}"
        )
    return Path("asset_library/images")

OUTPUTS_DIR  = Path("outputs")
CATALOG_PATH = Path("asset_library/catalog.json")
SUPPORTED    = {".jpg", ".jpeg", ".png"}


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
    if CATALOG_PATH.exists():
        try:
            return json.loads(CATALOG_PATH.read_text())
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
            seen_ids = {img["id"] for img in catalog["images"]}

            for f in current_files:
                # Skip flagged files
                if "Needs Review-" in f.name or "Art Review-" in f.name:
                    continue
                
                # Extract ID (e.g. lunchbag-SPRING-26-03-20-S1-001)
                img_id = f.stem
                if img_id in seen_ids:
                    continue
                
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
            catalog["meta"]["last_updated"] = datetime.now().isoformat()
            catalog["meta"]["total_images"]  = len(catalog["images"])
            
            sprints = {img["sprint"] for img in catalog["images"]}
            catalog["meta"]["sprints"] = sorted(list(sprints))

            CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
            CATALOG_PATH.write_text(json.dumps(catalog, indent=2))

            return (
                f"SUCCESS | Catalog updated at {CATALOG_PATH} | "
                f"Total images: {len(catalog['images'])} | "
                f"Added this run: {len(new_images)}"
            )

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
