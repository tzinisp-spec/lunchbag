import os
import subprocess
from pathlib import Path
from crewai.tools import BaseTool

REFERENCES_DIR = Path("references")
ASSET_DIR      = Path("asset_library/images")
OUTPUTS_DIR    = Path("outputs")


class HumanApprovalTool(BaseTool):
    name: str = "Human Approval"
    description: str = """
        Pauses the sprint and asks the brand owner for approval
        before continuing.

        CHECKPOINT 1: After the Creative Brief is written.
        Pass the brief text as input and wait for approval.

        Input: a message to show the brand owner describing
        what needs to be reviewed and where to find it.

        Example input for checkpoint 1:
        CHECKPOINT 1: Creative Brief is ready for your review.
        Find it at: outputs/creative_brief.md
        Open the file, read it, then return here to approve
        or request changes.

        Output: APPROVED or CHANGES REQUESTED: [feedback]
    """

    def _run(self, message: str) -> str:
        try:
            print("\n")
            print("=" * 60)
            print("  ⏸  ORPINA — HUMAN APPROVAL REQUIRED")
            print("=" * 60)
            print(f"\n{message}\n")
            print("=" * 60)
            print("\nOptions:")
            print("  Type 'approve' — accept the full shoot")
            print("  Type 'reshoot' — regenerate all images")
            print("             from scratch")
            print("=" * 60 + "\n")

            response = input("Your decision: ").strip().lower()

            if response == "approve":
                print("\n✓ Shoot approved — sprint complete.\n")
                return "APPROVED"
            elif response == "reshoot":
                print(
                    "\n⚠ RESHOOT will permanently delete "
                    "all generated images.\n"
                    f"Images in asset library: "
                )
                # Count images first
                asset_dir = Path(
                    "asset_library/images"
                )
                supported = {".jpg", ".jpeg", ".png"}
                image_count = sum(
                    1 for f in asset_dir.iterdir()
                    if f.is_file()
                    and f.suffix.lower() in supported
                ) if asset_dir.exists() else 0

                print(f"{image_count} images will be deleted.")
                print(
                    "Type 'confirm' to proceed with reshoot.\n"
                    "Type anything else to go back to approval.\n"
                )
                confirm = input(
                    "Confirm reshoot: "
                ).strip().lower()

                if confirm != "confirm":
                    print(
                        "\n↩ Reshoot cancelled — "
                        "returning to approval.\n"
                    )
                    return self._run(message)

                print("\n↩ Reshoot confirmed — clearing images...\n")
                cleared = 0
                for f in asset_dir.iterdir():
                    if (
                        f.is_file()
                        and f.suffix.lower() in supported
                    ):
                        f.unlink()
                        cleared += 1
                print(f"[Approval] Cleared {cleared} images.")
                print("[Approval] Restarting photoshoot...\n")
                return "RESHOOT"
            else:
                print(
                    "\n⚠ Unrecognised input. "
                    "Please type 'approve' or 'reshoot'.\n"
                )
                return self._run(message)

        except KeyboardInterrupt:
            return "RESHOOT"
        except Exception as e:
            return f"TOOL_ERROR: {str(e)}"
