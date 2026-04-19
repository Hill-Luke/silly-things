# No changes to this file; instructions were for a different file. Outputting the original content unchanged.
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
import os
from shrq_dj.tools.custom_tool import (
    QueryIntakeTool,
    SelectRelevantFieldsTool,
    FilterDatasetTool,
    AnalyzeRelevantDataTool,
    CuratePlaylistTool,
)
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

@CrewBase
class ShrqDj():
    """ShrqDj crew"""

    agents: List[BaseAgent]
    tasks: List[Task]
    llm_model: str = os.getenv("OPENAI_MODEL", "openai/gpt-4o-mini")

    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def data_analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['data_analyst'],  # type: ignore[index]
            tools=[
                QueryIntakeTool(),
                SelectRelevantFieldsTool(),
                FilterDatasetTool(),
                AnalyzeRelevantDataTool(),
            ],
            llm=self.llm_model,
            verbose=True,
        )

    @agent
    def disc_jockey(self) -> Agent:
        return Agent(
            config=self.agents_config['disc_jockey'], # type: ignore[index]
            tools=[CuratePlaylistTool()],
            llm=self.llm_model,
            verbose=True
        )

    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def query_intake(self) -> Task:
        return Task(
            config=self.tasks_config['query_intake'], # type: ignore[index]
        )

    @task
    def select_relevant_fields(self) -> Task:
        return Task(
            config=self.tasks_config['select_relevant_fields'],
            context=[self.query_intake(),], # type: ignore[index]
        )
    
    @task
    def filter_dataset(self) -> Task:
        return Task(
            config=self.tasks_config['filter_dataset'],
            context=[self.query_intake(),self.select_relevant_fields()], # type: ignore[index] # type: ignore[index]
        )
    
    @task
    def analyze_relevant_data(self) -> Task:
        return Task(
            config=self.tasks_config['analyze_relevant_data'],
            context=[self.query_intake(),self.select_relevant_fields(),self.filter_dataset()], # type: ignore[index]
        )
    @task
    def curate_playlist(self) -> Task:
        return Task(
            config=self.tasks_config['curate_playlist'],
            context=[self.query_intake(),self.select_relevant_fields(),self.filter_dataset(),self.analyze_relevant_data()], # type: ignore[index]
        )

    @crew
    def crew(self) -> Crew:
        """Creates the ShrqDj crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )
