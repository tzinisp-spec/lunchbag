import os
import json
import base64
from pathlib import Path
from datetime import datetime
from google import genai
from google.genai import types
from crewai.tools import BaseTool

SUPPORTED     = {".jpg", ".jpeg", ".png"}
OUTPUTS_DIR   = Path("outputs")
STRATEGY_PATH = Path("brand/copy_strategy.md")
CALENDAR_PATH = Path("brand/greek_calendar.json")


def _get_catalog_path() -> Path:
    shoot_folder = os.getenv("SHOOT_FOLDER", "")
    if shoot_folder:
        return (
            Path("asset_library/images")
            / shoot_folder
            / "catalog.json"
        )
    return Path("asset_library/catalog.json")


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


def _load_catalog() -> list[dict]:
    catalog_path = _get_catalog_path()
    if not catalog_path.exists():
        return []
    try:
        data = json.loads(catalog_path.read_text())
        images = data.get("images", [])
        # Normalise id -> ref_code
        for img in images:
            if not img.get("ref_code") and img.get("id"):
                img["ref_code"] = img["id"]
        return images
    except Exception:
        return []


def _get_latest_sprint(images: list[dict]) -> str:
    sprints = list({
        img.get("sprint", "") for img in images
    })
    sprints = [s for s in sprints if s]
    return sorted(sprints)[-1] if sprints else ""


def _get_seasonal_context() -> str:
    """Get current seasonal context from calendar."""
    try:
        if not CALENDAR_PATH.exists():
            return ""
        cal   = json.loads(CALENDAR_PATH.read_text())
        month = datetime.now().month
        for season in cal.get("seasons", []):
            if month in season.get("months", []):
                return (
                    f"Current season: {season['name']}. "
                    f"Seasonal food context: "
                    f"{season['food_note']}. "
                    f"Tone direction: {season['tone']}."
                )
    except Exception:
        pass
    return ""


def _detect_pillar(shot_category: str) -> str:
    """Map shot category to content pillar."""
    mapping = {
        "HERO":        "PRODUCT SHOWCASE",
        "DETAIL":      "PRODUCT SHOWCASE",
        "PROPS":       "PRODUCT SHOWCASE",
        "MODEL":       "LIFESTYLE MOMENT",
        "PARTIAL":     "LIFESTYLE MOMENT",
        "INTERACTION": "LIFESTYLE MOMENT",
        "MOTION":      "LIFESTYLE MOMENT",
        "ATMOSPHERE":  "LIFESTYLE MOMENT",
        "OPEN":        "FOOD INSPIRATION",
        "UNPACK":      "FOOD INSPIRATION",
    }
    return mapping.get(
        shot_category.upper(), "LIFESTYLE MOMENT"
    )


def _load_strategy() -> str:
    if not STRATEGY_PATH.exists():
        return ""
    return STRATEGY_PATH.read_text()


def _write_caption(
    client: genai.Client,
    image_bytes: bytes,
    ref_code: str,
    strategy: str,
    seasonal_context: str,
) -> dict:
    """
    Two-step process:
    1. Analyse the image composition deeply
    2. Write a specific caption based on analysis
    """
    try:
        # STEP 1 — Deep composition analysis
        analysis_prompt = (
            "Analyse this product image carefully "
            "and return ONLY a JSON object.\n\n"
            "Look at:\n"
            "- What is the main subject "
            "(bag only, person with bag, "
            "food being unpacked, hands only, "
            "wide scene, close-up detail etc.)\n"
            "- How many people are visible "
            "and what are they doing\n"
            "- What food or drink is visible "
            "if any — be specific\n"
            "- What setting or environment\n"
            "- What bag details are prominent "
            "(pattern, texture, hardware, "
            "opening mechanism)\n"
            "- What is the mood or energy "
            "of the image\n"
            "- What shot type best describes it:\n"
            "  PRODUCT SHOWCASE: bag is hero, "
            "minimal context, pattern/details "
            "prominent\n"
            "  LIFESTYLE MOMENT: person with bag "
            "in a relatable everyday situation\n"
            "  FOOD INSPIRATION: food is prominent, "
            "bag is context\n"
            "  DETAIL: extreme close-up of texture, "
            "pattern, or hardware\n"
            "  SOCIAL: two or more people visible\n"
            "  MOTION: movement, action, energy\n"
            "  ATMOSPHERE: wide shot, setting "
            "dominant\n\n"
            "Return ONLY this JSON:\n"
            "{\n"
            '  "shot_type": "one of the above",\n'
            '  "pillar": "matching content pillar",\n'
            '  "subject": "what is the main '
            'subject in one sentence",\n'
            '  "details": "specific visual '
            'details — food items, bag pattern '
            'name if visible, setting name, '
            'person action",\n'
            '  "mood": "one or two words",\n'
            '  "copy_angle": "what this image '
            'is best suited to communicate — '
            'one sentence"\n'
            "}\n\n"
            "Return ONLY the JSON. No other text."
        )

        analysis_response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="image/png",
                                data=image_bytes,
                            )
                        ),
                        types.Part(
                            text=analysis_prompt
                        ),
                    ],
                )
            ],
        )

        # Parse analysis
        analysis_text = analysis_response.text.strip()
        analysis_text = analysis_text.replace(
            "```json", ""
        ).replace("```", "").strip()

        try:
            analysis = json.loads(analysis_text)
        except Exception:
            analysis = {
                "shot_type": "LIFESTYLE MOMENT",
                "pillar":    "LIFESTYLE MOMENT",
                "subject":   "bag in lifestyle context",
                "details":   "",
                "mood":      "warm",
                "copy_angle": "relatable everyday moment",
            }

        pillar     = analysis.get(
            "pillar", "LIFESTYLE MOMENT"
        )
        details    = analysis.get("details", "")
        mood       = analysis.get("mood", "")
        copy_angle = analysis.get("copy_angle", "")
        shot_type  = analysis.get("shot_type", "")

        print(
            f"[Copywriter] Analysis: {shot_type} "
            f"| {mood} | {details[:50]}"
        )

        # STEP 2 — Write caption using analysis
        caption_prompt = (
            f"You are a social media copywriter "
            f"for The Lunchbags, a Greek brand "
            f"making cotton thermal lunch bags.\n\n"
            f"BRAND VOICE & STRATEGY:\n"
            f"{strategy}\n\n"
            f"SEASONAL CONTEXT (inform tone subtly, "
            f"never mention directly):\n"
            f"{seasonal_context}\n\n"
            f"CONTENT PILLAR: {pillar}\n"
            f"SHOT TYPE: {shot_type}\n"
            f"IMAGE DETAILS: {details}\n"
            f"MOOD: {mood}\n"
            f"COPY ANGLE: {copy_angle}\n\n"
            f"Before writing anything, read the "
            f"image carefully and answer these "
            f"questions internally:\n"
            f"- How many people are in the image?\n"
            f"- What are they doing?\n"
            f"- What is the mood — relaxed, rushed, "
            f"joyful, focused, casual?\n"
            f"- Is this a solo moment or a shared "
            f"one?\n"
            f"- What food or drink is visible?\n"
            f"- What does the setting suggest about "
            f"the time of day or occasion?\n\n"
            f"Then write a caption that responds "
            f"to what you see:\n\n"
            f"SCENE RULES:\n"
            f"- Solo person: speak to them directly "
            f"— their routine, their choice, their "
            f"small daily win.\n"
            f"- Two people: the caption should feel "
            f"like it's about sharing, company, "
            f"friendship — 'μαζί' energy. Reference "
            f"the social moment without being "
            f"obvious about it.\n"
            f"- Group or gathering: warmth, "
            f"togetherness, the pleasure of eating "
            f"well with people you like.\n"
            f"- No people, product only: let the "
            f"bag and its print speak — the caption "
            f"can be more poetic or product-focused.\n"
            f"- Food being unpacked or handled: "
            f"focus on the anticipation, the smell, "
            f"the moment before eating.\n\n"
            f"The caption must feel like a natural "
            f"reaction to this specific image — "
            f"not a generic product description. "
            f"If someone covered the image and read "
            f"the caption, they should be able to "
            f"roughly picture what's in the photo.\n\n"
            f"Write EXACTLY in this format:\n\n"
            f"CAPTION:\n"
            f"[1-2 sentences in Greek. "
            f"Specific to this image. "
            f"2-3 emojis woven naturally. "
            f"No Greeklish. No formal Greek. "
            f"No diet talk. No preaching.]\n\n"
            f"HASHTAGS:\n"
            f"[25 hashtags. Mix Greek and English. "
            f"Always include: #thelunchbags "
            f"#takeyourluncheverywhere "
            f"#lunchbag #τσαντακιφαγητου "
            f"#σπιτικοφαγητο "
            f"Plus specific tags for this image. "
            f"One per line.]\n\n"
            f"Return ONLY CAPTION and HASHTAGS."
        )

        caption_response = client.models.generate_content(
            model="gemini-2.5-pro",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part(
                            inline_data=types.Blob(
                                mime_type="image/png",
                                data=image_bytes,
                            )
                        ),
                        types.Part(
                            text=caption_prompt
                        ),
                    ],
                )
            ],
        )

        text = caption_response.text.strip()
        caption  = ""
        hashtags = []

        if "CAPTION:" in text:
            parts   = text.split("HASHTAGS:")
            caption = parts[0].replace(
                "CAPTION:", ""
            ).strip()
            if len(parts) > 1:
                hashtag_lines = parts[1].strip().splitlines()
                hashtags = [
                    h.strip()
                    for h in hashtag_lines
                    if h.strip().startswith("#")
                ]

        return {
            "ref_code":   ref_code,
            "pillar":     pillar,
            "shot_type":  shot_type,
            "mood":       mood,
            "details":    details,
            "copy_angle": copy_angle,
            "caption":    caption,
            "hashtags":   hashtags,
            "written_at": datetime.now().isoformat(),
        }

    except Exception as e:
        print(f"[Copywriter] Error on {ref_code}: {e}")
        return {
            "ref_code": ref_code,
            "pillar":   "LIFESTYLE MOMENT",
            "caption":  "",
            "hashtags": [],
            "error":    str(e),
        }


class CopywriterTool(BaseTool):
    name: str        = "Lunchbags Copywriter"
    description: str = """
        Writes Instagram copy for all approved
        images in the most recent sprint.

        For each image reads the Brand Voice Guide
        and Greek seasonal calendar, analyses the
        image with Gemini Vision, and writes:
        - 1-2 sentence Greek caption with emojis
        - 25 relevant hashtags

        Saves results to outputs/copy_latest.json

        No input required — call with empty string.
    """

    def _run(self, _: str = "") -> str:
        try:
            client = genai.Client(
                api_key=os.getenv("GEMINI_API_KEY")
            )

            images = _load_catalog()
            if not images:
                return (
                    "TOOL_ERROR: catalog.json "
                    "not found or empty."
                )

            latest_sprint = _get_latest_sprint(images)
            if not latest_sprint:
                return (
                    "TOOL_ERROR: No sprint found "
                  "in catalog."
                )

            sprint_images = [
                img for img in images
                if img.get("sprint") == latest_sprint
                and img.get("status") != "pending"
            ]

            strategy         = _load_strategy()
            seasonal_context = _get_seasonal_context()

            print(
                f"\n[Copywriter] Sprint: "
                f"{latest_sprint}\n"
                f"[Copywriter] Season: "
                f"{seasonal_context[:60]}...\n"
                f"[Copywriter] Writing copy for "
                f"{len(sprint_images)} images..."
            )

            asset_dir = _get_asset_dir()
            results   = []
            success   = 0
            failed    = 0

            for img in sprint_images:
                ref_code = img.get("ref_code", "")
                filename = img.get("filename", "")

                img_path = asset_dir / filename
                if not img_path.exists():
                    matches = list(
                        Path("asset_library/images")
                        .rglob(filename)
                    )
                    if matches:
                        img_path = matches[0]
                    else:
                        print(
                            f"[Copywriter] "
                            f"Not found: {filename}"
                        )
                        failed += 1
                        continue

                print(
                    f"[Copywriter] {ref_code} "
                    f"({_detect_pillar(img.get('shot_category', ''))})"
                )

                image_bytes = img_path.read_bytes()
                copy = _write_caption(
                    client,
                    image_bytes,
                    ref_code,
                    strategy,
                    seasonal_context,
                )

                results.append(copy)
                if copy.get("caption"):
                    success += 1
                    print(
                        f"[Copywriter] ✓ "
                        f"{copy['pillar']}"
                    )
                else:
                    failed += 1

            output = {
                "sprint":    latest_sprint,
                "season":    seasonal_context,
                "generated": datetime.now().isoformat(),
                "total":     len(results),
                "copy":      results,
            }

            OUTPUTS_DIR.mkdir(
                parents=True, exist_ok=True
            )
            out_path = OUTPUTS_DIR / "copy_latest.json"
            out_path.write_text(
                json.dumps(
                    output, indent=2,
                    ensure_ascii=False
                )
            )

            return (
                f"COPY COMPLETE\n"
                f"Sprint: {latest_sprint}\n"
              f"Season: {seasonal_context[:50]}\n"
                f"Written: {success}/"
                f"{len(sprint_images)}\n"
                f"Failed: {failed}\n"
                f"Saved: outputs/copy_latest.json\n"
            )

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
