from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from .tools.custom_tool import BPMTool, AudioPreprocessTool, LUFSTool


@CrewBase
class MusicTagger():
    """MusicEnergyClassifier crew"""

    agents: List[BaseAgent]
    tasks: List[Task]

    @agent
    def bpm_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['bpm_researcher'],  # type: ignore[index]
            tools=[BPMTool()],
            verbose=True
        )

    @agent
    def loudness_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['loudness_researcher'],  # type: ignore[index]
            tools=[AudioPreprocessTool(), LUFSTool()],
            verbose=True
        )

    @agent
    def energy_curator(self) -> Agent:
        # This agent integrates results, no tools needed
        return Agent(
            config=self.agents_config['energy_curator'],  # type: ignore[index]
            verbose=True
        )

    @task
    def bpm_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config['bpm_analysis_task'],  # type: ignore[index]
            inputs={"filepaths": "{filepaths}"}
        )

    @task
    def bpm_categorization_task(self) -> Task:
        return Task(
            config=self.tasks_config['bpm_categorization_task'],  # type: ignore[index]
            inputs={"filepaths": "{filepaths}"},
            context=[self.bpm_analysis_task()]
        )

    @task
    def loudness_analysis_task(self) -> Task:
        return Task(
            config=self.tasks_config['loudness_analysis_task'],  # type: ignore[index]
            inputs={"filepaths": "{filepaths}"}
        )

    @task
    def energy_classification_task(self) -> Task:
        return Task(
            config=self.tasks_config['energy_classification_task'],  # type: ignore[index]
            inputs={"filepaths": "{filepaths}"},
            context=[self.bpm_analysis_task(),self.bpm_categorization_task(), self.loudness_analysis_task()]
        )

    @task
    def playlist_classification_task(self) -> Task:
        return Task(
            config=self.tasks_config['playlist_classification_task'],  # type: ignore[index]
            inputs={"filepaths": "{filepaths}"}
        )

    @crew
    def crew(self) -> Crew:
        """Creates the MusicEnergyClassifier crew"""
        return Crew(
            agents=self.agents,  # Automatically created by the @agent decorator
            tasks=self.tasks,    # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
        )