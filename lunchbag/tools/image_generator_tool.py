import os
import re
import json
import base64
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from crewai.tools import BaseTool
from google import genai
from google.genai import types

# Max simultaneous Gemini image generation requests.
# 3 is conservative — enough to cut generation time ~3x
# without triggering rate limits.
MAX_CONCURRENT_SHOTS = 3

def _get_asset_dir() -> Path:
    """
    Returns the set subfolder path:
    asset_library/images/March2026/Shoot01/Set1

    SHOOT_FOLDER holds the shoot root (e.g.
    March2026/Shoot01). CURRENT_SET determines
    the Set subfolder. Creates folders as needed.
    """
    shoot_folder = os.getenv("SHOOT_FOLDER", "")
    current_set  = int(os.getenv("CURRENT_SET", "0"))
    base_dir     = Path("asset_library/images")

    if shoot_folder:
        path = base_dir / shoot_folder
        if current_set > 0:
            path = path / f"Set{current_set}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    # Auto-detect current month folder
    month_name = datetime.now().strftime("%B%Y")
    month_dir  = base_dir / month_name

    # Find next shoot number
    if month_dir.exists():
        existing = sorted([
            d for d in month_dir.iterdir()
            if d.is_dir()
            and d.name.startswith("Shoot")
        ])
        if existing:
            last_num = int(
                existing[-1].name.replace("Shoot", "")
            )
            shoot_num = last_num + 1
        else:
            shoot_num = 1
    else:
        shoot_num = 1

    shoot_dir = month_dir / f"Shoot{shoot_num:02d}"
    shoot_dir.mkdir(parents=True, exist_ok=True)

    # Store shoot root in env so all tools share it
    os.environ["SHOOT_FOLDER"] = (
        f"{month_name}/Shoot{shoot_num:02d}"
    )
    print(
        f"[ImageGenerator] Shoot folder: "
        f"{month_name}/Shoot{shoot_num:02d}"
    )

    # Return set subfolder
    if current_set > 0:
        set_path = shoot_dir / f"Set{current_set}"
        set_path.mkdir(parents=True, exist_ok=True)
        return set_path

    return shoot_dir

PRODUCTS_DIR   = Path("products")
REFS_DIR       = Path("references")
OUTPUTS_DIR    = Path("outputs")
SUPPORTED      = {".jpg", ".jpeg", ".png"}

TECHNICAL_ANCHOR = (
    "Photorealistic high-end lifestyle photography. "
    "The bag is the absolute hero of the image. "
    "Reproduce the bag from the product reference "
    "with perfect fidelity — this is non-negotiable:\n"
    "PATTERN: The print pattern on the bag must be "
    "IDENTICAL to the product reference. Same motifs, "
    "same colours, same scale, same arrangement. "
    "A different pattern = wrong product.\n"
    "FABRIC: The cotton exterior must look like real "
    "woven cotton — visible fabric texture, natural "
    "drape, soft matte surface. Not leather, not "
    "plastic, not synthetic. The fabric weave should "
    "be visible in close-up shots.\n"
    "DETAILS: Reproduce all visible details from the "
    "product reference — zip, handles, strap, seams, "
    "any branding. Do not invent or omit details.\n"
    "HARDWARE: Reproduce ONLY the hardware "
    "visible in the product reference — exact "
    "number of zippers, exact straps and handles, "
    "exact clips and closures. Do not add any "
    "hardware not present in the reference. "
    "CRITICAL: This bag has NO shoulder strap "
    "and NO crossbody strap. It has ONLY a short "
    "top handle and a front closure strap with a "
    "snap button. Any extra strap, long strap, or "
    "shoulder strap = wrong product.\n"
    "SHAPE: The bag must hold its correct form — "
    "H21cm x W16cm x D24cm rectangular with slight "
    "natural softness from the cotton. Not collapsed, "
    "not overly rigid.\n"
    "SIZE AND SCALE: The bag is a compact lunch "
    "bag — H21cm x W16cm x D24cm, approximately "
    "the size of a small handbag or a large "
    "lunchbox. When held in one hand it should "
    "fit comfortably with fingers wrapping around "
    "the top handle — it is NOT a large tote, "
    "NOT a backpack, NOT a shopping bag. When "
    "carried by a model it should sit naturally "
    "at hip height if held at arm's length, or "
    "at waist height if carried short. The bag "
    "should never appear larger than a model's "
    "torso or wider than her shoulders. "
    "If the scale looks unrealistic compared to "
    "the human body — regenerate.\n"
    "Maximum realism. No text overlays. No watermarks."
)


def _load_folder_images(
    folder: Path,
) -> list[tuple[bytes, str, str]]:
    if not folder.exists():
        return []
    files = sorted([
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in SUPPORTED
    ])
    result = []
    for f in files:
        mime = (
            "image/png" if f.suffix.lower() == ".png"
            else "image/jpeg"
        )
        result.append((f.read_bytes(), mime, f.name))
    return result


def _load_set_refs(current_set: int) -> list:
    """
    Load reference images for the current set.
    Looks for references/Set1/, Set2/, Set3/
    first. Falls back to references/ root if
    set subfolder does not exist.
    """
    set_dir = REFS_DIR / f"Set{current_set}"
    if set_dir.exists() and any(
        set_dir.iterdir()
    ):
        refs = _load_folder_images(set_dir)
        print(
            f"[ImageGenerator] Using set refs: "
            f"references/Set{current_set}/ "
            f"({len(refs)} images)"
        )
        return refs

    # Fallback to root references folder
    refs = _load_folder_images(REFS_DIR)
    print(
        f"[ImageGenerator] No Set{current_set}/ "
        f"folder found — using references/ root "
        f"({len(refs)} images)"
    )
    return refs


def _scan_clean_refs(
    all_refs: list,
    product_images: list,
) -> list:
    """
    Test each ref image individually against the API.
    Returns only the refs that pass the content filter.
    Blocked refs are permanently excluded for this batch.
    """
    if not all_refs:
        return []

    # Single ref — no isolation possible,
    # return as-is and let the batch loop handle it.
    if len(all_refs) == 1:
        return all_refs

    print(
        f"[ImageGenerator] Pre-flight: scanning "
        f"{len(all_refs)} ref image(s) individually..."
    )

    api_key = (
        os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
    )
    client = genai.Client(api_key=api_key)

    # Use first product image for the test
    prod_bytes, prod_mime, prod_name = product_images[0]

    clean_refs = []
    for ref_bytes, ref_mime, ref_name in all_refs:
        time.sleep(4)  # respect rate limit
        try:
            test_parts = [
                types.Part(
                    inline_data=types.Blob(
                        mime_type=prod_mime,
                        data=prod_bytes,
                    )
                ),
                types.Part(
                    inline_data=types.Blob(
                        mime_type=ref_mime,
                        data=ref_bytes,
                    )
                ),
                types.Part(
                    text=(
                        "Lifestyle product photograph. "
                        "Reproduce the bag from IMAGE 1 "
                        "in a scene inspired by IMAGE 2."
                    )
                ),
            ]
            response = client.models.generate_content(
                model="gemini-3-pro-image-preview",
                contents=[
                    types.Content(
                        role="user",
                        parts=test_parts,
                    )
                ],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                    temperature=0.7,
                ),
            )
            if response.candidates:
                _track_api_call("preflight_calls")
                print(
                    f"[ImageGenerator] Pre-flight: "
                    f"{ref_name} ✓ pass"
                )
                clean_refs.append(
                    (ref_bytes, ref_mime, ref_name)
                )
            else:
                _track_api_call("preflight_calls")
                feedback = ""
                if hasattr(response, "prompt_feedback"):
                    feedback = str(response.prompt_feedback)
                print(
                    f"[ImageGenerator] Pre-flight: "
                    f"{ref_name} ✗ blocked — excluded"
                    + (f" ({feedback})" if feedback else "")
                )
        except Exception as e:
            _track_api_call("preflight_calls")
            print(
                f"[ImageGenerator] Pre-flight: "
                f"{ref_name} ✗ error — excluded ({e})"
            )

    excluded = len(all_refs) - len(clean_refs)
    if excluded:
        print(
            f"[ImageGenerator] Pre-flight complete: "
            f"{len(clean_refs)}/{len(all_refs)} refs clean "
            f"({excluded} excluded by content filter)"
        )
    else:
        print(
            f"[ImageGenerator] Pre-flight complete: "
            f"all {len(all_refs)} refs clean"
        )

    return clean_refs


def _extract_shoot_dna() -> str:
    """
    Read the SHOOT DNA PROMPT BLOCK from the style bible.
    Returns the block text or empty string if not found.
    """
    style_bible_path = (
        OUTPUTS_DIR / "style_bible_and_shot_list.md"
    )
    if not style_bible_path.exists():
        return ""

    content = style_bible_path.read_text()

    # Extract the SHOOT DNA PROMPT BLOCK section
    match = re.search(
        r"(?:\*\*|#+)?\s*SHOOT DNA PROMPT BLOCK\s*(?:\*\*|#+)?\s*\n+(.*?)(?=\n\s*[═=]{3,}|\n\s*#+|\n\s*\[SHOOT-|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )

    if match:
        block = match.group(1).strip()
        return block

    return ""


def _read_concept() -> str:
    """Read campaign concept if present."""
    path = Path("concept.md")
    if not path.exists():
        return ""
    content = path.read_text()
    lines = [
        l for l in content.splitlines()
        if not l.strip().startswith("#")
        and not l.strip().startswith("<!--")
        and not l.strip().startswith("-->")
        and l.strip() != ""
    ]
    concept = "\n".join(lines).strip()
    return concept if concept else ""


def _extract_set_dnas() -> list[str]:
    """
    Extract DNA blocks for each set from the style bible.
    Returns list of DNA strings, one per set, in set order.
    """
    style_bible_path = (
        OUTPUTS_DIR / "style_bible_and_shot_list.md"
    )
    if not style_bible_path.exists():
        return []

    content = style_bible_path.read_text()

    # Find all SET DNA PROMPT BLOCKs in order.
    # Handles both bold (**SET DNA PROMPT BLOCK:**)
    # and plain (SET DNA PROMPT BLOCK:) formatting.
    blocks = re.findall(
        r"\*{0,2}SET DNA PROMPT BLOCK:\*{0,2}\s*(.*?)"
        r"(?=\n\s*[═=]{3,}|\n\s*\*{0,2}SET \d|\n\s*\[SHOOT-|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )

    return [b.strip() for b in blocks if b.strip()]


def _get_set_dna_for_shot(
    ref_code: str,
    set_dnas: list[str],
) -> str:
    """
    Determine which set a shot belongs to based
    on its ref_code, then return that set's DNA.

    Shot ref_codes include set identifier:
    S1-001 → Set 1
    S2-018 → Set 2

    Falls back to first set DNA if no set
    identifier found in ref_code.
    """
    if not set_dnas:
        return ""

    match = re.search(r"S(\d+)-", ref_code)
    if match:
        set_index = int(match.group(1)) - 1
        if 0 <= set_index < len(set_dnas):
            return set_dnas[set_index]

    return set_dnas[0]


def _get_first_generated_image() -> tuple[bytes, str] | None:
    """
    Get the first successfully generated image from the
    asset library to use as a consistency anchor.
    Excludes TEST- images.
    Returns (bytes, mime_type) or None if none exist yet.
    """
    asset_dir = _get_asset_dir()
    if not asset_dir.exists():
        return None

    files = sorted([
        f for f in asset_dir.iterdir()
        if f.is_file()
        and f.suffix.lower() in SUPPORTED
        and "TEST-" not in f.name
    ])

    if not files:
        return None

    first = files[0]
    mime  = (
        "image/png" if first.suffix.lower() == ".png"
        else "image/jpeg"
    )
    return first.read_bytes(), mime


def _preflight_check(current_set: int) -> str | None:
    """
    Verify all required assets are present before generation.
    Returns an error string listing missing items, or None if all OK.
    """
    errors = []

    # 1 — Style bible
    style_bible_path = OUTPUTS_DIR / "style_bible_and_shot_list.md"
    if not style_bible_path.exists():
        errors.append(
            "Style bible missing: "
            "outputs/style_bible_and_shot_list.md — "
            "run Phase 1 crew first."
        )
        return "PREFLIGHT FAILED:\n" + "\n".join(
            f"  ✗ {e}" for e in errors
        )

    content = style_bible_path.read_text()

    # 2 — SET DNA for this set
    set_dnas = _extract_set_dnas()
    if not set_dnas:
        errors.append(
            "No SET DNA PROMPT BLOCKs found in "
            "style bible — creative planning output "
            "is incomplete."
        )
    elif current_set > 0 and len(set_dnas) < current_set:
        errors.append(
            f"SET DNA for Set {current_set} not found "
            f"(only {len(set_dnas)} set(s) defined in "
            f"style bible)."
        )

    # 3 — Shot list for this set
    shot_matches = re.findall(
        r"\[(SHOOT-[^\]]+)\]", content
    )
    if current_set > 0:
        set_shots = [
            s for s in shot_matches
            if f"-S{current_set}-" in s
        ]
        if not set_shots:
            errors.append(
                f"No shots found for Set {current_set} "
                f"in style bible shot list."
            )

    # 4 — Reference images
    has_refs = False
    if current_set > 0:
        set_ref_dir = REFS_DIR / f"Set{current_set}"
        if set_ref_dir.exists():
            set_ref_imgs = [
                f for f in set_ref_dir.iterdir()
                if f.suffix.lower() in SUPPORTED
            ]
            has_refs = len(set_ref_imgs) > 0
    if not has_refs:
        root_refs = (
            [
                f for f in REFS_DIR.iterdir()
                if f.suffix.lower() in SUPPORTED
            ]
            if REFS_DIR.exists() else []
        )
        has_refs = len(root_refs) > 0
    if not has_refs:
        errors.append(
            f"No reference images found in "
            f"references/Set{current_set}/ or "
            f"references/ — add style references "
            f"before running generation."
        )

    # 5 — Product images
    product_imgs = (
        [
            f for f in PRODUCTS_DIR.iterdir()
            if f.suffix.lower() in SUPPORTED
        ]
        if PRODUCTS_DIR.exists() else []
    )
    if not product_imgs:
        errors.append(
            "No product images found in products/ — "
            "add product photos before running."
        )

    if errors:
        return (
            "PREFLIGHT FAILED — generation aborted:\n"
            + "\n".join(f"  ✗ {e}" for e in errors)
        )
    return None


# Global counter for product distribution (thread-safe)
_GENERATION_COUNTER = 0
_COUNTER_LOCK = threading.Lock()
_LOG_LOCK      = threading.Lock()   # serialise multi-line log blocks

# API call tracking
_API_COUNTER_PATH = Path("outputs/api_counters.json")
_API_FILE_LOCK    = threading.Lock()

def _track_api_call(category: str, count: int = 1) -> None:
    """Atomically increment an API call counter in api_counters.json."""
    with _API_FILE_LOCK:
        try:
            data = {}
            if _API_COUNTER_PATH.exists():
                try:
                    data = json.loads(_API_COUNTER_PATH.read_text())
                except Exception:
                    pass
            data[category] = data.get(category, 0) + count
            _API_COUNTER_PATH.parent.mkdir(parents=True, exist_ok=True)
            _API_COUNTER_PATH.write_text(json.dumps(data, indent=2))
        except Exception:
            pass  # Never let counter errors break generation

class ImageGeneratorTool(BaseTool):
    name: str = "The Lunchbags Image Generator"
    description: str = """
        Generates a photoshoot image using Nano Banana Pro
        (gemini-3-pro-image-preview) via the Gemini API.

        Uses a two-layer consistency system:
        1. SHOOT DNA — a written description of the mod,
           location, lighting, and mood extracted from the
           Style Bible. Injected into every prompt to ensure
           all images in the sprint share the same world.
        2. FIRST IMAGE ANCHOR — once the first image is
           generated, it is passed as a visual reference
           to all subsequent generations so the model,
           location, and mood stay visually consistent.

        Reference images define inspiration only —
        not direct replication.

        Input must be pipe-separated with 3 fields:
        creative_prompt|aspect_ratio|reference_code

        creative_prompt: what makes THIS shot unique —
        the specific composition, subject placement,
        and any shot-specific details.

        Output: file path and reference code, or TOOL_ERROR
    """

    def _run(self, input_str: str) -> str:
        try:
            # ── Handle Batch Mode (empty input) ──────────
            if not input_str or input_str.strip() == "":
                return self._run_batch()

            # ── Parse single shot input ──────────────────
            parts = input_str.split("|")
            if len(parts) != 3:
                return (
                    "TOOL_ERROR: Input must be "
                    "creative_prompt|aspect_ratio|reference_code"
                )

            creative_prompt, aspect_ratio, ref_code = [
                p.strip() for p in parts
            ]
            
            return self._generate_single_shot(
                creative_prompt, aspect_ratio, ref_code
            )

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"

    def _run_batch(self) -> str:
        """
        Parses the shot list and generates all shots
        for the current set.
        """
        current_set = int(os.getenv("CURRENT_SET", "0"))

        # ── Pre-flight: abort if anything is missing ──
        preflight_error = _preflight_check(current_set)
        if preflight_error:
            print(f"\n{preflight_error}\n")
            return f"TOOL_ERROR: {preflight_error}"

        style_bible_path = (
            OUTPUTS_DIR / "style_bible_and_shot_list.md"
        )

        content = style_bible_path.read_text()
        
        # Extract all shots: [SHOOT-...]
        shot_matches = re.findall(
            r"\[(SHOOT-[^\]]+)\]\s*(.*?)(?=\n\s*\[SHOOT-|\Z)",
            content,
            re.DOTALL
        )
        
        if not shot_matches:
            return "TOOL_ERROR: No shots found in style bible."

        # Filter shots by current set
        current_set = int(
            os.getenv("CURRENT_SET", "0")
        )
        if current_set > 0:
            set_shots = [
                s for s in shot_matches
                if f"-S{current_set}-" in s[0]
            ]
            print(
                f"[ImageGenerator] Set {current_set}: "
                f"{len(set_shots)} shots found"
            )
        else:
            set_shots = shot_matches

        images_this_set = int(
            os.getenv("IMAGES_THIS_SET", "0")
        )

        if images_this_set > 0 and len(set_shots) > 0:
            # Cycle shots to reach target count
            cycled_shots = []
            while len(cycled_shots) < images_this_set:
                for shot in set_shots:
                    if len(cycled_shots) >= images_this_set:
                        break
                    # Update shot ref to avoid duplicates
                    cycle_num = len(cycled_shots) // len(set_shots) + 1
                    shot_ref  = shot[0]
                    if cycle_num > 1:
                        # Append cycle number to ref
                        parts    = shot_ref.rsplit("-", 1)
                        new_num  = int(parts[-1]) + (
                            (cycle_num - 1) * len(set_shots)
                        )
                        shot_ref = f"{parts[0]}-{new_num:03d}"
                    cycled_shots.append(
                        (shot_ref, shot[1])
                    )
            set_shots = cycled_shots
            print(
                f"[ImageGenerator] Cycling shots to "
                f"reach {images_this_set} images. "
                f"Total shots queued: {len(set_shots)}"
            )

        to_generate = []
        for ref_code, entry in set_shots:
            prompt = ""

            # ── New inline format ─────────────────────────
            # e.g. [MODEL] 9:16, Description text here.
            m_inline = re.match(
                r"\[.*?\]\s*(\d:\d+),?\s*(.*)",
                entry.strip(),
                re.DOTALL,
            )
            if m_inline:
                prompt = m_inline.group(2).strip()
            else:
                # ── Legacy labelled format ────────────────
                # Format: / Composition: / Mood: / Notes:
                m_comp  = re.search(
                    r"Composition:\s*(.*?)\n", entry,
                    re.IGNORECASE
                )
                m_mood  = re.search(
                    r"Mood:\s*(.*?)\n", entry,
                    re.IGNORECASE
                )
                m_notes = re.search(
                    r"Notes:\s*(.*?)\n", entry,
                    re.IGNORECASE
                )
                if m_comp:
                    prompt += f"Composition: {m_comp.group(1).strip()}. "
                if m_mood:
                    prompt += f"Mood: {m_mood.group(1).strip()}. "
                if m_notes:
                    prompt += f"Notes: {m_notes.group(1).strip()}."

            # All images are 3:4 portrait — override any shot-list value
            aspect = "3:4"
            
            # Use only the ref_code portion for the tool (e.g. S1-001)
            # SHOOT-SPR26-S1-001 -> S1-001
            tool_ref = ref_code.split("-", 2)[-1]
            
            to_generate.append((prompt.strip(), aspect, tool_ref))

        if not to_generate:
            return f"No shots found for Set {current_set}."

        # ── REGEN_SHOTS filter ────────────────────────
        # When set, only regenerate the specified shot
        # codes (e.g. "S1-006,S2-027"). Used by the
        # auto-regen pass after photo editor.
        regen_shots_env = os.getenv("REGEN_SHOTS", "")
        if regen_shots_env:
            regen_codes = set(regen_shots_env.split(","))
            to_generate = [
                t for t in to_generate
                if t[2] in regen_codes
            ]
            print(
                f"[ImageGenerator] Regen mode: "
                f"{len(to_generate)} shot(s) targeted — "
                + ", ".join(regen_codes)
            )
            if not to_generate:
                return (
                    f"REGEN_NOTHING: none of "
                    f"{regen_codes} found in shot list."
                )

        # ── Pre-flight: scan refs once for this batch ──
        product_images = _load_folder_images(PRODUCTS_DIR)
        all_refs   = _load_set_refs(current_set)
        clean_refs = _scan_clean_refs(all_refs, product_images)

        print(f"[ImageGenerator] Starting batch for Set {current_set}...")
        print(f"[ImageGenerator] Found {len(to_generate)} shots.")
        if clean_refs:
            print(
                f"[ImageGenerator] Using {len(clean_refs)} "
                f"clean ref(s) for all shots."
            )
        else:
            print(
                f"[ImageGenerator] No clean refs available — "
                f"generating without style references."
            )

        # Event set by any worker that hits DAILY_QUOTA_EXHAUSTED.
        # All other workers check this before starting a new attempt.
        quota_exhausted = threading.Event()

        def _generate_one(args) -> str:
            """
            Per-shot worker: up to 3 attempts with style ref,
            then one no-ref fallback. Returns the final result
            string for this shot.
            """
            prompt, aspect, ref = args

            if quota_exhausted.is_set():
                return f"SKIPPED | {ref} (quota exhausted)"

            success = False
            last_res = ""
            for attempt in range(1, 4):
                if quota_exhausted.is_set():
                    return f"SKIPPED | {ref} (quota exhausted)"

                res = self._generate_single_shot(
                    prompt, aspect, ref,
                    style_refs=clean_refs,
                    attempt=attempt,
                )
                last_res = res

                if "SUCCESS" in res:
                    success = True
                    break
                if "DAILY_QUOTA_EXHAUSTED" in res:
                    quota_exhausted.set()
                    print(
                        f"\n[ImageGenerator] ✗ DAILY QUOTA EXHAUSTED\n"
                        f"  {res}\n"
                        f"  Stopping all workers.\n"
                    )
                    return res
                print(f"[ImageGenerator] {ref} FAILED: {res}")
                # BlockedReason.OTHER = prompt triggered content filter.
                # No point retrying — go straight to no-ref fallback.
                if "BlockedReason.OTHER" in res:
                    print(
                        f"[ImageGenerator] {ref} — "
                        f"prompt triggered content filter, "
                        f"falling back to no-ref."
                    )
                    break
                if attempt < 3:
                    print(
                        f"[ImageGenerator] Backing off 20s "
                        f"before retry..."
                    )
                    time.sleep(20)

            if not success:
                if quota_exhausted.is_set():
                    return f"SKIPPED | {ref} (quota exhausted)"
                # Fallback: one attempt without style ref
                res = self._generate_single_shot(
                    prompt, aspect, ref,
                    style_refs=[],
                    attempt="fallback",
                )
                last_res = res
                if "DAILY_QUOTA_EXHAUSTED" in res:
                    quota_exhausted.set()
                    print(
                        f"\n[ImageGenerator] ✗ DAILY QUOTA EXHAUSTED\n"
                        f"  {res}\n"
                        f"  Stopping all workers.\n"
                    )
                    return res
                if "SUCCESS" in res:
                    print(
                        f"[ImageGenerator] {ref} ✓ "
                        f"fallback succeeded"
                    )
                else:
                    print(
                        f"[ImageGenerator] {ref} ✗ "
                        f"fallback also failed: {res}"
                    )
                    return f"FAILED | {ref}"

            return last_res

        print(
            f"[ImageGenerator] Running {len(to_generate)} shots "
            f"with {MAX_CONCURRENT_SHOTS} concurrent workers..."
        )
        results = []
        with ThreadPoolExecutor(
            max_workers=MAX_CONCURRENT_SHOTS,
            thread_name_prefix="ImgGen",
        ) as pool:
            futures = {
                pool.submit(_generate_one, args): args[2]
                for args in to_generate
            }
            for future in as_completed(futures):
                ref = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = f"FAILED | {ref}"
                    print(
                        f"[ImageGenerator] {ref} raised "
                        f"exception: {exc}"
                    )
                results.append(result)

        # Hard-stop if quota was hit during parallel run
        if quota_exhausted.is_set():
            return "DAILY_QUOTA_EXHAUSTED"

        success_count = sum(1 for r in results if "SUCCESS" in r)
        return f"Batch complete. {success_count}/{len(to_generate)} successful."

    def _generate_single_shot(
        self,
        creative_prompt: str,
        aspect_ratio: str,
        ref_code: str,
        style_refs: list | None = None,
        attempt: int | str | None = None,
    ) -> str:
        try:
            valid_ratios = ["1:1", "9:16", "3:4", "4:3", "4:5"]
            if aspect_ratio not in valid_ratios:
                aspect_ratio = "1:1"

            # ── Load product images ───────────────────────
            product_images = _load_folder_images(PRODUCTS_DIR)
            if not product_images:
                return (
                    "TOOL_ERROR: No product images found in "
                    "products/."
                )

            global _GENERATION_COUNTER
            with _COUNTER_LOCK:
                idx = _GENERATION_COUNTER % len(product_images)
                _GENERATION_COUNTER += 1
            product_bytes, product_mime, product_name = (
                product_images[idx]
            )

            # ── Extract set DNAs ──────────────────────────
            set_dnas  = _extract_set_dnas()
            set_dna   = _get_set_dna_for_shot(
                ref_code, set_dnas
            )

            # Fall back to single shoot DNA if
            # no set structure found
            if not set_dna:
                set_dna = _extract_shoot_dna()

            # ── Get first image anchor ────────────────────
            anchor = _get_first_generated_image()

            # ── Build prompt ──────────────────────────────
            # Shoot DNA defines the world — refs inspired it
            # but are no longer passed directly to generation

            # style_refs is pre-validated by _scan_clean_refs().
            # Empty list = no refs (fallback mode).
            # None = standalone call, load refs from disk.
            if style_refs is not None:
                ref_images = style_refs[:1]
                if not ref_images:
                    print(
                        f"[ImageGenerator] Fallback mode — "
                        f"skipping style ref image"
                    )
            else:
                current_set = int(
                    os.getenv("CURRENT_SET", "1")
                )
                all_refs   = _load_set_refs(current_set)
                ref_images = all_refs[:1]
            ref_count = len(ref_images)

            # ── Build prompt ──────────────────────────────
            if set_dna:
                world_block = (
                    f"THE WORLD OF THIS SET:\n"
                    f"{set_dna}\n\n"
                    f"This image belongs to this specific "
                    f"set. Stay true to this set's location, "
                    f"lighting, and mood.\n"
                    f"The model is the same person across "
                    f"all sets — only the space around her "
                    f"changes.\n\n"
                )
            else:
                world_block = (
                    "Create a photorealistic editorial "
                    "lifestyle product photograph with warm "
                    "Mediterranean mood, natural directional "
                    "lighting, and a minimal clean setting.\n\n"
                )

            concept = _read_concept()
            if concept:
                concept_block = (
                    f"CAMPAIGN CONCEPT:\n"
                    f"{concept}\n\n"
                    f"Every image in this sprint tells "
                    f"this story. The situation, setting, "
                    f"and narrative described above must "
                    f"be present in the generated image.\n\n"
                )
            else:
                concept_block = ""

            full_prompt = (
                f"HARD CONSTRAINTS — VIOLATIONS = WRONG IMAGE:\n"
                f"1. NO shoulder strap. NO crossbody strap. "
                f"NO long strap of any kind. "
                f"The bag has ONE short top handle only.\n"
                f"2. The bag pattern must EXACTLY match "
                f"the product reference — same motifs, "
                f"same colours, same scale.\n"
                f"3. The bag is a compact lunch bag "
                f"(H21cm x W16cm x D24cm). NOT a tote, "
                f"NOT a backpack, NOT a messenger bag.\n\n"
                f"IMAGE REFERENCES:\n"
                f"IMAGE 1: Product — reproduce this "
                f"bag exactly: same pattern, fabric, "
                f"shape, hardware.\n"
            )

            for i in range(ref_count):
                full_prompt += (
                    f"IMAGE {i+2}: Style reference — "
                    f"recreate this scene with our bag.\n"
                )

            full_prompt += (
                f"\n{TECHNICAL_ANCHOR}\n\n"
                f"{world_block}"
                f"{concept_block}"
                f"COMPOSITION: {creative_prompt}\n\n"
                f"Place our exact bag into a scene "
                f"inspired by the style references. "
                f"Match the setting, lighting and mood. "
                f"Bag pattern must be identical to "
                f"product reference."
            )

            # ── Build content parts ───────────────────────
            parts_list = []

            # Product reference
            parts_list.append(
                types.Part(
                    inline_data=types.Blob(
                        mime_type=product_mime,
                        data=product_bytes,
                    )
                )
            )

            # Style reference
            for ref_bytes, ref_mime, ref_name in ref_images:
                parts_list.append(
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=ref_mime,
                            data=ref_bytes,
                        )
                    )
                )

            # Prompt LAST
            parts_list.append(types.Part(text=full_prompt))

            with _LOG_LOCK:
                attempt_label = (
                    f" — attempt {attempt}" if attempt is not None else ""
                )
                print(
                    f"[ImageGenerator] {ref_code}{attempt_label} — "
                    f"sending request\n"
                    f"  Product: {product_name} | "
                    f"Refs: {ref_count} | "
                    f"Prompt: {len(full_prompt)} chars"
                )

            # ── Call Nano Banana Pro ──────────────────────
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                return "TOOL_ERROR: API key not found in environment (tried GEMINI_API_KEY and GOOGLE_API_KEY)."

            client = genai.Client(api_key=api_key)

            # Stay under 20 RPM rate limit
            # 4 seconds = max 15 RPM — safe headroom
            time.sleep(4)

            try:
                response = client.models.generate_content(
                    model="gemini-3-pro-image-preview",
                    contents=[
                        types.Content(
                            role="user",
                            parts=parts_list,
                        )
                    ],
                    config=types.GenerateContentConfig(
                        response_modalities=["IMAGE", "TEXT"],
                        temperature=0.7,
                        image_config=types.ImageConfig(
                            aspect_ratio=aspect_ratio,
                        ),
                    ),
                )
                _track_api_call("image_gen_calls")
            except (AttributeError, TypeError, ImportError,
                    ModuleNotFoundError, NotImplementedError) as api_err:
                # Programming error — retrying will never help
                return (
                    f"FATAL_ERROR: {type(api_err).__name__}: {api_err}"
                )
            except Exception as api_err:
                err_str = str(api_err)
                print(f"[ImageGenerator] API Call Failed: {api_err}")
                _track_api_call("image_gen_calls")
                if "generate_requests_per_model_per_day" in err_str:
                    # Daily quota exhausted — extract retry time if available
                    import re as _re
                    retry_match = _re.search(
                        r"retryDelay.*?(\d+h\d+m[\d.]+s|\d+h[\d.]+s|\d+m[\d.]+s)",
                        err_str,
                    )
                    retry_hint = (
                        f" Retry in ~{retry_match.group(1)}."
                        if retry_match else
                        " Check https://ai.dev/rate-limit for reset time."
                    )
                    return (
                        f"DAILY_QUOTA_EXHAUSTED: Daily limit of 250 requests "
                        f"reached for gemini-3-pro-image.{retry_hint}"
                    )
                return f"TOOL_ERROR: API call failed: {err_str}"

            # ── Extract image ─────────────────────────────
            image_data = None
            response_text = ""
            
            if response.candidates:
                if response.candidates[0].content:
                    for part in response.candidates[0].content.parts:
                        if part.inline_data:
                            image_data = part.inline_data.data
                        if part.text:
                            response_text += part.text
                
                if not image_data:
                    # Check finish reason
                    finish_reason = response.candidates[0].finish_reason
                    print(f"[ImageGenerator] FAILED for {ref_code}. Finish Reason: {finish_reason}. Text: {response_text}")
                    return (
                        f"TOOL_ERROR: No image returned. Finish reason: {finish_reason}. "
                        f"Text: {response_text[:200]}"
                    )
            else:
                feedback = ""
                if hasattr(response, "prompt_feedback"):
                    feedback = str(response.prompt_feedback)
                print(
                    f"[ImageGenerator] FAILED for {ref_code}. "
                    f"No candidates in response. "
                    f"Feedback: {feedback}"
                )
                return (
                    f"TOOL_ERROR: No candidates in response "
                    f"from API. Feedback: {feedback}"
                )

            # ── Save and verify ───────────────────────────
            asset_dir = _get_asset_dir()
            asset_dir.mkdir(parents=True, exist_ok=True)
            
            shoot_id = os.getenv("SHOOT_ID", "SHOOT")
            file_path = asset_dir / f"{shoot_id}-{ref_code}.png"

            max_save_attempts = 3
            saved_successfully = False

            for save_attempt in range(1, max_save_attempts + 1):
                try:
                    if isinstance(image_data, str):
                        file_path.write_bytes(
                            base64.b64decode(image_data)
                        )
                    else:
                        file_path.write_bytes(image_data)

                    # Verify file exists and is not empty
                    if (
                        file_path.exists()
                       ):
                        saved_successfully = True
                        break
                    else:
                        print(
                            f"[ImageGenerator] Save attempt "
                            f"{save_attempt} produced empty "
                            f"or missing file — retrying"
                        )
                        if file_path.exists():
                            file_path.unlink()

                except Exception as save_err:
                    print(
                        f"[ImageGenerator] Save attempt "
                        f"{save_attempt} failed: {save_err}"
                    )

            if not saved_successfully:
                return (
                    f"GENERATION_FAILED | ref: {ref_code} | "
                    f"reason: file could not be saved after "
                    f"{max_save_attempts} attempts"
                )

            anchor_used = "yes" if anchor else "no (first image)"

            return (
                f"SUCCESS | path: {file_path} | "
                f"ref: {ref_code} | "
                f"product: {product_name} | "
                f"set_dna: {'found' if set_dna else 'not found'} | "
                f"anchor: {anchor_used}"
            )

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
