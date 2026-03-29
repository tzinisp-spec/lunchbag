import base64
import os
from pathlib import Path
from crewai.tools import BaseTool
from google import genai
from google.genai import types

REFERENCES_DIR = Path("references")


class CompositionReaderTool(BaseTool):
    name: str = "Composition Reference Reader"
    description: str = """
        Reads all reference images provided by the brand owner
        and returns a unified analysis of the composition 
        language — framing, angles, subject placement, and
        negative space — across the entire reference set.

        No input required — call with an empty string.
        Automatically reads all images from
        references/

        Output: unified analysis of the composition language.
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
                f for f in REFERENCES_DIR.rglob("*")
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
                "reference images for a lifestyle product brand photoshoot. "
                "Analyse all provided images together and extract the "
                "unified composition rules that govern this visual "
                "language:\n\n"
                "FRAMING RULES\n"
                "[Common crops — tight, medium, wide]\n\n"
                "CAMERA ANGLES\n"
                "[Dominant perspectives — eye-level, top-down, etc.]\n\n"
                "SUBJECT PLACEMENT\n"
                "[Where does the product usually sit? Rule of thirds, "
                "centred, asymmetric?]\n\n"
                "NEGATIVE SPACE USAGE\n"
                "[How much space is left empty? Where is it placed?]\n\n"
                "DEPTH & LAYERING\n"
                "[How is depth created? Foregrounds, backgrounds, "
                "focus depth?]\n\n"
                "UNIFIED COMPOSITION RULE\n"
                "[A single technical instruction a photographer could "
                "follow to replicate this spatial language]\n\n"
                "Be precise and technical."
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
                f"COMPOSITION LANGUAGE ANALYSIS\n"
                f"Images analysed: {len(images)}\n"
                f"{'='*50}\n"
                f"{response.text}"
            )

        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
