from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from crewai_tools import ScrapeWebsiteTool
from gpt_hip_spots.tools.custom_tool import DuckDuckGoTool, OpenStreetMapTool
from pathlib import Path
import os
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

@CrewBase
class GptHipSpots():
    """GptHipSpots crew"""

    agents: List[BaseAgent]
    tasks: List[Task]
    agents_config = str(Path(__file__).parent / 'config' / 'agents.yaml')
    tasks_config = str(Path(__file__).parent / 'config' / 'tasks.yaml')

    search_tool = DuckDuckGoTool()
    scrape_tool = ScrapeWebsiteTool()
    osm_tool = OpenStreetMapTool()
    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher'], # type: ignore[index]
            verbose=True,
            tools=[self.search_tool, self.scrape_tool,self.osm_tool],
        )

    @agent
    def writer(self) -> Agent:
        return Agent(
            config=self.agents_config['writer'],  # type: ignore[index]
            tools=[],  # writer should not call tools; it composes from context
            verbose=True
        )


    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def research_bars(self) -> Task:
        return Task(
            config=self.tasks_config['research_bars'], # type: ignore[index]
        )
    def research_coffee(self) -> Task:
        return Task(
            config=self.tasks_config['research_coffee'], # type: ignore[index]
        )
    def research_shopping(self) -> Task:
        return Task(
            config=self.tasks_config['research_shopping'], # type: ignore[index]
        )
    def research_homewares(self) -> Task:
        return Task(
            config=self.tasks_config['research_homewares'], # type: ignore[index]
        )
    def research_art(self) -> Task:
        return Task(
            config=self.tasks_config['research_art'], # type: ignore[index]
        )
    def research_quirky(self) -> Task:
        return Task(
            config=self.tasks_config['research_quirky'], # type: ignore[index]
        )
    def research_restaurants(self) -> Task:
        return Task(
            config=self.tasks_config['research_restaurants'], # type: ignore[index]
        )

    @task
    def reporting_task(self) -> Task:
        return Task(
            config=self.tasks_config['compose_guide'], # type: ignore[index]
            output_file='report.md',
            context=[self.research_bars(),self.research_coffee(),self.research_shopping(),self.research_homewares(),self.research_art(),self.research_quirky(),self.research_restaurants()],
        )


    @crew
    def crew(self) -> Crew:
        """Creates the GptHipSpots crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
