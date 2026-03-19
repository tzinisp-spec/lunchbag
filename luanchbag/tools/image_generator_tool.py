import os
import re
import base64
import time
from pathlib import Path
from crewai.tools import BaseTool
from google import genai
from google.genai import types

ASSET_DIR      = Path("asset_library/images")
PRODUCTS_DIR   = Path("products")
REFS_DIR       = Path("references")
OUTPUTS_DIR    = Path("outputs")
SUPPORTED      = {".jpg", ".jpeg", ".png"}

TECHNICAL_ANCHOR = (
    "Photorealistic high-end editorial photography. "
    "The earring is the absolute hero of the image. "
    "Reproduce the earring from the product reference "
    "with perfect fidelity — identical shape, colour, "
    "and form. The earring must be fully visible and "
    "sharply in focus at all times. "
    "Maximum realism. No text overlays. No watermarks. "
    "No AI-looking plastic or flat surfaces."
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
    if not ASSET_DIR.exists():
        return None

    files = sorted([
        f for f in ASSET_DIR.iterdir()
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
    name: str = "Orpina Image Generator"
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
                    "jewelry photograph with warm "
                    "Mediterranean mood, natural directional "
                    "lighting, and a minimal clean setting.\n\n"
                )

            if anchor:
                anchor_instruction = (
                    "CONSISTENCY ANCHOR:\n"
                    "The second image provided is an already "
                    "approved image from this shoot. Match it "
                    "precisely on these four dimensions:\n"
                    "1. COLOUR GRADE: Match the overall tonal "
                    "treatment exactly — if the anchor is warm "
                    "and slightly desaturated, this image must "
                    "be too. If it is cool and high contrast, "
                    "match that. Do not introduce a different "
                    "colour grade.\n"
                    "2. EXPOSURE: Match the overall brightness "
                    "level of the anchor exactly. Do not make "
                    "this image brighter or darker.\n"
                    "3. SHADOW TREATMENT: Match the shadow "
                    "quality, direction, and density of the "
                    "anchor. If shadows are soft and subtle "
                    "in the anchor, they must be here too.\n"
                    "4. SKIN TONE RENDERING: If a model appears "
                    "in the anchor, match the skin tone "
                    "rendering — warmth, smoothness, and "
                    "overall treatment must feel identical.\n"
                    "These four dimensions must be locked "
                    "across every image in the sprint. "
                    "Only composition and earring placement "
                    "should differ.\n\n"
                )
            else:
                anchor_instruction = (
                    "This is the FIRST image of the sprint. "
                    "Establish the visual world clearly and "
                    "deliberately — pay close attention to:\n"
                    "1. COLOUR GRADE: Set a clear tonal "
                    "treatment that feels true to the shoot "
                    "concept. This will be the reference grade "
                    "for every subsequent image.\n"
                    "2. EXPOSURE: Set a natural, well-exposed "
                    "baseline that works across different "
                    "compositions.\n"
                    "3. SHADOW TREATMENT: Establish a clear "
                    "shadow quality and direction consistent "
                    "with the lighting spec.\n"
                    "4. SKIN TONE RENDERING: If a model "
                    "appears, render skin tone naturally and "
                    "consistently — this sets the standard "
                    "for all subsequent model shots.\n"
                    "This first image is the visual anchor "
                    "for the entire sprint. Make it count.\n\n"
                )

            full_prompt = (
                f"IMAGE REFERENCES PROVIDED:\n"
                f"IMAGE 1 — PRODUCT: The exact Orpina earring "
                f"({product_name}). Reproduce with perfect "
                f"fidelity — identical shape, colour, form.\n"
            )

            if anchor:
                full_prompt += (
                    f"IMAGE 2 — CONSISTENCY ANCHOR: An approved "
                    f"image from this shoot. Match the model, "
                    f"location, and mood exactly.\n"
                )

            full_prompt += (
                f"\n{world_block}"
                f"{anchor_instruction}"
                f"TECHNICAL REQUIREMENTS:\n"
                f"{TECHNICAL_ANCHOR}\n\n"
                f"COMPOSITION FOR THIS SHOT:\n"
                f"{creative_prompt}\n\n"
                f"IMPORTANT: The references inspired this shoot "
                f"conceptually. Do not replicate them literally. "
                f"Create something new that lives in the same "
                f"visual world — same model, mood, and light — "
                f"but with a fresh composition unique to this shot."
            )

            # ── Build content parts ───────────────────────
            # Order: product, anchor (if exists), prompt
            # Note: style refs NOT passed to generation —
            # their essence lives in the Shoot DNA text block
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

            # Consistency anchor (first generated image)
            if anchor:
                anchor_bytes, anchor_mime = anchor
                parts_list.append(
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=anchor_mime,
                            data=anchor_bytes,
                        )
                    )
                )

            # Prompt last
            parts_list.append(types.Part(text=full_prompt))

            # ── Call Nano Banana Pro ──────────────────────
            client = genai.Client(
                api_key=os.getenv("GEMINI_API_KEY")
            )

            # Stay under 20 RPM rate limit
            # 4 seconds = max 15 RPM — safe headroom
            time.sleep(4)

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
                    temperature=0.8,
                ),
            )

            # ── Extract image ─────────────────────────────
            image_data = None
            if response.candidates and response.candidates[0].content:
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        image_data = part.inline_data.data
                        break

            if not image_data:
                return (
                    "TOOL_ERROR: No image returned. "
                    "Try simplifying the creative prompt."
                )

            # ── Save and verify ───────────────────────────
            ASSET_DIR.mkdir(parents=True, exist_ok=True)
            file_path = ASSET_DIR / f"{ref_code}.png"

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
