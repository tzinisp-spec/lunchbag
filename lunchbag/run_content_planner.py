import sys, os
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))
from dotenv import load_dotenv
load_dotenv()
from lunchbag.tools.content_planner_tool import ContentPlannerTool

print("\n" + "="*50)
print("  CONTENT PLANNER — THE LUNCHBAGS")
print("="*50 + "\n")
print(ContentPlannerTool()._run())
