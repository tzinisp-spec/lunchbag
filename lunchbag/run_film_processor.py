import sys
import os
from pathlib import Path

# Setup path to find lunchbag package
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from dotenv import load_dotenv
load_dotenv()

from lunchbag.tools.film_processor_tool import FilmProcessorTool

def run():
    print("\n" + "="*50)
    print("  FILM PROCESSOR — THE LUNCHBAGS")
    print("="*50 + "\n")

    tool   = FilmProcessorTool()
    result = tool._run()
    print(result)

    print("\n" + "="*50)

if __name__ == "__main__":
    run()
