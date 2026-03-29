import sys, os
sys.path.insert(0, os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
))
from dotenv import load_dotenv
load_dotenv()
from lunchbag.tools.review_generator_tool import ReviewGeneratorTool

print("\n" + "="*50)
print("  REVIEW GENERATOR — THE LUNCHBAGS")
print("="*50 + "\n")
result = ReviewGeneratorTool()._run()
print(result)
if "outputs/review.html" in result:
    os.system("open outputs/review.html")
