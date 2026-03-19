import sys
import os
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))

from dotenv import load_dotenv
from luanchbag.tools.art_director_tool import ArtDirectorTool

load_dotenv()

print("\n" + "="*50)
print("  ORPINA — ART DIRECTOR REVIEW")
print("="*50 + "\n")

tool   = ArtDirectorTool()
report = tool._run()
print(report)

print("\n" + "="*50)
print("  Report saved to:")
print("  outputs/art_director_latest.md")
print("="*50 + "\n")
