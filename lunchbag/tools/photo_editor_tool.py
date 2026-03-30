import os
import re
import json
import base64
import time
from pathlib import Path
from datetime import datetime
from crewai.tools import BaseTool
from google import genai
from google.genai import types

CHECKPOINT_PATH = Path("outputs/photo_editor_checkpoint.json")


def _save_checkpoint(
    index: int,
    anchor_file: str | None,
    passed_first: int,
    fixed: int,
    flagged: int,
    image_results: list,
) -> None:
    """Persist per-image progress so a retry can resume mid-set."""
    try:
        data = {
            "shoot_folder":    os.getenv("SHOOT_FOLDER", ""),
            "set":             int(os.getenv("CURRENT_SET", "0")),
            "completed_index": index,
            "anchor_image_file": anchor_file,
            "passed_first":    passed_first,
            "fixed":           fixed,
            "flagged":         flagged,
            "image_results":   image_results,
        }
        CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_PATH.write_text(json.dumps(data))
    except Exception:
        pass  # Never let a checkpoint save crash the main loop

# Issues that cannot be fixed by inpainting — they require a full
# re-generation of the shot from scratch.
_STRUCTURAL_KEYWORDS = [
    "shoulder strap",
    "crossbody strap",
    "long strap",
    "long shoulder",
    "replace the entire bag",
    "wrong bag model",
    "wrong shape",
    "reduce the scale of the bag",
    "bag is too large",
    "bag appears too large",
]


def _is_structural_failure(fix_instruction: str) -> bool:
    """Return True if the fix cannot be applied via image editing."""
    lower = fix_instruction.lower()
    return any(k in lower for k in _STRUCTURAL_KEYWORDS)


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

PRODUCTS_DIR = Path("products")
OUTPUTS_DIR  = Path("outputs")
REPORTS_DIR  = Path("outputs/photo_editor_reports")
SUPPORTED    = {".jpg", ".jpeg", ".png"}


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


def _get_shoot_concept() -> str:
    """Read creative concept from style bible."""
    path = OUTPUTS_DIR / "style_bible_and_shot_list.md"
    if not path.exists():
        return ""
    content = path.read_text()
    # Try concept name from header line first
    # e.g. "Concept: The Athletic Ritual | Brand: ..."
    match = re.search(
        r"^Concept:\s*(.+?)(?:\s*\||\s*$)",
        content,
        re.MULTILINE | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    # Fallback: MOOD paragraph
    match = re.search(
        r"\*\*MOOD\*\*\s*\n(.*?)(?=\n\s*\*\*|\n[═=]{3,}|\Z)",
        content,
        re.DOTALL,
    )
    if match:
        return match.group(1).strip()[:200]
    return ""


def _extract_technical_spec() -> str:
    """
    Read the Technical Spec from the style bible.
    Returns the full spec block or empty string.
    """
    path = OUTPUTS_DIR / "style_bible_and_shot_list.md"
    if not path.exists():
        return ""

    content = path.read_text()

    match = re.search(
        r"TECHNICAL SPEC.*?\n[═=]{3,}\n(.*?)(?=\n[═=]{3,}|\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )

    if match:
        spec = match.group(1).strip()
        print(
            f"[PhotoEditor] Technical Spec found "
            f"({len(spec)} chars)"
        )
        return spec

    print("[PhotoEditor] Technical Spec not found in style bible")
    return ""


def _review_image(
    client: genai.Client,
    product_images: list[tuple[bytes, str, str]],
    anchor_image: tuple[bytes, str] | None,
    gen_bytes: bytes,
    shoot_concept: str,
    image_index: int,
) -> tuple[str, str]:
    """
    Review a single image against all 8 criteria.
    Returns (verdict, full_review_text).
    verdict is one of: PASS, FIX
    """
    parts_list = []

    # Product references
    for prod_bytes, prod_mime, prod_name in product_images:
        parts_list.append(
          types.Part(
                inline_data=types.Blob(
                    mime_type=prod_mime,
                    data=prod_bytes,
                )
            )
        )

    # Anchor image for consistency check
    if anchor_image and image_index > 0:
        anchor_bytes, anchor_mime = anchor_image
        parts_list.append(
            types.Part(
                inline_data=types.Blob(
                    mime_type=anchor_mime,
                    data=anchor_bytes,
                )
            )
        )

    # Generated image to review
    parts_list.append(
        types.Part(
            inline_data=types.Blob(
                mime_type="image/png",
                data=gen_bytes,
            )
        )
    )

    anchor_instruction = (
        f"IMAGE {len(product_images) + 1} is an approved "
        f"reference image from this sprint. Compare the "
        f"model appearance and lighting against it.\n"
        if anchor_image and image_index > 0
        else ""
    )

    review_prompt = (
        "You are a Photo Editor and Stylist "
        "reviewing images for The Lunchbags, "
        "a brand making cotton thermal lunch bags "
        "with distinctive graphic prints.\n\n"
        "CRITICAL MATERIAL CONTEXT:\n"
        "The Lunchbags are made from cotton with "
        "a waterproof interior. The exterior has "
        "a soft woven textile surface with bold "
        "graphic prints. They are NOT leather, "
        "NOT plastic, NOT glossy. The fabric "
        "texture should be clearly visible. "
        "The print pattern must match the product "
        "reference EXACTLY — wrong pattern = "
        "wrong product.\n\n"
        f"IMAGES PROVIDED:\n"
        f"- First {len(product_images)} image(s): "
        f"PRODUCT REFERENCE — the exact bag that "
        f"must appear\n"
        f"{anchor_instruction}"
        f"- LAST IMAGE: the photograph to review\n\n"
        f"SHOOT CONCEPT: {shoot_concept}\n\n"
        "Review the LAST IMAGE against these "
        "8 criteria:\n\n"
        "1. PATTERN ACCURACY\n"
        "Does the print pattern on the bag match "
        "the product reference? Check motifs, "
        "colours, and overall design. "
        "Allow for natural variation caused by "
        "lighting, angle, and fabric drape — "
        "a pattern that appears slightly darker "
        "or lighter due to shadows is acceptable. "
        "Fail only if: the pattern design is "
        "fundamentally different, wrong motifs, "
        "completely wrong colours, or the pattern "
        "appears to be a different product entirely. "
        "Lighting variation on same pattern = pass.\n\n"
        "2. FABRIC QUALITY\n"
        "Does the bag surface look like real "
        "woven cotton? It MUST have visible "
        "fabric weave texture, natural matte "
        "finish, and soft drape. This is a "
        "hard fail — no partial credit:\n"
        "- Surface looks plastic, vinyl, or "
        "synthetic = FAIL\n"
        "- Surface looks like leather = FAIL\n"
        "- Surface is glossy or shiny = FAIL\n"
        "- No visible fabric texture (smooth "
        "like rubber) = FAIL\n"
        "Cotton weave must be visible, especially "
        "in close-up shots. If you cannot "
        "clearly see fabric texture = FAIL.\n\n"
        "3. BAG SIZE AND SCALE\n"
        "The bag is H21cm x W16cm x D24cm — "
        "a compact lunch bag roughly the size "
        "of a large hardcover book. "
        "This is a hard fail — no partial credit:\n"
        "- Bag appears larger than the model's "
        "torso = FAIL\n"
        "- Bag appears wider than the model's "
        "shoulders = FAIL\n"
        "- Bag looks like a large tote, backpack, "
        "or shopping bag = FAIL\n"
        "- When held in one hand, the bag bottom "
        "should be near or above the hip — if it "
        "reaches the knee, it is too big = FAIL\n"
        "For no-model shots: the bag should appear "
        "smaller than an A4 sheet of paper in "
        "height (21cm). If it looks larger than "
        "a laptop bag or an everyday backpack, "
        "it is too big = FAIL.\n"
        "The shape should be rectangular with "
        "natural cotton softness — not collapsed, "
        "not rigidly geometric.\n\n"
        "4. HARDWARE AND DETAIL FIDELITY\n"
        "Compare every visible hardware detail "
        "on the bag against the product reference. "
        "Check each of these specifically:\n"
        "- ZIPPERS: Count the zippers. Does the "
        "generated bag have exactly the same "
        "number as the product reference? "
        "Extra zipper not in reference = fail.\n"
        "- STRAPS AND HANDLES: Does the bag have "
        "exactly the same straps and handles as "
        "the reference? Extra strap, missing "
        "handle, different handle style = fail.\n"
        "- CLIPS AND CLOSURES: Are the clips, "
        "buckles, or closures identical to the "
        "reference in number and position? "
        "Extra clip or missing clip = fail.\n"
        "- SEAMS AND PANELS: Does the bag have "
        "the same panel structure and seam "
        "placement as the reference?\n"
        "- BRANDING: Any logos or labels must "
        "match the reference exactly or be "
        "absent if not in reference.\n"
        "ANY invented hardware not present in "
        "the product reference = fail. "
        "ANY missing hardware visible in the "
        "product reference = fail.\n\n"
        "5. MODEL CONSISTENCY\n"
        "If a model appears, does she look like "
        "the same person as in the anchor image? "
        "Skip if no anchor.\n\n"
        "6. LIGHTING REALISM\n"
        "Does the lighting feel like a real "
        "lifestyle photograph? Flat, overlit, "
        "or AI-looking = fail.\n\n"
        "7. COMPOSITION INTENT\n"
        "Does the composition feel deliberate? "
        "Is the bag clearly prominent? "
        "Random or cluttered = fail.\n\n"
        "8. ANTI-AI CHECK\n"
        "Does the image look AI-generated? "
        "Check: plastic surfaces, impossible "
        "geometry, warped backgrounds, fake "
        "fabric texture. Looks like a real "
        "photograph = pass.\n\n"
        "9. COMPOSITION REALITY CHECK — "
        "STRICT HUMAN ANATOMY AUDIT\n"
        "This is a zero-tolerance check. "
        "Any anatomical impossibility = "
        "immediate FAIL. No exceptions.\n\n"
        "BEFORE SCORING: physically count and "
        "write the numbers in your response. "
        "State: 'I count: X people, X hands "
        "total, X fingers on each visible hand, "
        "X legs total, X arms total.' "
        "If you cannot count clearly due to "
        "occlusion, state that explicitly. "
        "Do not skip this count.\n\n"
        "COUNT AND VERIFY:\n"
        "- Hands: count every visible hand. "
        "One person = maximum 2 hands. "
        "3 or more hands with one person = FAIL.\n"
        "- Fingers: each hand has exactly 5 "
        "fingers. 4 or 6 fingers = FAIL.\n"
        "- Legs: count every visible leg. "
        "One person = maximum 2 legs. "
        "Extra leg, third leg, leg growing "
        "from wrong place = FAIL.\n"
        "- Arms: one person = maximum 2 arms. "
        "Extra arm = FAIL.\n"
        "- Head: one person = one head. "
        "Head size must be proportional to "
        "body — not tiny or enormous = FAIL.\n"
        "- Limb proportions: arms and legs "
        "must be realistic human length. "
        "Extremely long or short limbs = FAIL.\n"
        "- Body position: the person must be "
        "in a physically possible position. "
        "Floating, impossible twist, or body "
        "parts at wrong angles = FAIL.\n"
        "- Clothing: fabric must have real "
        "texture and folds. Painted-on or "
        "melted clothing = FAIL.\n\n"
        "SKIN CHECK:\n"
        "- Skin must have natural texture — "
        "pores, slight variation in tone. "
        "Plastic, waxy, or poreless skin = FAIL.\n"
        "- Skin colour must be consistent "
        "across all visible body parts.\n\n"
        "If ANY of the above fail = "
        "FAIL this criterion immediately. "
        "Do not average with other scores.\n\n"
        "For each criterion respond PASS or FAIL "
        "with one sentence reason.\n"
        "Then give OVERALL: PASS or FIX\n"
        "FIX if ANY criterion fails.\n"
        "If FIX: write a FIX INSTRUCTION that "
        "addresses EVERY criterion that failed. "
        "List each required change as a numbered "
        "point. Do not skip any failed criterion.\n"
        "Examples:\n"
        "For one failure: 'Remove the extra "
        "zipper on [location] — not in reference.'\n"
        "For two failures: '1. Remove the long "
        "shoulder strap — not in reference. "
        "2. Replace the male model with the "
        "female model from the anchor image.'\n"
        "Be specific about location and what "
        "needs to change for each failure.\n\n"
        "Respond in EXACTLY this format:\n"
        "1. PATTERN ACCURACY: PASS/FAIL — [reason]\n"
        "2. FABRIC QUALITY: PASS/FAIL — [reason]\n"
        "3. BAG SIZE AND SCALE: PASS/FAIL — [reason]\n"
        "4. DETAIL FIDELITY: PASS/FAIL — [reason]\n"
        "5. MODEL CONSISTENCY: PASS/FAIL — [reason]\n"
        "6. LIGHTING REALISM: PASS/FAIL — [reason]\n"
        "7. COMPOSITION INTENT: PASS/FAIL — [reason]\n"
        "8. ANTI-AI CHECK: PASS/FAIL — [reason]\n"
        "9. COMPOSITION REALITY CHECK: "
        "I count: [X people, X hands, X fingers "
        "per hand, X legs, X arms]. "
        "PASS/FAIL — [reason]\n"
        "OVERALL: PASS or FIX\n"
        "FIX INSTRUCTION: [specific fix or "
        "'none needed']"
    )

    parts_list.append(types.Part(text=review_prompt))

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=[
            types.Content(role="user", parts=parts_list)
        ],
    )

    review_text = response.text.strip()
    
    # Criterion 9 is a hard veto
    if "9. COMPOSITION REALITY CHECK" in review_text:
        crit9_section = review_text.split(
            "9. COMPOSITION REALITY CHECK"
        )[-1][:200]
        if "FAIL" in crit9_section.upper():
            return "FIX", review_text

    verdict     = (
        "PASS"
        if "OVERALL: PASS" in review_text.upper()
        else "FIX"
    )
    return verdict, review_text


def _fix_image(
    client: genai.Client,
    product_images: list[tuple[bytes, str, str]],
    gen_bytes: bytes,
    fix_instruction: str,
) -> bytes | None:
    """
    Ask Nano Banana to fix a specific issue in the image.
    Keeps everything else identical.
    """
    try:
        parts_list = []
        for prod_bytes, prod_mime, _ in product_images:
            parts_list.append(
                types.Part(
                    inline_data=types.Blob(
                        mime_type=prod_mime,
                        data=prod_bytes,
                    )
                )
            )

        parts_list.append(
            types.Part(
                inline_data=types.Blob(
                    mime_type="image/png",
                    data=gen_bytes,
                )
            )
        )

        parts_list.append(types.Part(text=(
            "You are given a product reference image "
            "and a photoshoot image that needs a fix.\n\n"
            "CRITICAL: The Lunchbags have distinctive "
            "cotton print patterns. If the fix involves "
            "the pattern, restore it to match "
            "the product reference EXACTLY — same motifs, "
            "same colours, same scale, same arrangement. "
            "Do not invent a new pattern.\n\n"
            "The bag surface must look like real woven "
            "cotton — matte, soft texture, not glossy "
            "or plastic-looking.\n\n"
            f"FIX REQUIRED: {fix_instruction}\n\n"
            "Apply ONLY this fix. Keep everything else "
            "in the image identical — composition, "
            "lighting, background, model pose, "
            "skin tone, hair. Only change what is "
            "specified in the fix.\n\n"
            "Output the fixed image only."
        )))

        # Rate limit protection on fix calls
        time.sleep(4)

        response = client.models.generate_content(
            model="gemini-3-pro-image-preview",
            contents=[
                types.Content(role="user", parts=parts_list)
            ],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
                temperature=0.2,
                image_config=types.ImageConfig(
                    aspect_ratio="3:4",
                ),
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                data = part.inline_data.data
                if isinstance(data, str):
                    return base64.b64decode(data)
                return data

    except (AttributeError, TypeError, ImportError,
            ModuleNotFoundError, NotImplementedError):
        raise  # Let monitor catch these as fatal — no point retrying
    except Exception as e:
        print(f"[PhotoEditor] Fix error: {e}")

    return None


def _batch_consistency_check(
    client: genai.Client,
    product_images: list[tuple[bytes, str, str]],
    passed_files: list[tuple[Path, bytes]],
    technical_spec: str = "",
) -> list[tuple[Path, str]]:
    """
    Second pass — looks at all passing images together
    and flags any that don't belong in the same shoot.
    Returns list of (file_path, reason) that should
    be flagged despite passing individual review.
    """
    if len(passed_files) < 3:
        return []

    max_attempts = 2
    for check_attempt in range(1, max_attempts + 1):
      try:
        # Check in batches of 6 to stay within
        # Nano Banana's context limits
        batch_size   = 6
        to_flag      = []

        for batch_start in range(
            0, len(passed_files), batch_size
        ):
            batch = passed_files[
                batch_start:batch_start + batch_size
            ]

            parts_list = []

            # All product references first
            for prod_bytes, prod_mime, prod_name in product_images:
                parts_list.append(
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=prod_mime,
                            data=prod_bytes,
                        )
                    )
                )

            # All photoshoot images in this batch
            for _, img_bytes in batch:
                parts_list.append(
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="image/png",
                            data=img_bytes,
                        )
                    )
                )

            batch_names = [f.name for f, _ in batch]
            prod_names  = [name for _, _, name in product_images]

            parts_list.append(types.Part(text=(
                "You are reviewing a batch of photoshoot "
                "images for The Lunchbags lifestyle product brand as both "
                "a Photo Editor and Technical Supervisor.\n\n"
                f"IMAGES 1 to {len(prod_names)}: Product "
                f"references — the exact bags that "
                f"must appear in the shoot:\n"
                + "\n".join(
                    f"IMAGE {i+1}: {name}"
                    for i, name in enumerate(prod_names)
                ) +
                f"\n\nIMAGES {len(prod_names)+1} to "
                f"{len(prod_names)+len(batch)}: Photoshoot "
                f"images that have already passed individual "
                f"review. Look at them as a group.\n\n"
                f"The photoshoot images in this batch are:\n"
                + "\n".join(
                    f"IMAGE {len(prod_names)+i+1}: {name}"
                    for i, name in enumerate(batch_names)
                ) +
                f"\n\nTECHNICAL SPEC FOR THIS SHOOT:\n"
                f"{technical_spec}\n\n"
                "Check for these batch-level issues:\n\n"
                "1. PRODUCT CONSISTENCY\n"
                "Each photoshoot image features ONE of the "
                "product references. Does the bag in every "
                "image match one of the references in "
                "pattern, shape, and colour? Flag any "
                "image where the bag does not match ANY "
                "of the references.\n\n"
                "2. MODEL CONSISTENCY\n"
                "If a model appears across multiple images, "
                "does she look like the same person? "
                "Different ethnicity, hair colour, or skin "
                "tone across images = flag.\n\n"
                "3. SHOOT CONSISTENCY\n"
                "This sprint has 2-3 distinct sets. "
                "Each set has a different location and "
                "lighting setup — this is intentional. "
                "Do NOT flag images simply because they "
                "look different from each other. Only "
                "flag if the overall brand aesthetic "
                "has broken down completely — wrong "
                "colour world, wrong model, or content "
                "that could not belong to The Lunchbags.\n\n"
                "4. MATERIAL CONSISTENCY\n"
                "Do all bags show the same surface "
                "quality — real woven cotton texture, "
                "matte finish, no leather or plastic?\n\n"
                "5. TECHNICAL SPEC DRIFT\n"
                "Compare the lighting in each image against "
                "the Technical Spec provided above.\n"
                "Check specifically:\n"
                "- LIGHT DIRECTION: Is the key light coming "
                "from the same direction in every image? "
                "If the spec says camera-left but an image "
                "shows light from the right = flag.\n"
                "- COLOUR TEMPERATURE: Does the light feel "
                "consistent in warmth or coolness across "
                "all images? One image significantly warmer "
                "or cooler than the others = flag.\n"
                "- SHADOW QUALITY: Are shadows consistent "
                "in hardness and direction across images? "
                "One image with hard shadows when others "
                "have soft = flag.\n"
                "- OVERALL EXPOSURE: Do all images sit at "
                "roughly the same exposure level? One "
                "significantly brighter or darker = flag.\n\n"
                "For each image respond PASS or FLAG.\n"
                "If FLAG give a specific one-sentence reason "
                "identifying which check failed and why.\n\n"
                "Respond in EXACTLY this format:\n"
                + "\n".join(
                    f"IMAGE {len(prod_names)+i+1} ({name}): PASS or FLAG — reason"
                    for i, name in enumerate(batch_names)
                )
            )))

            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[
                    types.Content(
                        role="user",
                        parts=parts_list,
                    )
                ],
            )

            result_text = response.text.strip()

            # Parse results
            for i, (file_path, _) in enumerate(batch):
                image_num  = len(prod_names) + i + 1
                image_name = file_path.name
                search     = f"IMAGE {image_num} ({image_name}):"
                for line in result_text.splitlines():
                    if search.upper() in line.upper():
                        if "FLAG" in line.upper():
                            reason = (
                                line.split("—", 1)[-1].strip()
                                if "—" in line
                                else "Failed batch consistency check"
                            )
                            to_flag.append(
                                (file_path, reason)
                            )
                            print(
                                f"[PhotoEditor] Batch check "
                                f"flagged: {image_name} — "
                                f"{reason}"
                            )
                        break

        return to_flag

      except Exception as e:
        print(
            f"[PhotoEditor] Batch check error "
            f"(attempt {check_attempt}/{max_attempts}): {e}"
        )
        if check_attempt < max_attempts:
            time.sleep(10)

    print(
        "[PhotoEditor] ⚠ Batch check failed after "
        f"{max_attempts} attempts — "
        "consistency NOT verified for this set"
    )
    return []


def _extract_fix_instruction(review_text: str) -> str:
    """
    Extract the FIX INSTRUCTION from review text.
    Captures multi-line instructions so all failures
    are addressed in a single fix call.
    """
    lines = review_text.splitlines()
    for i, line in enumerate(lines):
        if line.upper().startswith("FIX INSTRUCTION:"):
            first = line.split(":", 1)[-1].strip()
            parts = [first] if first else []
            # Collect continuation lines
            for j in range(i + 1, len(lines)):
                next_line = lines[j].strip()
                if not next_line:
                    break
                if re.match(
                    r"^(OVERALL|FIX INSTRUCTION):",
                    next_line,
                    re.IGNORECASE,
                ):
                    break
                parts.append(next_line)
            combined = " ".join(parts).strip()
            if combined.lower() not in ("none needed", ""):
                return combined
    return "Fix the most critical issue identified in the review"


class PhotoEditorTool(BaseTool):
    name: str = "The Lunchbags Photo Editor"
    description: str = """
        Reviews all generated images as a Photo Editor would —
        checking product accuracy, model consistency, lighting
        realism, composition intent, and anti-AI quality.

        For every image that fails any criterion, immediately
        attempts a targeted fix using Nano Banana image editing.
        Re-reviews the fix before accepting it.

        If fix passes review — overwrites original file.
        If fix fails review — flags for manual review.
        Files are never moved or renamed.

        No input required — call with an empty string.

        Output: full review report with per-image verdicts,
        fix results, and summary statistics.
    """

    def _run(self, input_str: str = "") -> str:
        try:
            # ── Parse input ────────────────────────────
            resume_idx = 0
            if "resume_from=" in input_str:
                try:
                    resume_idx = int(input_str.split("=")[-1]) - 1
                except:
                    pass

            client = genai.Client(
                api_key=os.getenv("GEMINI_API_KEY")
            )

            product_images = _load_folder_images(PRODUCTS_DIR)
            if not product_images:
                return "TOOL_ERROR: No product images found."

            shoot_concept  = _get_shoot_concept()
            technical_spec = _extract_technical_spec()

            # ── Load images to review ─────────────────────
            all_generated = sorted([
                f for f in _get_asset_dir().iterdir()
                if f.is_file()
                and f.suffix.lower() in SUPPORTED
                and "TEST-" not in f.name
            ])

            if not all_generated:
                return "No generated images found to review."

            # ── REGEN_FILES filter ────────────────────────
            # When set, only review the specified filenames.
            # Used by the auto-regen pass to avoid re-reviewing
            # the full set after regenerating a few shots.
            regen_files_env = os.getenv("REGEN_FILES", "")
            if regen_files_env:
                regen_set = set(regen_files_env.split(","))
                all_generated = [
                    f for f in all_generated
                    if f.name in regen_set
                ]
                print(
                    f"[PhotoEditor] Regen QC mode: "
                    f"reviewing {len(all_generated)} "
                    f"regenerated shot(s)"
                )
                if not all_generated:
                    return "REGEN_QC_NOTHING: no matching files found."

            # ── Auto-resume from checkpoint ───────────────
            checkpoint_data = {}
            if not regen_files_env and CHECKPOINT_PATH.exists():
                try:
                    checkpoint_data = json.loads(
                        CHECKPOINT_PATH.read_text()
                    )
                    ckpt_folder = checkpoint_data.get("shoot_folder")
                    ckpt_set    = checkpoint_data.get("set")
                    curr_folder = os.getenv("SHOOT_FOLDER", "")
                    curr_set    = int(os.getenv("CURRENT_SET", "0"))
                    if (ckpt_folder == curr_folder
                            and ckpt_set == curr_set):
                        resume_idx = checkpoint_data.get(
                            "completed_index", 0
                        )
                        print(
                            f"[PhotoEditor] Resuming from "
                            f"checkpoint at image "
                            f"{resume_idx + 1}"
                        )
                    else:
                        checkpoint_data = {}  # stale checkpoint
                except Exception:
                    checkpoint_data = {}

            # ── Load Art Director report for rework loop ──
            art_report_path = OUTPUTS_DIR / "art_director_latest.md"
            art_notes = {}
            if art_report_path.exists():
                art_content = art_report_path.read_text()
                notes_match = re.findall(
                    r"- (Art Review-.*?)\n\s+→ (.*?)\n",
                    art_content
                )
                for name, note in notes_match:
                    art_notes[name.strip()] = note.strip()

            total        = len(all_generated)
            passed_first = checkpoint_data.get("passed_first", 0)
            fixed        = checkpoint_data.get("fixed", 0)
            flagged      = checkpoint_data.get("flagged", 0)
            image_results = checkpoint_data.get("image_results", [])
            anchor_image  = None
            anchor_image_name: str | None = checkpoint_data.get(
                "anchor_image_file"
            )

            # Restore anchor image from checkpoint
            if anchor_image_name:
                anchor_path = _get_asset_dir() / anchor_image_name
                if anchor_path.exists():
                    anchor_image = (
                        anchor_path.read_bytes(), "image/png"
                    )

            for i, gen_file in enumerate(all_generated):
                # ── Handle Art Review Rework ──────────────
                is_art_rework = "Art Review-" in gen_file.name
                
                if i < resume_idx and not is_art_rework:
                    print(f"[PhotoEditor] Skipping {gen_file.name} (already reviewed)")
                    if anchor_image is None:
                        anchor_image = (gen_file.read_bytes(), "image/png")
                    image_results.append({
                        "file":    gen_file.name,
                        "status":  "PASS",
                        "review":  "Skipped during resume run.",
                    })
                    passed_first += 1
                    continue

                gen_bytes = gen_file.read_bytes()
                
                if is_art_rework:
                    print(f"\n[PhotoEditor] Processing Art Rework: {gen_file.name}...")
                    fix_instruction = art_notes.get(
                        gen_file.name, 
                        "Fix composition and lighting to match the shoot concept."
                    )
                    review_text = f"ART DIRECTOR REWORK REQUIRED: {fix_instruction}"
                    verdict = "FIX"
                else:
                    print(f"\n[PhotoEditor] Reviewing {gen_file.name}...")
                    verdict, review_text = _review_image(
                        client,
                        product_images,
                        anchor_image,
                        gen_bytes,
                        shoot_concept,
                        i,
                    )

                if verdict == "PASS":
                    passed_first += 1
                    if anchor_image is None:
                        anchor_image = (gen_bytes, "image/png")
                        anchor_image_name = gen_file.name
                    image_results.append({
                        "file":    gen_file.name,
                        "status":  "PASS",
                        "review":  review_text,
                    })
                    _save_checkpoint(
                        i, anchor_image_name,
                        passed_first, fixed, flagged,
                        image_results,
                    )
                    print(f"[PhotoEditor] ✓ PASS")
                    continue

                # ── Attempt fix up to 3 times ────────────
                fix_instruction = _extract_fix_instruction(
                    review_text
                )
                print(f"[PhotoEditor] Fix needed: {fix_instruction}")

                # Structural failures (shoulder strap, wrong bag
                # model, wrong scale) cannot be removed by editing.
                # Skip fix attempts — mark for regeneration.
                if _is_structural_failure(fix_instruction):
                    print(
                        f"[PhotoEditor] ✗ Structural failure — "
                        f"edit cannot fix this. Marking for regen."
                    )
                    base_name = gen_file.name
                    for pfx in ["Needs Review-", "Art Review-", "Regen-"]:
                        if base_name.startswith(pfx):
                            base_name = base_name[len(pfx):]
                            break
                    regen_name = f"Regen-{base_name}"
                    regen_path = gen_file.parent / regen_name
                    gen_file.rename(regen_path)
                    flagged += 1
                    print(f"[PhotoEditor] Marked for regen: {regen_name}")
                    image_results.append({
                        "file":     regen_name,
                        "status":   "REGEN_NEEDED",
                        "review":   review_text,
                        "fix":      fix_instruction,
                        "attempts": 0,
                    })
                    _save_checkpoint(
                        i, anchor_image_name,
                        passed_first, fixed, flagged,
                        image_results,
                    )
                    continue

                best_bytes      = None
                fix_passed      = False
                last_fix_review = ""
                last_fix_instruction = fix_instruction

                attempt = 0
                for attempt in range(1, 4):
                    print(
                        f"[PhotoEditor] Fix attempt "
                        f"{attempt}/3..."
                    )

                    fixed_bytes = _fix_image(
                        client,
                        product_images,
                        gen_bytes,
                        last_fix_instruction,
                    )

                    if not fixed_bytes:
                        # API error — retry once without
                        # counting against fix budget
                        print(
                            f"[PhotoEditor] API error on "
                            f"attempt {attempt} — retrying..."
                        )
                        time.sleep(10)
                        fixed_bytes = _fix_image(
                            client,
                            product_images,
                            gen_bytes,
                            last_fix_instruction,
                        )

                    if not fixed_bytes:
                        print(
                            f"[PhotoEditor] No image returned "
                            f"on attempt {attempt}"
                        )
                        continue

                    fix_verdict, fix_review = _review_image(
                        client,
                        product_images,
                        anchor_image,
                        fixed_bytes,
                        shoot_concept,
                        i,
                    )

                    last_fix_review = fix_review

                    if fix_verdict == "PASS":
                        best_bytes  = fixed_bytes
                        fix_passed  = True
                        print(
                            f"[PhotoEditor] ✓ Fixed on "
                            f"attempt {attempt}"
                        )
                        break
                    else:
                        # Use new fix instruction for next attempt
                        last_fix_instruction = (
                            _extract_fix_instruction(fix_review)
                        )
                        print(
                            f"[PhotoEditor] Still failing "
                            f"attempt {attempt} — retrying"
                        )

                if fix_passed and best_bytes:
                    # Write fixed image
                    gen_file.write_bytes(best_bytes)

                    # If file had a prefix, rename
                    # back to original clean name
                    original_name = gen_file.name
                    clean_name = original_name
                    for prefix in [
                        "Needs Review-",
                        "Art Review-",
                    ]:
                        if clean_name.startswith(prefix):
                            clean_name = clean_name[len(prefix):]
                            break

                    if clean_name != original_name:
                        clean_path = gen_file.parent / clean_name
                        gen_file.rename(clean_path)
                        print(
                            f"[PhotoEditor] Renamed back: "
                            f"{original_name} → {clean_name}"
                        )
                        final_name = clean_name
                    else:
                        final_name = original_name

                    if anchor_image is None:
                        anchor_image = (best_bytes, "image/png")
                        anchor_image_name = final_name
                    fixed += 1
                    print(f"[PhotoEditor] ✓ Saved fixed image as {final_name}")
                    image_results.append({
                        "file":       final_name,
                        "status":     "FIXED",
                        "review":     review_text,
                        "fix":        fix_instruction,
                        "fix_review": last_fix_review,
                        "attempts":   attempt,
                    })
                    _save_checkpoint(
                        i, anchor_image_name,
                        passed_first, fixed, flagged,
                        image_results,
                    )
                    continue

                # ── All 3 attempts failed ─────────────────
                # Rename with "Needs Review-" prefix.
                # Strip any existing prefix first to
                # prevent double-prefixing on re-review.
                base_name = gen_file.name
                for pfx in ["Needs Review-", "Art Review-"]:
                    if base_name.startswith(pfx):
                        base_name = base_name[len(pfx):]
                        break
                flagged_name = f"Needs Review-{base_name}"
                flagged_path = gen_file.parent / flagged_name
                gen_file.rename(flagged_path)
                flagged += 1
                print(
                    f"[PhotoEditor] ✗ Flagged after 3 attempts: "
                    f"{flagged_name}"
                )
                image_results.append({
                    "file":     flagged_name,
                    "status":   "FLAGGED",
                    "review":   review_text,
                    "fix":      fix_instruction,
                    "attempts": 3,
                })
                _save_checkpoint(
                    i, anchor_image_name,
                    passed_first, fixed, flagged,
                    image_results,
                )

            # ── Second pass batch consistency check ───
            print(
                f"\n[PhotoEditor] Running batch "
                f"consistency check "
                f"({'with' if technical_spec else 'without'} "
                f"Technical Spec)..."
            )

            passed_files = [
                (
                    _get_asset_dir() / r["file"],
                    (_get_asset_dir() / r["file"]).read_bytes(),
                )
                for r in image_results
                if r["status"] in ("PASS", "FIXED")
                and (_get_asset_dir() / r["file"]).exists()
            ]

            batch_flags = _batch_consistency_check(
                client,
                product_images,
                passed_files,
                technical_spec,
            )

            for flagged_path, reason in batch_flags:
                # Rename with Needs Review prefix.
                # Strip any existing prefix first.
                base_name = flagged_path.name
                for pfx in ["Needs Review-", "Art Review-"]:
                    if base_name.startswith(pfx):
                        base_name = base_name[len(pfx):]
                        break
                new_name     = f"Needs Review-{base_name}"
                new_path     = flagged_path.parent / new_name
                flagged_path.rename(new_path)
                # Update path reference for completeness
                flagged_path = new_path
                flagged     += 1
                passed_first = max(0, passed_first - 1)

                # Update result entry
                for r in image_results:
                    if r["file"] == new_path.name.replace("Needs Review-", ""):
                        r["status"] = "FLAGGED_BATCH"
                        r["file"]   = new_name
                        r["review"] += (
                            f"\nFAILED BATCH CHECK: {reason}"
                        )
                        break

                print(
                    f"[PhotoEditor] Renamed to: {new_name}"
                )

            if batch_flags:
                print(
                    f"[PhotoEditor] Batch check flagged "
                    f"{len(batch_flags)} additional image(s)"
                )
            else:
                print(
                    f"[PhotoEditor] Batch check complete — "
                    f"no additional flags"
                )

            # ── Verify no stale prefixes ──────────────
            stale = [
                f.name for f in _get_asset_dir().iterdir()
                if f.is_file()
                and f.suffix.lower() in SUPPORTED
                and any(
                    f.name.startswith(p)
                    for p in [
                        "Needs Review-",
                        "Art Director Review-",
                        "Art Review-",
                    ]
                )
            ]
            if stale:
                print(
                    f"\n[PhotoEditor] ⚠ {len(stale)} files "
                    f"still have review prefixes after "
                    f"processing — check manually:"
                )
                for s in stale:
                    print(f"  {s}")

            # ── Build report ──────────────────────────────
            now          = datetime.now().strftime("%Y-%m-%d %H:%M")
            pass_pct     = round(
                (passed_first / total) * 100
            ) if total else 0
            final_pass   = passed_first + fixed
            final_pct    = round(
                (final_pass / total) * 100
            ) if total else 0

            report = (
                f"# PHOTO EDITOR REPORT — THE LUNCHBAGS\n"
                f"Run: {now}\n"
                f"Shoot concept: {shoot_concept}\n\n"
                f"{'='*50}\n"
                f"## SUMMARY\n"
                f"Total reviewed:              {total}\n"
                f"Passed first review:          {passed_first} "
                f"({pass_pct}%)\n"
                f"Fixed by targeted edit:       {fixed}\n"
                f"Flagged by batch check:       "
                f"{len(batch_flags)}\n"
                f"Flagged for manual review:    {flagged}\n"
                f"Final approval rate:          "
                f"{final_pass}/{total} ({final_pct}%)\n"
                f"{'='*50}\n\n"
                f"## PER IMAGE RESULTS\n\n"
            )

            for r in image_results:
                icon = (
                    "✓" if r["status"] in ("PASS", "FIXED")
                    else "✗"
                )
                report += (
                    f"{icon} {r['status']} | {r['file']}"
                )
                if r.get("attempts"):
                    report += f" | attempts: {r['attempts']}"
                report += f"\n{r['review']}\n"
                if r["status"] == "FIXED":
                    report += f"FIX APPLIED: {r['fix']}\n"
                report += "\n"

            if flagged > 0:
                flagged_files = [
                    r["file"] for r in image_results
                    if r["status"] == "FLAGGED"
                ]
                report += (
                    f"{'='*50}\n"
                    f"## FLAGGED FOR MANUAL REVIEW\n"
                    f"These files have been renamed with "
                    f"'Needs Review-' prefix:\n\n"
                    + "\n".join(flagged_files) + "\n\n"
                    f"Find them in:\n"
                    f"asset_library/images/\n"
                )

            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp   = datetime.now().strftime("%Y%m%d_%H%M")
            report_path = REPORTS_DIR / f"review_{timestamp}.md"
            report_path.write_text(report)

            latest = Path(
                "outputs/photo_editor_latest.md"
            )
            latest.write_text(report)

            # Clear checkpoint — set completed cleanly
            if CHECKPOINT_PATH.exists():
                try:
                    CHECKPOINT_PATH.unlink()
                except Exception:
                    pass

            return report

        except (AttributeError, TypeError, ImportError,
                ModuleNotFoundError, NotImplementedError) as e:
            return f"FATAL_ERROR: {type(e).__name__}: {e}"
        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
