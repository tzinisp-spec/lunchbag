import os
from datetime import date
from dotenv import load_dotenv
from lunchbag.tools.image_generator_tool import ImageGeneratorTool

load_dotenv()

# ── Test configuration ────────────────────────────────────
# Edit these values before running if needed.
# TEST_PRODUCT must match a key in PRODUCT_FILE_MAP exactly.

TEST_CREATIVE_PROMPT = (
    "Neutral light grey studio background, model in profile "
    "with hair pinned up, captured at the peak of a gentle "
    "hair flip with dynamic strands suspended in motion, "
    "bold composed facial expression, warm Mediterranean skin "
    "tone, minimal modern styling, cobalt blue earring "
    "catching the light from the left."
)

TEST_ASPECT_RATIO = "1:1"
TEST_REF_CODE     = "SHOOT-SPR26-TEST"
TEST_PRODUCT      = "geometric crescent drop earrings"

# ── Run ───────────────────────────────────────────────────
print("="*50)
print("  ORPINA IMAGE GENERATION TEST")
print(f"  Product:  {TEST_PRODUCT}")
print(f"  Format:   {TEST_ASPECT_RATIO}")
print(f"  Ref code: {TEST_REF_CODE}")
print("="*50 + "\n")

tool   = ImageGeneratorTool()
result = tool._run(
    f"{TEST_CREATIVE_PROMPT}|{TEST_ASPECT_RATIO}|{TEST_REF_CODE}|{TEST_PRODUCT}"
)

print(f"\nResult: {result}\n")

if result.startswith("SUCCESS"):
    print("="*50)
    print("  IMAGE GENERATED SUCCESSFULLY")
    print("  Check:")
    print("  asset_library/images/SHOOT-SPR26-TEST.png")
    print("="*50)
else:
    print("="*50)
    print("  GENERATION FAILED — see error above")
    print("="*50)
