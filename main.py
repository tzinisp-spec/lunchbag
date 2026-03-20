import os
from datetime import date
from dotenv import load_dotenv
from lunchbag.crew import LunchbagCrew
from lunchbag.trend_crew import LunchbagTrendCrew

load_dotenv()

INPUTS = {
    "brand_name":        "The Lunchbags",
    "current_season":    "Spring 2026",
    "client_code":       "lunchbag",
    "shoot_month":       "03",
    "shoot_day":         "20",
    "product_focus":     "Original thermal lunch bag — cotton exterior, waterproof interior, Thermo Hot&Cold mechanism, H21cm x W16cm x D24cm, various prints and colours",
    "product_materials": "Cotton exterior, waterproof interior lining, thermal insulation, fabric straps. Surface has a soft textile feel — not leather, not plastic, not glossy. Bold graphic prints on cotton.",
    "target_audience":   "Women and men 25-45, Greece and Europe, active lifestyle, health-conscious, daily commuters, parents, office workers, anyone who carries food on the go",
    "content_mix":       "35% bag in use — carried or held by model, 25% product only — bag on surface, 20% detail close-up — print texture and materials, 15% lifestyle context — food preparation or outdoor setting, 5% flat lay — bag open showing interior",
    "posts_per_week":    "5",
    "images_per_sprint": "10",
    "shoot_dont_list":   "No artificial clinical lighting, no white studio backgrounds, no images that make the bag look cheap or disposable",
    "imagen_style_anchor": "High-end lifestyle photography, 8k resolution, photorealistic, cinematic lighting.",
    "current_date":      date.today().strftime("%B %d, %Y"),
}

def run_trend_scout():
    """Run the Trend Scout only — once per month."""
    os.makedirs("trends", exist_ok=True)
    print("\n" + "="*60)
    print("  ORPINA — TREND SCOUT")
    print("="*60 + "\n")

    LunchbagTrendCrew().crew().kickoff(inputs=INPUTS)

    print("\n" + "="*60)
    print("  DONE: trends/latest_trends.md")
    print("="*60 + "\n")

def run():
    """Run the monthly creative sprint."""
    os.makedirs("outputs",              exist_ok=True)
    os.makedirs("memory",               exist_ok=True)
    os.makedirs("asset_library/images", exist_ok=True)
    os.makedirs("references",           exist_ok=True)

    # ── Compute shoot metadata ──────────────────────
    import datetime
    season_code = INPUTS.get(
        "current_season", "SPR-26"
    ).replace(" ", "-").upper()[:6]
    client      = INPUTS.get("client_code", "client")
    month       = INPUTS.get("shoot_month", "01")
    day         = INPUTS.get("shoot_day", "01")
    year        = INPUTS.get(
        "current_season", "2026"
    ).split()[-1][2:]

    # Convert numeric month to uppercase name for folder
    try:
        month_name = datetime.date(2000, int(month), 1).strftime('%B').upper()
    except ValueError:
        month_name = month.upper()

    shoot_id = (
        f"{client}-{season_code}-{year}-{month}-{day}"
    )
    shoot_folder = f"{month_name}{year}"

    INPUTS["shoot_id"]     = shoot_id
    INPUTS["shoot_folder"] = shoot_folder

    print(f"Shoot ID: {shoot_id}")
    print(f"Shoot folder: asset_library/images/{shoot_folder}/")

    # ── Check references are in place ────────────────
    ref_dir = "references"
    ref_images = [
        f for f in os.listdir(ref_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ] if os.path.exists(ref_dir) else []

    if not ref_images:
        print("\n" + "="*60)
        print("  ⚠  MISSING: No reference images found")
        print(f"  Add at least one image to {ref_dir}/")
        print("  Any filename is accepted.")
        print("="*60 + "\n")
        return

    print(f"  ✓ References: {len(ref_images)} image(s) found")

    print("\n" + "="*60)
    print("  ORPINA — MONTHLY CREATIVE SPRINT")
    print("="*60 + "\n")

    os.environ["SHOOT_ID"]     = shoot_id
    os.environ["SHOOT_FOLDER"] = shoot_folder

    LunchbagCrew().run_with_report(inputs=INPUTS)

    print("\n" + "="*60)
    print("  SPRINT COMPLETE")
    print("  Outputs: outputs/")
    print(f"  Images: asset_library/images/{shoot_folder}/")
    print("="*60 + "\n")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--trends":
        run_trend_scout()
    else:
        run()
