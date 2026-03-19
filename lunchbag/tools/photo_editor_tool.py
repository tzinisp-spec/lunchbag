import os
import re
import base64
import time
from pathlib import Path
from datetime import datetime
from crewai.tools import BaseTool
from google import genai
from google.genai import types

ASSET_DIR    = Path("asset_library/images")
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
    match = re.search(
        r"MOOD IN ONE SENTENCE\s*\n(.*?)(?=\n\s*[═=]{3,}|\n\s*##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
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
        "You are a Photo Editor and Stylist reviewing "
        "images for Orpina, a jewelry brand that makes "
        "3D printed polymer earrings.\n\n"
        "IMPORTANT MATERIAL CONTEXT:\n"
        "Orpina earrings are made from 3D printed "
        "eco-friendly polymer. They have a matte to satin "
        "surface finish. They are NOT metallic, NOT shiny "
        "plastic, NOT glossy. They are lightweight with "
        "bold solid colours. Any image showing metallic, "
        "mirror-like, or high-gloss earrings is wrong.\n\n"
        f"IMAGES PROVIDED:\n"
        f"- First {len(product_images)} image(s): PRODUCT "
        f"REFERENCE — the exact earring that must appear\n"
        f"{anchor_instruction}"
        f"- LAST IMAGE: the photograph to review\n\n"
        f"SHOOT CONCEPT: {shoot_concept}\n\n"
        "Review the LAST IMAGE against these 8 criteria:\n\n"
        "1. PRODUCT ACCURACY\n"
        "Does the earring match the product reference in "
        "shape and colour? A completely different design "
        "or colour = fail.\n\n"
        "2. MATERIAL CORRECTNESS\n"
        "Does the earring surface look like matte to satin "
        "polymer? Check: it should NOT look metallic, "
        "mirror-like, or high-gloss plastic. It should "
        "have a subtle, soft surface quality consistent "
        "with 3D printed polymer. Metallic or glossy = fail.\n\n"
        "3. EARRING SIZE\n"
        "Is the earring a realistic size relative to the "
        "model's ear or the surface it sits on? "
        "Earrings should look wearable — not oversized "
        "like a prop, not so tiny they disappear. "
        "Unrealistic scale = fail.\n\n"
        "4. EARRING ORIENTATION\n"
        "Does the earring hang or sit naturally? "
        "Check for: twisted at an impossible angle, "
        "floating unnaturally, warped shape, or looking "
        "physically implausible. Unnatural orientation "
        "= fail.\n\n"
        "5. MODEL CONSISTENCY\n"
        "If a model appears, does she look like the same "
        "person as in the anchor image? Check ethnicity, "
        "hair colour, and skin tone. Skip if no anchor.\n\n"
        "6. LIGHTING REALISM\n"
        "Does the lighting feel like a real photograph? "
        "Flat, overlit, or obviously AI-generated = fail.\n\n"
        "7. COMPOSITION INTENT\n"
        "Does the composition feel deliberate? Does the "
        "earring have clear visual prominence? "
        "Random or cluttered = fail.\n\n"
        "8. ANTI-AI CHECK\n"
        "Does the image look AI-generated? Check: "
        "plastic skin, impossible geometry, blurry hands, "
        "unnatural hair, warped backgrounds. "
        "Looks like a real photograph = pass.\n\n"
        "For each criterion respond PASS or FAIL with "
        "one sentence reason.\n"
        "Then give an OVERALL verdict: PASS or FIX\n"
        "FIX if ANY single criterion fails.\n"
        "If FIX: write a FIX INSTRUCTION — one specific "
        "sentence telling Nano Banana exactly what to "
        "change to fix the most critical issue. "
        "For material issues say exactly: "
        "'Change the earring surface from [current] to "
        "matte polymer with soft satin finish, "
        "non-metallic, non-glossy.'\n\n"
        "Respond in EXACTLY this format:\n"
        "1. PRODUCT ACCURACY: PASS/FAIL — [reason]\n"
        "2. MATERIAL CORRECTNESS: PASS/FAIL — [reason]\n"
        "3. EARRING SIZE: PASS/FAIL — [reason]\n"
        "4. EARRING ORIENTATION: PASS/FAIL — [reason]\n"
        "5. MODEL CONSISTENCY: PASS/FAIL — [reason]\n"
        "6. LIGHTING REALISM: PASS/FAIL — [reason]\n"
        "7. COMPOSITION INTENT: PASS/FAIL — [reason]\n"
        "8. ANTI-AI CHECK: PASS/FAIL — [reason]\n"
        "OVERALL: PASS or FIX\n"
        "FIX INSTRUCTION: [specific fix or 'none needed']"
    )

    parts_list.append(types.Part(text=review_prompt))

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=[
            types.Content(role="user", parts=parts_list)
        ],
    )

    review_text = response.text.strip()
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
            "You are given a product reference image and a "
            "photoshoot image that needs a specific fix.\n\n"
            "MATERIAL CONTEXT: Orpina earrings are 3D printed "
            "polymer with a matte to satin surface finish. "
            "They are NOT metallic and NOT high-gloss plastic. "
            "If the fix involves the earring surface, ensure "
            "the result shows matte polymer texture.\n\n"
            f"FIX REQUIRED: {fix_instruction}\n\n"
            "Apply ONLY this fix. Keep everything else in "
            "the image identical — composition, lighting, "
            "background, model pose, skin tone, hair. "
            "Only change what is specified in the fix.\n\n"
            "The product earring from the reference must "
            "remain exactly as shown — same shape, colour, "
            "and form. Output the fixed image only."
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
            ),
        )

        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                data = part.inline_data.data
                if isinstance(data, str):
                    return base64.b64decode(data)
                return data

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

            # Product reference first
            for prod_bytes, prod_mime, _ in product_images:
                parts_list.append(
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=prod_mime,
                            data=prod_bytes,
                        )
                    )
                )

            # All images in this batch
            for _, img_bytes in batch:
                parts_list.append(
                    types.Part(
                        inline_data=types.Blob(
                            mime_type="image/png",
                            data=img_bytes,
                        )
                    )
                )

            batch_names = [
                f.name for f, _ in batch
            ]

            parts_list.append(types.Part(text=(
                "You are reviewing a batch of photoshoot "
                "images for Orpina jewelry brand as both "
                "a Photo Editor and Technical Supervisor.\n\n"
                f"IMAGE 1: Product reference — the exact "
                f"earring that must appear in every shot.\n"
                f"IMAGES 2 to {len(batch)+1}: Photoshoot "
                f"images that have already passed individual "
                f"review. Look at them as a group.\n\n"
                f"The images in this batch are:\n"
                + "\n".join(
                    f"IMAGE {i+2}: {name}"
                    for i, name in enumerate(batch_names)
                ) +
                f"\n\nTECHNICAL SPEC FOR THIS SHOOT:\n"
                f"{technical_spec}\n\n"
                "Check for these batch-level issues:\n\n"
                "1. EARRING CONSISTENCY\n"
                "Does the earring in every image match the "
                "product reference in shape and colour? "
                "Flag any image where the earring slipped "
                "through individual review incorrectly.\n\n"
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
                "that could not belong to Orpina.\n\n"
                "4. MATERIAL CONSISTENCY\n"
                "Do all earrings show the same surface "
                "quality — matte to satin polymer, not "
                "metallic or glossy? Any image showing "
                "a different surface quality = flag.\n\n"
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
                    f"IMAGE {i+2} ({name}): PASS or FLAG — reason"
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
                image_num  = batch_start + i + 2
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
        print(f"[PhotoEditor] Batch check error: {e}")
        return []


def _extract_fix_instruction(review_text: str) -> str:
    """Extract the FIX INSTRUCTION line from review text."""
    for line in review_text.splitlines():
        if line.upper().startswith("FIX INSTRUCTION:"):
            instruction = line.split(":", 1)[-1].strip()
            if instruction.lower() != "none needed":
                return instruction
    return "Fix the most critical issue identified in the review"


class PhotoEditorTool(BaseTool):
    name: str = "Orpina Photo Editor"
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
                f for f in ASSET_DIR.iterdir()
                if f.is_file()
                and f.suffix.lower() in SUPPORTED
                and "TEST-" not in f.name
            ])

            if not all_generated:
                return "No generated images found to review."

            # ── Load Art Director report for rework loop ──
            art_report_path = OUTPUTS_DIR / "art_director_latest.md"
            art_notes = {}
            if art_report_path.exists():
                art_content = art_report_path.read_text()
                # Simple extraction of: - Art Review-NAME -> NOTE
                notes_match = re.findall(
                    r"- (Art Review-.*?)\n\s+→ (.*?)\n",
                    art_content
                )
                for name, note in notes_match:
                    art_notes[name.strip()] = note.strip()

            total        = len(all_generated)
            passed_first = 0
            fixed        = 0
            flagged      = 0
            image_results = []
            anchor_image  = None

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
                    # First passing image becomes anchor
                    if anchor_image is None:
                        anchor_image = (gen_bytes, "image/png")
                    image_results.append({
                        "file":    gen_file.name,
                        "status":  "PASS",
                        "review":  review_text,
                    })
                    print(f"[PhotoEditor] ✓ PASS")
                    continue

                # ── Attempt fix up to 3 times ────────────
                fix_instruction = _extract_fix_instruction(
                    review_text
                )
                print(f"[PhotoEditor] Fix needed: {fix_instruction}")

                best_bytes      = None
                fix_passed      = False
                last_fix_review = ""
                last_fix_instruction = fix_instruction

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
                    target_file = gen_file
                    final_name  = gen_file.name
                    if is_art_rework:
                        final_name = gen_file.name.replace("Art Review-", "")
                        target_file = gen_file.parent / final_name
                        # Write new and remove old
                        target_file.write_bytes(best_bytes)
                        gen_file.unlink()
                    else:
                        gen_file.write_bytes(best_bytes)

                    if anchor_image is None:
                        anchor_image = (best_bytes, "image/png")
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
                    continue

                # ── All 3 attempts failed ─────────────────
                # Rename with "Needs Review-" prefix
                flagged_name = f"Needs Review-{gen_file.name}"
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

            # ── Second pass batch consistency check ───
            print(
                f"\n[PhotoEditor] Running batch "
                f"consistency check "
                f"({'with' if technical_spec else 'without'} "
                f"Technical Spec)..."
            )

            passed_files = [
                (
                    ASSET_DIR / r["file"],
                    (ASSET_DIR / r["file"]).read_bytes(),
                )
                for r in image_results
                if r["status"] in ("PASS", "FIXED")
                and (ASSET_DIR / r["file"]).exists()
            ]

            batch_flags = _batch_consistency_check(
                client,
                product_images,
                passed_files,
                technical_spec,
            )

            for flagged_path, reason in batch_flags:
                # Rename with Needs Review prefix
                new_name     = f"Needs Review-{flagged_path.name}"
                new_path     = flagged_path.parent / new_name
                flagged_path.rename(new_path)
                flagged     += 1
                passed_first = max(0, passed_first - 1)

                # Update result entry
                for r in image_results:
                    if r["file"] == flagged_path.name:
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
                    f"[PhotoEditor] Batch check passed — "
                    f"no additional flags"
                )

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
                f"# PHOTO EDITOR REPORT — ORPINA\n"
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

            return report

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
