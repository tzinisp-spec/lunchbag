import os
import sys
import re
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from lunchbag.tools.image_generator_tool import ImageGeneratorTool
from lunchbag.tools.film_processor_tool import FilmProcessorTool
from lunchbag.tools.photo_editor_tool import PhotoEditorTool
from lunchbag.tools.catalog_writer_tool import CatalogWriterTool

def get_next_set_number() -> int:
    asset_dir    = Path("asset_library/images")
    shoot_folder = os.getenv("SHOOT_FOLDER", "")

    if shoot_folder:
        folder = asset_dir / shoot_folder
    else:
        folders = []
        for month_dir in asset_dir.iterdir():
            if not month_dir.is_dir():
                continue
            for shoot_dir in month_dir.iterdir():
                if (shoot_dir.is_dir()
                        and shoot_dir.name.startswith(
                            "Shoot"
                        )):
                    folders.append(shoot_dir)
        folder = (
            sorted(folders)[-1]
            if folders else asset_dir
        )

    if not folder.exists():
        return 1

    # Find which sets are already complete
    # A set is complete if it has at least
    # one approved image (not Needs Review-)
    complete_sets = set()
    for f in folder.glob("*.png"):
        if "Needs Review-" in f.name:
            continue
        if "Art Review-" in f.name:
            continue
        m = re.search(r"-S(\d+)-", f.name)
        if m:
            complete_sets.add(int(m.group(1)))

    if not complete_sets:
        return 1

    # Return next set after highest complete set
    return max(complete_sets) + 1


def get_style_bible_set_count() -> int:
    return 3


def get_images_per_set(
    total: int,
    sets: int,
    set_num: int
) -> int:
    # Always 3 sets: 17, 17, 16
    distribution = {1: 17, 2: 17, 3: 16}
    if sets == 3:
        return distribution.get(set_num, 17)
    # Fallback for other set counts
    base      = total // sets
    remainder = total % sets
    if set_num == sets:
        return base + remainder
    return base


set_num        = get_next_set_number()
total_sets     = get_style_bible_set_count()

import importlib.util
spec = importlib.util.spec_from_file_location(
    "main", "main.py"
)
main_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(main_module)
INPUTS = main_module.INPUTS
total_images = int(
    INPUTS.get("images_per_sprint", "50")
)
images_this_set = get_images_per_set(
    total_images, total_sets, set_num
)
os.environ["IMAGES_THIS_SET"] = str(
    images_this_set
)

shoot_folder   = os.getenv("SHOOT_FOLDER", "")

print("\n" + "="*60)
print(f"  THE LUNCHBAGS — PHASE 1b")
print(f"  Generating Set {set_num} of {total_sets}")
print(
    f"[Phase 1b] Target: {images_this_set} "
    f"images for Set {set_num}"
)
print("="*60 + "\n")

if set_num > total_sets:
    print(
        f"All {total_sets} sets already generated."
        f" Run main_phase2.py when ready."
    )
    sys.exit(0)

os.environ["CURRENT_SET"] = str(set_num)

print(f"[Phase 1b] Generating Set {set_num}...")
result = ImageGeneratorTool()._run("")
print(result)

print(f"[Phase 1b] Film processing...")
result = FilmProcessorTool()._run("")
print(result)

print(f"[Phase 1b] Photo Editor review...")
result = PhotoEditorTool()._run("")
print(result)

print(f"[Phase 1b] Updating catalog...")
result = CatalogWriterTool()._run("")
print(result)

print("\n" + "="*60)
if set_num < total_sets:
    print(
        f"  SET {set_num} COMPLETE"
    )
    print(
        f"  Run main_phase1b.py again for "
        f"Set {set_num + 1}"
    )
else:
    print(f"  ALL {total_sets} SETS COMPLETE")
    print(f"  Run main_phase2.py when ready")
print("="*60 + "\n")
