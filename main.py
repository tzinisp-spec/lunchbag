import os
from datetime import date
from dotenv import load_dotenv
from lunchbag.crew import LuanchbagCrew
from lunchbag.trend_crew import LuanchbagTrendCrew

load_dotenv()

INPUTS = {
    "brand_name":        "Luanchbag",
    "current_season":    "Spring 2026",
    "product_focus":     "TBD — add products to products/ folder",
    "earring_materials": "TBD — describe product materials here",
    "target_audience":   "TBD — describe target audience here",
    "content_mix":       "40% worn on model, 25% product only, 20% detail close-up, 10% lifestyle context, 5% held or handled",
    "posts_per_week":    "5",
    "images_per_sprint": "10",
    "shoot_dont_list":   "TBD — add restrictions here",
}

def run_trend_scout():
    """Run the Trend Scout only — once per month."""
    os.makedirs("trends", exist_ok=True)
    print("\n" + "="*60)
    print("  ORPINA — TREND SCOUT")
    print("="*60 + "\n")

    LuanchbagTrendCrew().crew().kickoff(inputs=INPUTS)

    print("\n" + "="*60)
    print("  DONE: trends/latest_trends.md")
    print("="*60 + "\n")

def run():
    """Run the monthly creative sprint."""
    os.makedirs("outputs",              exist_ok=True)
    os.makedirs("memory",               exist_ok=True)
    os.makedirs("asset_library/images", exist_ok=True)
    os.makedirs("references",           exist_ok=True)

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
    print("  Human checkpoints: 2")
    print("  Checkpoint 1: Creative Brief approval")
    print("  Checkpoint 2: Final package approval")
    print("="*60 + "\n")

    LuanchbagCrew().crew().kickoff(inputs=INPUTS)

    print("\n" + "="*60)
    print("  SPRINT COMPLETE")
    print("  Outputs: outputs/")
    print("  Images: asset_library/images/")
    print("="*60 + "\n")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--trends":
        run_trend_scout()
    else:
        run()
