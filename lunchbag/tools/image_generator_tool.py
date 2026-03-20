import os
import re
import base64
import time
from pathlib import Path
from crewai.tools import BaseTool
from google import genai
from google.genai import types

def _get_asset_dir() -> Path:
    """
    Returns the shoot-specific asset directory.
    Reads shoot_folder from environment or
    falls back to 'images' root.
    """
    shoot_folder = os.getenv("SHOOT_FOLDER", "")
    if shoot_folder:
        return Path(
            f"asset_library/images/{shoot_folder}"
        )
    return Path("asset_library/images")

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
    "HARDWARE: Reproduce only the hardware "
    "visible in the product reference — exact "
    "number of zippers, exact straps and handles, "
    "exact clips and closures. Do not add any "
    "hardware not present in the reference. "
    "A bag with an extra zipper or extra "
    "is the wrong product.\n"
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

    # Find all SET DNA PROMPT BLOCKs in order
    blocks = re.findall(
        r"\*\*SET DNA PROMPT BLOCK:\*\*\s*\n(.*?)"
        r"(?=\n\s*[═=]{3,}|\n\s*\*\*SET \d|\n\s*SET \d|\Z)",
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
    SHOOT-SPR26-S1-001 → Set 1
    SHOOT-SPR26-S2-001 → Set 2

    Falls back to first set DNA if no set
    identifier found in ref_code.
    """
    if not set_dnas:
        return ""

    match = re.search(r"-S(\d+)-", ref_code)
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


# Global counter for product distribution
_GENERATION_COUNTER = 0

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
            # ── Parse input ────────────────────────────
            parts = input_str.split("|")
            if len(parts) != 3:
                return (
                    "TOOL_ERROR: Input must be "
                    "creative_prompt|aspect_ratio|reference_code"
                )

            creative_prompt, aspect_ratio, ref_code = [
                p.strip() for p in parts
            ]

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
            idx = (
                _GENERATION_COUNTER
                % len(product_images)
            )
            product_bytes, product_mime, product_name = (
                product_images[idx]
            )
            _GENERATION_COUNTER += 1

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

            # Load max 1 reference image
            # to avoid overloading Nano Banana
            all_refs = _load_folder_images(REFS_DIR)
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
                f"\n{world_block}"
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

            print(f"[ImageGenerator] Sending request for {ref_code}...")
            print(f"[ImageGenerator] - Product: {product_name}")
            print(f"[ImageGenerator] - Style Refs: {ref_count}")
            print(f"[ImageGenerator] - Prompt Length: {len(full_prompt)} chars")

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
                    ),
                )
            except Exception as api_err:
                print(f"[ImageGenerator] API Call Failed: {api_err}")
                return f"TOOL_ERROR: API call failed: {str(api_err)}"

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
                print(f"[ImageGenerator] FAILED for {ref_code}. No candidates in response.")
                return "TOOL_ERROR: No candidates in response from API."

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
