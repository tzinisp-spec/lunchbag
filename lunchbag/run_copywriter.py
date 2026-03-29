import sys, os
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))
from dotenv import load_dotenv
load_dotenv()
from lunchbag.tools.copywriter_tool import CopywriterTool

print("\n" + "="*50)
print("  COPYWRITER — THE LUNCHBAGS")
print("="*50 + "\n")
print(CopywriterTool()._run())
