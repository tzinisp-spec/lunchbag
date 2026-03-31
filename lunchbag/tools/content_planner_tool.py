import os
import json
from pathlib import Path
from datetime import datetime, timedelta
from crewai.tools import BaseTool

OUTPUTS_DIR   = Path("outputs")
COPY_PATH     = OUTPUTS_DIR / "copy_latest.json"
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

# 5 posts per week
# 3 carousels + 2 singles
# Mon=0 Tue=1 Thu=3 Fri=4 Sat=5
WEEKLY_SLOTS = [
    {"day": 0, "time": "19:00", "type": "carousel"},
    {"day": 1, "time": "09:00", "type": "single"},
    {"day": 3, "time": "19:00", "type": "carousel"},
    {"day": 4, "time": "09:00", "type": "single"},
    {"day": 5, "time": "19:00", "type": "carousel"},
]


def _load_catalog() -> list[dict]:
    catalog_path = _get_catalog_path()
    if not catalog_path.exists():
        return []
    try:
        data = json.loads(catalog_path.read_text())
        images = data.get("images", [])
        for img in images:
            if not img.get("ref_code") and img.get("id"):
                img["ref_code"] = img["id"]
        return images
    except Exception:
        return []


def _load_copy() -> dict:
    if not COPY_PATH.exists():
        return {}
    try:
        data  = json.loads(COPY_PATH.read_text())
        index = {}
        for item in data.get("copy", []):
            index[item["ref_code"]] = item
        return index
    except Exception:
        return {}


def _load_calendar() -> dict:
    if not CALENDAR_PATH.exists():
        return {}
    try:
        return json.loads(CALENDAR_PATH.read_text())
    except Exception:
        return {}


def _get_latest_sprint(images: list[dict]) -> str:
    sprints = list({
        img.get("sprint", "") for img in images
    })
    sprints = [s for s in sprints if s]
    return sorted(sprints)[-1] if sprints else ""


def _get_next_monday() -> datetime:
    today      = datetime.now()
    days_ahead = 7 - today.weekday()
    if days_ahead == 7:
        days_ahead = 0
    return today + timedelta(
        days=days_ahead if days_ahead else 7
    )


def _get_planning_start() -> datetime:
    """Return the first Monday of the target planning month.
    Reads PLANNING_MONTH env var (format: YYYY-MM).
    Falls back to next Monday from today if not set.
    """
    planning_month = os.getenv("PLANNING_MONTH", "").strip()
    if planning_month:
        try:
            year, month = map(int, planning_month.split("-"))
            first_day = datetime(year, month, 1)
            # days until first Monday (0 = Monday)
            days_to_monday = (0 - first_day.weekday()) % 7
            return first_day + timedelta(days=days_to_monday)
        except (ValueError, AttributeError):
            pass
    return _get_next_monday()


def _get_planning_month_num() -> int:
    """Return the target planning month number (1–12).
    Reads PLANNING_MONTH env var (format: YYYY-MM).
    Falls back to current month.
    """
    planning_month = os.getenv("PLANNING_MONTH", "").strip()
    if planning_month:
        try:
            return int(planning_month.split("-")[1])
        except (ValueError, IndexError):
            pass
    return datetime.now().month


def _get_set_number(ref_code: str) -> str:
    """Extract set number from ref_code e.g. S1, S2."""
    import re
    match = re.search(r"S(\d+)", ref_code)
    return match.group(1) if match else "1"


def _is_holiday(
    date: datetime, calendar: dict
) -> bool:
    date_str = date.strftime("%m-%d")
    for h in calendar.get("holidays", []):
        if (h["date"] == date_str
                and h.get("posting") == "pause"):
            return True
    return False


def _get_seasonal_note(calendar: dict) -> str:
    month = _get_planning_month_num()
    for s in calendar.get("seasons", []):
        if month in s.get("months", []):
            return s.get("tone", "")
    return ""


def _group_by_set(
    images: list[dict],
) -> dict[str, list]:
    """Group images by their set number."""
    sets: dict[str, list] = {}
    for img in images:
        ref = img.get("ref_code", "")
        s   = _get_set_number(ref)
        if s not in sets:
            sets[s] = []
        sets[s].append(img)
    return sets


def _build_carousels(
    sets: dict[str, list],
    copy_index: dict,
    max_per_carousel: int = 4,
) -> list[dict]:
    """
    Build carousel posts from sets.
    Each carousel = images from same set.
    One caption written for the whole carousel.
    """
    carousels = []
    for set_num, images in sorted(sets.items()):
        # Take up to max_per_carousel images
        slides = images[:max_per_carousel]
        if not slides:
            continue

        # Use copy from first image as carousel caption
        # or best caption from the set
        caption  = ""
        hashtags = []
        for img in slides:
            ref  = img.get("ref_code", "")
            copy = copy_index.get(ref, {})
            if copy.get("caption"):
                caption  = copy["caption"]
                hashtags = copy.get("hashtags", [])
                break

        carousels.append({
            "type":     "carousel",
            "set":      set_num,
            "slides":   [
                {
                    "ref_code": img.get("ref_code", ""),
                    "filename": img.get("filename", ""),
                }
                for img in slides
            ],
            "caption":  caption,
            "hashtags": hashtags,
        })

    return carousels


def _build_singles(
    images: list[dict],
    copy_index: dict,
    used_refs: set,
) -> list[dict]:
    """
    Build single image posts from images
    not already used in carousels.
    Prefer HERO and DETAIL shots.
    """
    singles = []
    priority = ["HERO", "DETAIL", "ATMOSPHERE",
                "PARTIAL", "MOTION"]

    remaining = [
        img for img in images
        if img.get("ref_code") not in used_refs
    ]

    # Sort by priority category
    def sort_key(img):
        ref = img.get("ref_code", "").upper()
        for i, cat in enumerate(priority):
            if cat in ref:
                return i
        return len(priority)

    remaining.sort(key=sort_key)

    for img in remaining:
        ref  = img.get("ref_code", "")
        copy = copy_index.get(ref, {})
        singles.append({
            "type":     "single",
            "ref_code": ref,
            "filename": img.get("filename", ""),
            "caption":  copy.get("caption", ""),
            "hashtags": copy.get("hashtags", []),
        })

    return singles


class ContentPlannerTool(BaseTool):
    name: str        = "Lunchbags Content Planner"
    description: str = """
        Builds a full 4-week monthly posting
        calendar for The Lunchbags Instagram.

        5 posts per week — 20 posts total:
        - 3 carousel posts per week (images from
          same set grouped together, 2-4 slides)
        - 2 single image posts per week

        Schedule: Mon/Thu/Sat carousels at 19:00
        Tue/Fri singles at 09:00

        Checks Greek holiday calendar.

        Saves to:
        outputs/monthly_calendar.json
        outputs/monthly_calendar.md

        No input required — call with empty string.
    """

    def _run(self, _: str = "") -> str:
        try:
            images = _load_catalog()
            if not images:
                return "TOOL_ERROR: catalog.json empty."

            copy_index    = _load_copy()
            calendar      = _load_calendar()
            latest_sprint = _get_latest_sprint(images)

            sprint_images = [
                img for img in images
                if img.get("sprint") == latest_sprint
                and img.get("status") != "pending"
            ]

            if len(sprint_images) < 5:
                return (
                    f"TOOL_ERROR: Only "
                    f"{len(sprint_images)} images "
                    f"in sprint."
                )

            sets      = _group_by_set(sprint_images)
            carousels = _build_carousels(
                sets, copy_index
            )

            used_refs = set()
            for c in carousels:
                for slide in c["slides"]:
                    used_refs.add(slide["ref_code"])

            singles = _build_singles(
                sprint_images, copy_index, used_refs
            )

            # Build 4-week calendar
            next_monday   = _get_planning_start()
            seasonal_note = _get_seasonal_note(calendar)
            all_posts     = []
            carousel_pool = list(carousels)
            single_pool   = list(singles)
            slot_num      = 0

            for week in range(4):
                week_start = next_monday + timedelta(
                    weeks=week
                )

                for slot in WEEKLY_SLOTS:
                    post_date = week_start + timedelta(
                        days=slot["day"]
                    )

                    # Skip holidays
                    if _is_holiday(post_date, calendar):
                        post_date += timedelta(days=1)

                    slot_num += 1

                    if slot["type"] == "carousel":
                        if carousel_pool:
                            # Cycle through carousels
                            idx  = (slot_num - 1) % len(
                                carousel_pool
                            )
                            post = dict(carousel_pool[idx])
                        else:
                            # Fallback to single
                            post = (
                                single_pool.pop(0)
                                if single_pool
                                else {"type": "single",
                                      "ref_code": "",
                                      "caption": "",
                                      "hashtags": []}
                            )
                    else:
                        post = (
                            single_pool.pop(0)
                            if single_pool
                            else {"type": "single",
                                  "ref_code": "",
                                  "caption": "",
                                  "hashtags": []}
                        )

                    all_posts.append({
                        "slot":  slot_num,
                        "week":  week + 1,
                        "date":  post_date.strftime(
                            "%Y-%m-%d"
                        ),
                        "day":   post_date.strftime(
                            "%A"
                        ),
                        "time":  slot["time"],
                        **post,
                    })

            # Save JSON
            output = {
                "sprint":        latest_sprint,
                "month_of":      next_monday.strftime(
                    "%B %Y"
                ),
                "seasonal_note": seasonal_note,
                "generated":     datetime.now().isoformat(),
                "total_posts":   len(all_posts),
                "posts":         all_posts,
            }

            OUTPUTS_DIR.mkdir(
                parents=True, exist_ok=True
            )

            json_path = (
                OUTPUTS_DIR / "monthly_calendar.json"
            )
            json_path.write_text(
                json.dumps(
                    output, indent=2,
                    ensure_ascii=False
                )
            )

            # Save Markdown
            md = (
                f"# Monthly Content Calendar\n\n"
                f"**Sprint:** {latest_sprint}\n"
                f"**Month:** "
                f"{next_monday.strftime('%B %Y')}\n"
                f"**Seasonal tone:** {seasonal_note}\n"
                f"**Total posts:** {len(all_posts)}\n\n"
            )

            for week_num in range(1, 5):
                week_posts = [
                    p for p in all_posts
                    if p["week"] == week_num
                ]
                md += f"## Week {week_num}\n\n"
                for post in week_posts:
                    if post["type"] == "carousel":
                        slides_str = ", ".join([
                            s["ref_code"]
                            for s in post.get(
                                "slides", []
                            )
                        ])
                        md += (
                            f"**Slot {post['slot']}** — "
                            f"{post['day']} "
                            f"{post['date']} "
                            f"{post['time']} "
                            f"| CAROUSEL (Set "
                            f"{post.get('set','')})\n"
                            f"Slides: {slides_str}\n"
                            f"Caption: {post['caption']}"
                            f"\n\n"
                        )
                    else:
                        md += (
                            f"**Slot {post['slot']}** — "
                            f"{post['day']} "
                            f"{post['date']} "
                            f"{post['time']} "
                            f"| SINGLE\n"
                            f"Image: {post.get('ref_code','')}\n"
                            f"Caption: {post['caption']}"
                            f"\n\n"
                        )

            md_path = OUTPUTS_DIR / "monthly_calendar.md"
            md_path.write_text(md, encoding="utf-8")

            summary = (
                f"MONTHLY CALENDAR COMPLETE\n"
                f"Sprint: {latest_sprint}\n"
                f"Month: "
                f"{next_monday.strftime('%B %Y')}\n"
                f"Total posts: {len(all_posts)}\n"
                f"Carousels: "
                f"{len([p for p in all_posts if p['type']=='carousel'])}\n"
                f"Singles: "
                f"{len([p for p in all_posts if p['type']=='single'])}\n"
                f"Saved: outputs/monthly_calendar.md\n"
            )

            return summary

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
