import os
import numpy as np
from pathlib import Path
from datetime import datetime
from crewai.tools import BaseTool
from PIL import Image, ImageFilter

SUPPORTED = {".jpg", ".jpeg", ".png"}


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


def _apply_film_grain(
    img: Image.Image,
    strength: float = 8.0,
) -> Image.Image:
    """
    Apply light film grain.
    Strength 8 = light, takes the digital edge off.
    Grain is luminance-based (not colour noise)
    and slightly larger than digital noise.
    """
    import numpy as np

    arr  = np.array(img, dtype=np.float32)
    h, w = arr.shape[:2]

    # Generate luminance grain
    # Slightly larger grain size = more filmic
    grain = np.random.normal(
        loc=0,
        scale=strength,
        size=(h, w),
    ).astype(np.float32)

    # Apply grain to all channels equally
    # (luminance grain, not colour noise)
    for c in range(arr.shape[2]):
        arr[:, :, c] = np.clip(
            arr[:, :, c] + grain, 0, 255
        )

    return Image.fromarray(arr.astype(np.uint8))


def _process_image(file_path: Path) -> bool:
    """
    Apply light film grain to one image.
    Returns True if successful, False if failed.
    """
    try:
        img = Image.open(file_path).convert("RGB")

        # Step 1 — Film grain only
        img = _apply_film_grain(img, strength=8.0)

        # Save back to same path
        img.save(file_path, quality=95)
        return True

    except Exception as e:
        print(
            f"[FilmProcessor] Error processing "
            f"{file_path.name}: {e}"
        )
        return False


class FilmProcessorTool(BaseTool):
    name: str  = "Film Processor"
    description: str = """
        Applies a light film grain overlay to all
        generated images in the asset library.

        Grain strength 8 — light, takes the digital
        edge off without being obvious.

        Processes only approved images — skips files
        with Needs Review- or Art Review- prefix.
        Overwrites originals in place.

        No input required — call with empty string.

        Output: processing summary with count and
        any errors.
    """

    def _run(self, _: str = "") -> str:
        try:
            asset_dir = _get_asset_dir()

            if not asset_dir.exists():
                return (
                    "TOOL_ERROR: Asset directory not "
                    "found. Run image generation first."
                )

            # Only process approved images.
            # _get_asset_dir() already scopes to the
            # current set's subfolder so no filename
            # filtering is needed.
            files = sorted([
                f for f in asset_dir.iterdir()
                if f.is_file()
                and f.suffix.lower() in SUPPORTED
                and "Needs Review-" not in f.name
                and "Art Review-"   not in f.name
                and "TEST-"         not in f.name
            ])

            if not files:
                return "No approved images found to process."

            total     = len(files)
            succeeded = 0
            failed    = 0
            errors    = []

            print(
                f"\n[FilmProcessor] Processing "
                f"{total} images..."
            )

            for f in files:
                print(
                    f"[FilmProcessor] {f.name}..."
                )
                if _process_image(f):
                    succeeded += 1
                    print(
                        f"[FilmProcessor] ✓ {f.name}"
                    )
                else:
                    failed += 1
                    errors.append(f.name)

            summary = (
                f"FILM PROCESSING COMPLETE\n"
                f"Total processed: {succeeded}/{total}\n"
            )

            if failed:
                summary += (
                    f"Failed: {failed}\n"
                    f"Errors: {', '.join(errors)}\n"
                )
            else:
                summary += "All images processed successfully.\n"

            summary += (
                f"\nProcessing applied:\n"
                f"- Light film grain (strength 8)\n"
            )

            return summary

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
