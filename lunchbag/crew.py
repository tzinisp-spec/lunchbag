from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import FileReadTool, FileWriterTool

from lunchbag.tools.image_generator_tool import ImageGeneratorTool
from lunchbag.tools.style_reference_tool import StyleReferenceReaderTool
from lunchbag.tools.composition_reader_tool import CompositionReaderTool
from lunchbag.tools.human_approval_tool import HumanApprovalTool

import os

from lunchbag.tools.photo_editor_tool import PhotoEditorTool
from lunchbag.tools.art_director_tool import ArtDirectorTool
from lunchbag.tools.sprint_reporter_tool import SprintReporterTool
from lunchbag.tools.catalog_writer_tool import CatalogWriterTool

@CrewBase
class LuanchbagCrew:
    """
    Luanchbag main crew — monthly creative sprint.
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
                HumanApprovalTool(),
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
    def final_approval(self) -> Task:
        return Task(
            config=self.tasks_config["final_approval"],
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
