import json
import os
import re
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
    catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False))
    return images
