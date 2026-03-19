import base64
import os
from pathlib import Path
from crewai.tools import BaseTool
from google import genai
from google.genai import types

REFERENCES_DIR = Path("references")


class StyleReferenceReaderTool(BaseTool):
    name: str = "Style Reference Reader"
    description: str = """
        Reads and analyses all monthly reference images provided
        by the brand owner. Synthesises mood, colours,
        aesthetic, and visual language across the entire
        reference set.

        This analysis is used by the Content Strategist to
        inform the Creative Brief and by the Visual Director
        to anchor the Style Bible.

        No input required — call with an empty string.
        The tool automatically reads all images from
        references/

        Output: unified creative analysis across all references.
    """

    def _run(self, _: str = "") -> str:
        try:
            supported = {".jpg", ".jpeg", ".png"}
            if not REFERENCES_DIR.exists():
                return (
                    "TOOL_ERROR: References folder not found at "
                    "references/"
                )

            images = sorted([
                f for f in REFERENCES_DIR.iterdir()
                if f.is_file()
                and f.suffix.lower() in supported
            ])

            if not images:
                return (
                    "TOOL_ERROR: No images found in "
                    "references/. "
                    "Add your reference images before running."
                )

            client = genai.Client(
                api_key=os.getenv("GEMINI_API_KEY")
            )

            parts_list = []
            for img_path in images:
                mime = (
                    "image/png"
                    if img_path.suffix.lower() == ".png"
                    else "image/jpeg"
                )
                parts_list.append(
                    types.Part(
                        inline_data=types.Blob(
                            mime_type=mime,
                            data=img_path.read_bytes(),
                        )
                    )
                )

            analysis_prompt = (
                "You are a creative director analysing a set of "
                "reference images for a jewelry brand photoshoot. "
                "These images collectively define the complete "
                "creative direction — mood, aesthetic, colour "
                "palette, lighting, composition, and visual tone.\n\n"
                "Analyse all images together and return a unified "
                "creative brief covering:\n\n"
                "OVERALL MOOD\n"
                "[What feeling do all these images share?]\n\n"
                "COLOUR PALETTE\n"
                "[Dominant colours across all refs, with HEX codes]\n\n"
                "LIGHTING\n"
                "[Direction, quality, temperature, shadows]\n\n"
                "BACKGROUNDS & SURFACES\n"
                "[Materials, textures, colours]\n\n"
                "COMPOSITION LANGUAGE\n"
                "[Framing, angles, subject placement, negative space]\n\n"
                "AESTHETIC RULES\n"
                "[What visual rules do all these images follow?]\n\n"
                "CREATIVE DIRECTION IN ONE SENTENCE\n"
                "[A single sentence a photographer could pin above "
                "their monitor to guide every shot in this shoot]\n\n"
                "Be specific. This analysis is the creative "
                "foundation for a full monthly photoshoot."
            )

            parts_list.append(types.Part(text=analysis_prompt))

            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[
                    types.Content(
                        role="user",
                        parts=parts_list,
                    )
                ],
            )

            return (
                f"REFERENCE IMAGES ANALYSIS\n"
                f"Images analysed: {len(images)}\n"
                f"Files: {', '.join(f.name for f in images)}\n"
                f"{'='*50}\n"
                f"{response.text}"
            )

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
