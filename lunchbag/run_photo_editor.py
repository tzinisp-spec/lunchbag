import sys
import os
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))

from dotenv import load_dotenv
from lunchbag.tools.photo_editor_tool import PhotoEditorTool

import sys

load_dotenv()

resume_arg = ""
if len(sys.argv) > 1:
    resume_arg = sys.argv[1]

print("\n" + "="*50)
print(f"  ORPINA — PHOTO EDITOR REVIEW {'(' + resume_arg + ')' if resume_arg else ''}")
print("="*50 + "\n")

tool   = PhotoEditorTool()
report = tool._run(resume_arg)
print(report)

print("\n" + "="*50)
print("  Report saved to:")
print("  outputs/photo_editor_latest.md")
print("="*50 + "\n")
