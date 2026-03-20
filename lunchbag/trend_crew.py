from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai_tools import ScrapeWebsiteTool
import os

@CrewBase
class LunchbagTrendCrew:
    """
    Standalone crew — runs the Trend Scout only.
    Run this once per month independently of the main crew.
    Output saved to trends/latest_trends.md
    """

    agents_config = "config/agents.yaml"
    tasks_config  = "config/trends_tasks.yaml"

    scrape_tool = ScrapeWebsiteTool()

    @agent
    def trend_scout(self) -> Agent:
        return Agent(
            config=self.agents_config["trend_scout"],
            tools=[self.scrape_tool],
        )

    @task
    def research_trends(self) -> Task:
        return Task(config=self.tasks_config["research_trends"])

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,  # no orchestrator needed
            verbose=True,
        )
