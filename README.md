# Orpina AI Photoshoot System

A fully autonomous AI pipeline that plans, shoots, reviews, and catalogs a monthly image library for an earring brand. Built with CrewAI and Google Gemini.

## What it does

Produces 40 reviewed, cataloged, brand-consistent photoshoot images per sprint from a folder of moodboard references. No photographer required.

## Prerequisites

- Python 3.12
- [gcloud CLI](https://cloud.google.com/sdk/docs/install)
- A Google Cloud project with [Gemini for Google Cloud API](https://console.developers.google.com) enabled
- A Gemini API key from [Google AI Studio](https://aistudio.google.com)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/tzinisp-spec/Orpina.git
   cd Orpina
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

4. Authenticate Google Cloud:
   ```bash
   gcloud auth application-default login
   gcloud auth application-default set-quota-project YOUR_PROJECT_ID
   ```

5. Create .env file in the project root:
   ```env
   GEMINI_API_KEY=your_gemini_api_key
   GOOGLE_API_KEY=your_google_api_key
   MODEL=gemini/gemini-2.5-pro
   GOOGLE_CLOUD_PROJECT=your_project_id
   ```

6. Add your content:
   - Drop product photos into `products/` (any filename, .jpg or .png)
   - Drop moodboard images into `references/` (any filename, .jpg or .png)

## Running a sprint

Always run from the project root in Terminal:

```bash
cd /path/to/Orpina
./test_env/bin/python3 main.py
```

The sprint runs autonomously. One checkpoint appears at the end — type 'approve' or 'reshoot' directly in the Terminal window.

## Configuration

Edit the `INPUTS` dictionary in `main.py` to configure:

```python
"images_per_sprint": "40"   # use 10 for testing
"current_season":   "Spring 2026"
"product_focus":    "your products"
"content_mix":      "40% worn on model, ..."
```

## Documentation

Full documentation: https://tzinisp-spec.github.io/Orpina/

## Running standalone tools

If a sprint crashes mid-way run remaining steps:

```bash
PYTHONPATH=. ./test_env/bin/python3 orpina/run_photo_editor.py
PYTHONPATH=. ./test_env/bin/python3 orpina/run_art_director.py
PYTHONPATH=. ./test_env/bin/python3 orpina/run_catalog.py
```

## Stack

- [CrewAI](https://crewai.com) — multi-agent orchestration
- [Gemini 2.5 Pro](https://deepmind.google/gemini) — agent reasoning and image review
- [Gemini 3 Pro Image](https://deepmind.google/gemini) — image generation and editing
- Python 3.12
