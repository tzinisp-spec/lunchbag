from pathlib import Path
from crewai.tools import BaseTool

CONCEPT_PATH = Path("concept.md")


class ConceptReaderTool(BaseTool):
    name: str        = "Campaign Concept Reader"
    description: str = """
        Reads the campaign concept file (concept.md)
        from the project root if it exists.

        The concept file contains a plain language
        description of the campaign narrative —
        the situation, setting, and story the
        shoot should tell. It adds context to
        the reference images without replacing them.

        Returns the concept text if found, or an
        empty string if no concept file exists or
        if the file only contains the placeholder
        comment.

        No input required — call with empty string.
    """

    def _run(self, input_str: str = "") -> str:
        if not CONCEPT_PATH.exists():
            return ""

        content = CONCEPT_PATH.read_text().strip()

        # Return empty if only placeholder comment
        lines = [
            l for l in content.splitlines()
            if l.strip()
            and not l.strip().startswith("#")
            and not l.strip().startswith("<!--")
            and not l.strip().startswith("-->")
            and not l.strip().startswith("*")
            and l.strip() != ""
        ]

        if not lines:
            return ""

        # Strip markdown heading and comments
        # return only the actual concept text
        concept_lines = [
            l for l in content.splitlines()
            if not l.strip().startswith("#")
            and not l.strip().startswith("<!--")
            and not l.strip().startswith("-->")
            and l.strip() != ""
        ]

        concept = "\n".join(concept_lines).strip()

        if not concept:
            return ""

        print(
            f"[ConceptReader] Concept file found "
            f"({len(concept)} chars)"
        )
        return f"CAMPAIGN CONCEPT:\n{concept}"
