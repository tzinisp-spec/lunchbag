import os
import re
from pathlib import Path
from datetime import datetime
from crewai.tools import BaseTool
from google import genai
from google.genai import types

def _get_asset_dir() -> Path:
    shoot_folder = os.getenv("SHOOT_FOLDER", "")
    base_dir     = Path("asset_library/images")
    if shoot_folder:
        path = base_dir / shoot_folder
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
REPORTS_DIR = Path("outputs/art_director_reports")
SUPPORTED   = {".jpg", ".jpeg", ".png"}
BATCH_SIZE  = 6


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


def _get_style_bible() -> str:
    """Read full style bible content."""
    path = OUTPUTS_DIR / "style_bible_and_shot_list.md"
    if not path.exists():
        return ""
    return path.read_text()


def _extract_section(
    content: str,
    section_name: str,
) -> str:
    """Extract a named section from the style bible."""
    match = re.search(
        rf"{section_name}.*?\n[═=]{{3,}}\n(.*?)"
        rf"(?=\n[═=]{{3,}}|\n##|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()
    return ""


def _review_batch(
    client: genai.Client,
    batch_files: list[Path],
    batch_index: int,
    total_batches: int,
    shoot_concept: str,
    technical_spec: str,
    mood_statement: str,
    all_previous_names: list[str],
) -> dict:
    """
    Review a batch of images for composition drift,
    lighting drift, and mood drift.
    Returns dict with per-image verdicts and
    batch-level observations.
    """
    parts_list = []

    # Load batch images
    batch_images = []
    for f in batch_files:
        img_bytes = f.read_bytes()
        mime = (
            "image/png" if f.suffix.lower() == ".png"
            else "image/jpeg"
        )
        batch_images.append((img_bytes, mime, f.name))
        parts_list.append(
            types.Part(
                inline_data=types.Blob(
                    mime_type=mime,
                    data=img_bytes,
                )
            )
        )

    batch_names = [f.name for f in batch_files]

    review_prompt = (
        "You are the Art Director for The Lunchbags, a lifestyle product "
        "brand photoshoot. You have a sharp creative eye "
        "and high standards for visual storytelling.\n\n"
        f"You are reviewing batch {batch_index + 1} of "
        f"{total_batches} from this shoot.\n\n"
        f"SHOOT CONCEPT:\n{shoot_concept}\n\n"
        f"TECHNICAL SPEC:\n{technical_spec}\n\n"
        f"MOOD STATEMENT:\n{mood_statement}\n\n"
        f"IMAGES IN THIS BATCH:\n"
        + "\n".join(
            f"IMAGE {i+1}: {name}"
            for i, name in enumerate(batch_names)
        ) +
        f"\n\nPREVIOUSLY REVIEWED IMAGES IN THIS SHOOT:\n"
        + (
            "\n".join(all_previous_names)
            if all_previous_names
            else "None — this is the first batch."
        ) +
        "\n\nReview each image in this batch against "
        "these three creative criteria:\n\n"
        "IMPORTANT — MULTI-SET SHOOT:\n"
        "This sprint is organised into 2-3 "
        "distinct sets. Each set has a different "
        "location, lighting setup, and mood. "
        "Differences between sets are INTENTIONAL "
        "and should NEVER be flagged as drift. "
        "Only flag drift within the same set — "
        "where images that should share a location "
        "and lighting language look inconsistent "
        "with each other.\n\n"
        "1. COMPOSITION DRIFT\n"
        "Does this image's composition feel too similar "
        "to others in this shoot? Check distance "
        "(close/medium/wide), angle (front/profile/"
        "top-down), and subject relationship (worn/"
        "only/held/context). Flag if: same distance "
        "AND angle as 2+ previous images, or if this "
        "batch has no variety across its own images.\n\n"
        "2. LIGHTING DRIFT\n"
        "Does the lighting in this image match the "
        "Technical Spec? Compare light direction, "
        "colour temperature, and shadow quality against "
        "the spec. Flag if: light comes from wrong "
        "direction, temperature is noticeably warmer "
        "or cooler than spec, shadows are wrong quality.\n\n"
        "3. MOOD DRIFT\n"
        "Does this image feel like it belongs to this "
        "shoot's concept and mood? Compare against the "
        "Shoot Concept and Mood Statement. Flag if: "
        "the energy feels wrong, the aesthetic has "
        "drifted, or the image could belong to a "
        "completely different brand.\n\n"
        "For each image respond PASS or FLAG with "
        "one sentence reason per criterion that fails.\n"
        "Then give OVERALL: PASS or FLAG.\n"
        "If FLAG: write a REGENERATION NOTE — one "
        "specific sentence describing what needs to "
        "change. This will be used by the Photo Editor "
        "as the fix instruction.\n\n"
        "After reviewing all images write a BATCH "
        "OBSERVATION — 2-3 sentences on the overall "
        "creative health of this batch and any pattern "
        "you notice across the shoot so far.\n\n"
        "Respond in EXACTLY this format:\n\n"
        + "\n".join(
            f"IMAGE {i+1} ({name}):\n"
            f"COMPOSITION DRIFT: PASS/FLAG — reason\n"
            f"LIGHTING DRIFT: PASS/FLAG — reason\n"
            f"MOOD DRIFT: PASS/FLAG — reason\n"
            f"OVERALL: PASS or FLAG\n"
            f"REGENERATION NOTE: [note or 'none needed']"
            for i, name in enumerate(batch_names)
        ) +
        "\n\nBATCH OBSERVATION: [2-3 sentences]"
    )

    parts_list.append(types.Part(text=review_prompt))

    response = client.models.generate_content(
        model="gemini-2.5-pro",
        contents=[
            types.Content(role="user", parts=parts_list)
        ],
    )

    result_text = response.text.strip()

    # Parse per-image verdicts
    image_verdicts = {}
    for i, name in enumerate(batch_names):
        search  = f"IMAGE {i+1} ({name}):"
        overall = "PASS"
        regen_note = "none needed"

        lines = result_text.splitlines()
        in_block = False
        for line in lines:
            if search.upper() in line.upper():
                in_block = True
            if in_block:
                if "OVERALL:" in line.upper():
                    overall = (
                        "FLAG"
                        if "FLAG" in line.upper()
                        else "PASS"
                    )
                if "REGENERATION NOTE:" in line.upper():
                    regen_note = (
                        line.split(":", 1)[-1].strip()
                    )
                    if regen_note.lower() == "none needed":
                        regen_note = ""
                    in_block = False
                    break

        image_verdicts[name] = {
            "overall":    overall,
            "regen_note": regen_note,
        }

    # Extract batch observation
    batch_obs = ""
    for line in result_text.splitlines():
        if "BATCH OBSERVATION:" in line.upper():
            batch_obs = line.split(":", 1)[-1].strip()
            break

    return {
        "verdicts":          image_verdicts,
        "batch_observation": batch_obs,
        "full_review":       result_text,
    }


class ArtDirectorTool(BaseTool):
    name: str = "The Lunchbags Art Director"
    description: str = """
        Reviews all approved images from the Photo Editor
        as an Art Director — checking for composition drift,
        lighting drift, and mood drift across the full shoot.

        Reviews images in batches of 6, building awareness
        of the full shoot as it progresses.

        Flags images that drift creatively and writes a
        specific regeneration note for each flagged image.
        The Photo Editor uses these notes as fix instructions.

        Does NOT fix images — flags only.
        Flagged images are renamed with 'Art Review-' prefix.

        No input required — call with an empty string.

        Output: full Art Direction report with per-image
        verdicts, batch observations, and summary.
    """

    def _run(self, _: str = "") -> str:
        try:
            client = genai.Client(
                api_key=os.getenv("GEMINI_API_KEY")
            )

            # ── Load style bible ──────────────────────────
            style_bible   = _get_style_bible()
            shoot_concept = _extract_section(
                style_bible, "SHOOT DNA"
            )
            technical_spec = _extract_section(
                style_bible, "TECHNICAL SPEC"
            )
            mood_statement = _extract_section(
                style_bible, "MOOD IN ONE SENTENCE"
            )

            if not style_bible:
                return (
                    "TOOL_ERROR: Style bible not found at "
                    "outputs/"
                    "style_bible_and_shot_list.md"
                )

            # ── Load images to review ─────────────────────
            # Only review images that passed Photo Editor
            # Skip anything with Needs Review or Art Review prefix
            review_files = sorted([
                f for f in _get_asset_dir().iterdir()
                if f.is_file()
                and f.suffix.lower() in SUPPORTED
                and "Needs Review-" not in f.name
                and "Art Review-" not in f.name
                and "TEST-" not in f.name
            ])

            if not review_files:
                return "No approved images found to review."

            total         = len(review_files)
            flagged       = 0
            passed        = 0
            all_results   = []
            reviewed_names = []
            batch_observations = []

            # ── Review in batches ─────────────────────────
            batches = [
                review_files[i:i + BATCH_SIZE]
                for i in range(0, total, BATCH_SIZE)
            ]
            total_batches = len(batches)

            for batch_idx, batch in enumerate(batches):
                print(
                    f"\n[ArtDirector] Reviewing batch "
                    f"{batch_idx + 1}/{total_batches} "
                )

                result = _review_batch(
                    client,
                    batch,
                    batch_idx,
                    total_batches,
                    shoot_concept,
                    technical_spec,
                    mood_statement,
                    reviewed_names,
                )

                if result["batch_observation"]:
                    batch_observations.append(
                        f"Batch {batch_idx + 1}: "
                        f"{result['batch_observation']}"
                    )

                for f in batch:
                    name    = f.name
                    verdict = result["verdicts"].get(
                        name, {"overall": "PASS", "regen_note": ""}
                    )

                    if verdict["overall"] == "FLAG":
                        # Rename with Art Review- prefix
                        new_name = f"Art Review-{name}"
                        new_path = f.parent / new_name
                        f.rename(new_path)
                        flagged += 1
                        print(
                            f"[ArtDirector] ✗ FLAGGED: "
                            f"{new_name}\n"
                            f"  Note: {verdict['regen_note']}"
                        )
                        all_results.append({
                            "file":      new_name,
                            "status":    "FLAGGED",
                            "regen_note": verdict["regen_note"],
                        })
                    else:
                        passed += 1
                        print(
                            f"[ArtDirector] ✓ PASS: {name}"
                        )
                        all_results.append({
                            "file":   name,
                            "status": "PASS",
                        })

                    reviewed_names.append(name)

            # ── Build report ──────────────────────────────
            now      = datetime.now().strftime("%Y-%m-%d %H:%M")
            pass_pct = round(
                (passed / total) * 100
            ) if total else 0

            report = (
                f"# ART DIRECTION REPORT — THE LUNCHBAGS\n"
                f"Run: {now}\n\n"
                f"{'='*50}\n"
                f"## SUMMARY\n"
                f"Total reviewed:       {total}\n"
                f"Passed:               {passed} ({pass_pct}%)\n"
                f"Flagged for rework:   {flagged}\n"
                f"{'='*50}\n\n"
                f"## BATCH OBSERVATIONS\n\n"
            )

            for obs in batch_observations:
                report += f"- {obs}\n"

            report += f"\n{'='*50}\n\n## PER IMAGE RESULTS\n\n"

            for r in all_results:
                icon = "✓" if r["status"] == "PASS" else "✗"
                report += f"{icon} {r['status']} | {r['file']}\n"
                if r["status"] == "FLAGGED":
                    report += (
                        f"  REGENERATION NOTE: "
                        f"{r['regen_note']}"
                    )
                report += "\n"

            if flagged > 0:
                flagged_files = [
                    r for r in all_results
                    if r["status"] == "FLAGGED"
                ]
                report += (
                    f"{'='*50}\n"
                    f"## FLAGGED FOR REWORK\n"
                    f"These files have been renamed with "
                    f"'Art Review-' prefix.\n"
                    f"The Photo Editor should use the "
                    f"REGENERATION NOTE as the fix instruction.\n\n"
                )
                for r in flagged_files:
                    report += (
                        f"- {r['file']}\n"
                        f"  → {r['regen_note']}\n\n"
                    )

            # ── Save reports ──────────────────────────────
            REPORTS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp   = datetime.now().strftime("%Y%m%d_%H%M")
            report_path = REPORTS_DIR / f"art_direction_{timestamp}.md"
            report_path.write_text(report)

            latest = Path(
                "outputs/"
                "art_director_latest.md"
            )
            latest.write_text(report)

            return report

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
