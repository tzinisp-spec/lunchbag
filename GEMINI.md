# Lunchbag Project Mandates

## Visual Consistency & Realism
- **Hard Format Enforcement:** Always enforce the 4:5 aspect ratio in the `ImageGeneratorTool` logic. If an agent passes 1:1, explicitly override it to 4:5 to maintain Instagram grid consistency.
- **Structural Integrity:** When using `product_angles`, instruct Nano Banana to use the physical structure from the angle references but the print pattern from the primary product reference.
- **Mandatory Shot Types:** Every creative sprint must include at least 2 `[UNPACK]` shots showing realistic interaction (hand reaching in) and the silver thermal lining.
- **Anatomy Verification:** The Photo Editor must perform a zero-tolerance "STRICT HUMAN ANATOMY AUDIT" (Criterion 9). Any anatomical impossibility (extra limbs, wrong finger count, floating parts) is an automatic and non-negotiable failure.
- **Model Proportions:** Arms and legs must be realistic human length; head size must be proportional to the body. Plastic, waxy, or poreless skin is an automatic failure.

## Sprint Architecture
- **Set Architecture:** Every sprint must have exactly 3 sets. No more, no less.
- **Shot Distribution:** Always use the "Three Core Pillars" distribution across the 50 images:
  - **Pillar A (50%):** Full model interaction ([MODEL], [MOTION], [INTERACTION], [ATMOSPHERE]).
  - **Pillar B (25%):** Details and textures ([PARTIAL], [DETAIL]).
  - **Pillar C (25%):** Open bag and food ([OPEN], [UNPACK]).
- **Set Enumeration:** Sets must be distributed as Set 1 (17 shots), Set 2 (17 shots), and Set 3 (16 shots).
- **Concept Adherence:** Set locations and themes must strictly follow the definitions in `concept.md`. The Visual Director must not invent locations outside of the concept file.

## Technical Robustness
- **Regex Fallbacks:** When parsing the Style Bible for `SET DNA PROMPT BLOCKS`, use a multi-pattern approach. If specific tags are missing, fall back to extracting the entire `SHOOT STRUCTURE` section to ensure generation always has context.
- **Tool-Direct Reporting:** Prefer having tools write detailed Markdown reports (e.g., `photo_editor_detail.md`) directly to the `outputs/` folder rather than having agents summarize them, to preserve technical data integrity.
- **Hardware Fidelity:** Any generated hardware (zippers, straps, clips) must match the product reference exactly in number and position; extra or missing hardware is an automatic technical failure.
- **Shot Cycling:** The Image Generator must cycle through the planned shots to reach the target image count for the set, incrementing shot reference numbers (e.g., S1-001 -> S1-011) to maintain unique filenames.
