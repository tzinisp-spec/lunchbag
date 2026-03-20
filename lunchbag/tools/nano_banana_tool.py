import os
from pathlib import Path
from crewai.tools import BaseTool
from google import genai
from google.genai import types

# Using 'the lunchbags' to match the rest of the project structure
ASSET_DIR = Path("asset_library/images")

class ImageGeneratorTool(BaseTool):
    name: str = "The Lunchbags Image Generator"
    description: str = """
        Generates a product image using Google Imagen 3.
        Input must be pipe-separated: prompt|aspect_ratio|reference_code
        aspect_ratio: 1:1 for feed, 9:16 for story
        Example: Cobalt blue bags on warm sand...|1:1|SHOOT-SPR26-001
        Output: file path and ref code, or TOOL_ERROR: <reason>
    """

    def _run(self, input_str: str) -> str:
        try:
            # ── Parse input ───────────────────────────────
            parts = input_str.split("|")
            if len(parts) != 3:
                return "TOOL_ERROR: Input must be prompt|aspect_ratio|reference_code"

            prompt, aspect_ratio, ref_code = [p.strip() for p in parts]

            valid_ratios = ["1:1", "9:16", "3:4", "4:3"]
            if aspect_ratio not in valid_ratios:
                aspect_ratio = "1:1"

            # ── Call Imagen 3 via new google-genai SDK ────
            api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                return "TOOL_ERROR: No API key found (GEMINI_API_KEY or GOOGLE_API_KEY)"

            client = genai.Client(api_key=api_key)

            response = client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    safety_filter_level="BLOCK_LOW_AND_ABOVE",
                    person_generation="ALLOW_ADULT",
                ),
            )

            if not response.generated_images:
                return "TOOL_ERROR: No image returned by Imagen 3"

            # ── Save image ────────────────────────────────
            ASSET_DIR.mkdir(parents=True, exist_ok=True)
            file_path = ASSET_DIR / f"{ref_code}.png"

            image_bytes = response.generated_images[0].image.image_bytes
            file_path.write_bytes(image_bytes)

            return f"SUCCESS | path: {file_path} | ref: {ref_code}"

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
