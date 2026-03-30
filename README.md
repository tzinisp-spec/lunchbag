# Lunchbag AI Photoshoot System

A fully autonomous AI pipeline that plans, shoots, reviews, and catalogs a monthly image library for **The Lunchbags** — a Greek cotton lunch bag brand. Built with CrewAI and Google Gemini.

## What it does

Takes a folder of moodboard reference images and produces a complete, reviewed, and cataloged photoshoot in one command — no photographer required.

Each sprint generates ~50 brand-consistent images across 3 shoot sets, runs automated QC on every frame, writes Greek Instagram captions, builds a weekly posting calendar, and delivers a full sprint report with timing and cost breakdown.

## Pipeline Overview

```
Reference images + product photos
        │
        ▼
[Content Strategist]  — reads refs, writes creative brief
        │
        ▼
[Visual Director]     — defines 3 shoot sets, writes shot list & DNA blocks
        │
        ▼
[Photographer]        — generates all images (3 parallel workers)
        │
        ▼
[Film Processor]      — applies film-style grading pass
        │
        ▼
[Photo Editor]        — QC reviews every image, fixes or flags issues
        │
        ▼
[Auto-Regen Loop]     — regenerates structural failures (Regen- files)
        │
        ▼
[Catalog Writer]      — writes asset library catalog
        │
        ▼
[Copywriter]          — Greek captions + hashtags
        │
        ▼
[Content Planner]     — weekly posting calendar
        │
        ▼
[Sprint Reporter]     — final report: images, timing, cost
```

## Prerequisites

- Python 3.12
- A Gemini API key from [Google AI Studio](https://aistudio.google.com)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/tzinisp-spec/lunchbag.git
   cd lunchbag
   ```

2. Create and activate virtual environment:
   ```bash
   python3.12 -m venv test_env
   source test_env/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install crewai google-genai python-dotenv
   ```

4. Create a `.env` file in the project root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   GOOGLE_API_KEY=your_google_api_key
   MODEL=gemini/gemini-2.5-pro
   ```

5. Add your content:
   - Drop product photos into `products/` (`.jpg` or `.png`)
   - Drop moodboard reference images into `references/Set1/`, `references/Set2/`, `references/Set3/`

## Running a sprint

Always run from the project root:

```bash
cd /path/to/lunchbag
./test_env/bin/python3 main.py
```

The sprint runs fully autonomously. Progress is printed to the terminal as each step completes. A sprint report is saved to `outputs/` at the end.

## Configuration

Edit the `INPUTS` dictionary in `main.py`:

```python
"brand_name":        "The Lunchbags"
"current_season":    "Spring 2026"
"shoot_month":       "03"
"shoot_day":         "20"
"images_per_sprint": "50"        # use 10 for testing
"posts_per_week":    "5"
"content_mix":       "35% bag in use — carried or held by model, ..."
```

## Resilience features

- **Auto-regen loop** — after QC, images marked `Regen-` (structural failures) are automatically regenerated without restarting the sprint
- **Checkpoint / resume** — photo editor saves progress after each image; if the process disconnects mid-set it resumes from where it left off
- **Fatal error fast-abort** — programming errors (wrong API call, missing module) exit immediately rather than retrying indefinitely
- **Retry with backoff** — transient API errors retry up to 3 times with a 10s delay

## Output structure

```
asset_library/
  images/
    Shoot{N}/
      Set1/   ← approved images
      Set2/
      Set3/
  catalog.json

outputs/
  style_bible_and_shot_list.md
  sprint_report_{shoot_id}.md
  weekly_calendar_{shoot_id}.md
```

## Stack

- [CrewAI](https://crewai.com) — multi-agent orchestration
- [Gemini 2.5 Pro](https://deepmind.google/gemini) — agent reasoning, image review, and generation
- Python 3.12
