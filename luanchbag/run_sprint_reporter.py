import os
import json
from pathlib import Path
from datetime import datetime
from luanchbag.tools.sprint_reporter_tool import SprintReporterTool

# Configuration
OUTPUTS_DIR = Path("outputs")

def get_file_mtime(filename):
    path = OUTPUTS_DIR / filename
    if path.exists():
        return path.stat().st_mtime
    return None

def generate():
    print("\n" + "="*50)
    print("  ORPINA — SPRINT REPORTER")
    print("="*50 + "\n")

    # Estimate timing data from file modification times
    t_brief   = get_file_mtime("creative_brief.md")
    t_bible   = get_file_mtime("style_bible_and_shot_list.md")
    t_pkg     = get_file_mtime("image_generation_package.md")
    t_pe      = get_file_mtime("photo_editor_latest.md")
    t_ad      = get_file_mtime("art_director_latest.md")
    
    # Baseline: started 1 hour before brief was finished
    started_at = t_brief - 3600 if t_brief else datetime.now().timestamp()
    
    steps = {
        "build_creative_brief":          int(t_brief - started_at) if t_brief else 300,
        "create_style_bible":            int(t_bible - t_brief) if (t_bible and t_brief) else 300,
        "build_image_generation_package": int(t_pkg - t_bible) if (t_pkg and t_bible) else 3600,
        "run_photo_editor":              int(t_pe - t_pkg) if (t_pe and t_pkg) else 600,
        "write_catalog":                 30,
        "run_art_director":              int(t_ad - t_pe) if (t_ad and t_pe) else 300,
        "final_approval":                0
    }

    # Construct input JSON
    timing_data = {
        "sprint_id": "SPR26",
        "started_at": datetime.fromtimestamp(started_at).isoformat(),
        "steps": steps,
        "images_planned": 40,
        "errors": []
    }

    tool = SprintReporterTool()
    result = tool._run(json.dumps(timing_data))
    print(result)

    print("\n" + "="*50)
    print("  Report saved to:")
    print("  outputs/sprint_report_latest.md")
    print("="*50 + "\n")

if __name__ == "__main__":
    generate()
