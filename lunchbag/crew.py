from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import FileReadTool, FileWriterTool

from lunchbag.tools.image_generator_tool import ImageGeneratorTool
from lunchbag.tools.style_reference_tool import StyleReferenceReaderTool
from lunchbag.tools.composition_reader_tool import CompositionReaderTool
from lunchbag.tools.concept_reader_tool import ConceptReaderTool
from lunchbag.tools.film_processor_tool import FilmProcessorTool

import os

from lunchbag.tools.photo_editor_tool import PhotoEditorTool
from lunchbag.tools.art_director_tool import ArtDirectorTool
from lunchbag.tools.sprint_reporter_tool import SprintReporterTool
from lunchbag.tools.catalog_writer_tool import CatalogWriterTool
from lunchbag.tools.copywriter_tool import CopywriterTool
from lunchbag.tools.content_planner_tool import ContentPlannerTool
from lunchbag.tools.review_generator_tool import ReviewGeneratorTool

PHASE_1_TASKS = [
    "build_creative_brief",
    "create_style_bible",
]

PHASE_2_TASKS = [
    "run_copywriter",
    "run_content_planner",
    "run_review_generator",
    "generate_sprint_report",
]

@CrewBase
class LunchbagCrew:
    """
    Lunchbag main crew — monthly creative sprint.
    Includes human-in-the-loop checkpoints.
    """
    agents_config = "config/agents.yaml"
    tasks_config  = "config/tasks.yaml"

    file_read_tool   = FileReadTool()
    file_writer_tool = FileWriterTool()

    # ── Agents ──────────────────────────────────────────────

    @agent
    def content_strategist(self) -> Agent:
        return Agent(
            config=self.agents_config["content_strategist"],
            tools=[
                self.file_read_tool,
                StyleReferenceReaderTool(),
                ConceptReaderTool(),
            ],
        )

    @agent
    def visual_director(self) -> Agent:
        return Agent(
            config=self.agents_config["visual_director"],
            tools=[
                self.file_read_tool,
                self.file_writer_tool,
                StyleReferenceReaderTool(),
                CompositionReaderTool(),
                PhotoEditorTool(),
                ArtDirectorTool(),
            ],
        )

    @agent
    def photographer(self) -> Agent:
        return Agent(
            config=self.agents_config["photographer"],
            tools=[
                self.file_read_tool,
                self.file_writer_tool,
                ImageGeneratorTool(),
                SprintReporterTool(),
                CatalogWriterTool(),
                FilmProcessorTool(),
                CopywriterTool(),
                ContentPlannerTool(),
                ReviewGeneratorTool(),
            ],
        )

    @agent
    def qc_inspector(self) -> Agent:
        return Agent(
            config=self.agents_config["qc_inspector"],
            tools=[
                PhotoEditorTool(),
                ArtDirectorTool(),
                CatalogWriterTool(),
            ],
        )

    # ── Tasks ───────────────────────────────────────────────

    @task
    def build_creative_brief(self) -> Task:
        return Task(
            config=self.tasks_config["build_creative_brief"],
            output_file="outputs/creative_brief.md",
        )

    @task
    def create_style_bible(self) -> Task:
        return Task(
            config=self.tasks_config["create_style_bible"],
            output_file="outputs/style_bible_and_shot_list.md",
        )

    @task
    def build_image_generation_package(self) -> Task:
        return Task(
            config=self.tasks_config["build_image_generation_package"],
            output_file="outputs/image_generation_package.md",
        )

    @task
    def run_film_processor(self) -> Task:
        return Task(
            config=self.tasks_config["run_film_processor"],
        )

    @task
    def run_photo_editor(self) -> Task:
        return Task(
            config=self.tasks_config["run_photo_editor"],
            output_file="outputs/photo_editor_latest.md",
        )

    @task
    def write_catalog(self) -> Task:
        return Task(
            config=self.tasks_config["write_catalog"],
        )

    @task
    def run_art_director(self) -> Task:
        return Task(
            config=self.tasks_config["run_art_director"],
            output_file="outputs/art_director_latest.md",
        )

    @task
    def run_copywriter(self) -> Task:
        return Task(
            config=self.tasks_config["run_copywriter"],
            output_file="outputs/copy_latest.json",
        )

    @task
    def run_content_planner(self) -> Task:
        return Task(
            config=self.tasks_config["run_content_planner"],
            output_file="outputs/weekly_calendar.md",
        )

    @task
    def run_review_generator(self) -> Task:
        return Task(
            config=self.tasks_config["run_review_generator"],
            output_file="outputs/review.html",
        )

    @task
    def generate_sprint_report(self) -> Task:
        return Task(
            config=self.tasks_config["generate_sprint_report"],
        )

    # ── Crew ────────────────────────────────────────────────

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            memory=False,
            verbose=True,
        )

    def run_with_report(self, phase: int = 1, inputs: dict = None) -> str:
        """
        Run the crew and always generate a
        sprint report at the end, even if the
        generate_sprint_report task fails.
        """
        import traceback
        import time
        from lunchbag.tools.sprint_reporter_tool import (
            SprintReporterTool
        )

        try:
            # Get all tasks by calling their methods
            task_names = (
                PHASE_1_TASKS if phase == 1
                else PHASE_2_TASKS
            )
            filtered_tasks = [
                getattr(self, t)() for t in task_names
            ]

            # Get all agents by calling their methods
            filtered_agents = [
                self.content_strategist(),
                self.visual_director(),
                self.photographer(),
                self.qc_inspector(),
            ]

            # Create a one-off crew for this run.
            # Phase 1 uses sequential process — tasks run
            # in defined order with no manager LLM overhead
            # and no risk of rogue tool calls between steps.
            c = Crew(
                agents=filtered_agents,
                tasks=filtered_tasks,
                process=Process.sequential,
                memory=False,
                verbose=True,
            )

            max_retries = 3
            retry_delay = 30

            for attempt in range(1, max_retries + 1):
                try:
                    print(
                        f"\n[Crew] Starting attempt "
                        f"{attempt}/{max_retries}..."
                    )
                    result = c.kickoff(inputs=inputs)
                    break
                except Exception as e:
                    err = str(e)
                    is_empty = (
                        "None or empty" in err
                        or "Invalid response" in err
                    )
                    if is_empty and attempt < max_retries:
                        print(
                            f"\n[Crew] Empty LLM response "
                            f"on attempt {attempt}. "
                            f"Retrying in {retry_delay}s..."
                        )
                        time.sleep(retry_delay)
                        continue
                    raise

        except Exception as e:
            print(f"\n[Crew] Sprint ended with error: {e}")
            result = str(e)
        finally:
            print(
                "\n[Crew] Running Sprint Reporter "
                "directly as fallback..."
            )
            try:
                reporter = SprintReporterTool()
                report   = reporter._run("{}")
                print("[Crew] ✓ Sprint Report generated")
                print(
                    "Report saved to: "
                    "outputs/sprint_report_latest.md"
                )
            except Exception as report_err:
                print(
                    f"[Crew] ✗ Sprint Report failed: "
                    f"{report_err}"
                )
                traceback.print_exc()

        return result
