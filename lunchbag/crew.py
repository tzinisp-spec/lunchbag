from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import FileReadTool, FileWriterTool

from lunchbag.tools.image_generator_tool import ImageGeneratorTool
from lunchbag.tools.style_reference_tool import StyleReferenceReaderTool
from lunchbag.tools.composition_reader_tool import CompositionReaderTool
from lunchbag.tools.concept_reader_tool import ConceptReaderTool

import os

from lunchbag.tools.photo_editor_tool import PhotoEditorTool
from lunchbag.tools.art_director_tool import ArtDirectorTool
from lunchbag.tools.sprint_reporter_tool import SprintReporterTool
from lunchbag.tools.catalog_writer_tool import CatalogWriterTool

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
            process=Process.hierarchical,
            manager_agent=Agent(
                config=self.agents_config["content_orchestrator"],
                allow_delegation=True,
                llm="gemini/gemini-2.5-pro",
            ),
            memory=False,
            verbose=True,
        )

    def run_with_report(self, inputs: dict) -> str:
        """
        Run the crew and always generate a
        sprint report at the end, even if the
        generate_sprint_report task fails.
        """
        import traceback
        from lunchbag.tools.sprint_reporter_tool import (
            SprintReporterTool
        )

        try:
            result = self.crew().kickoff(inputs=inputs)
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
