from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task
from crewai.agents.agent_builder.base_agent import BaseAgent
from typing import List
from dj.tools.custom_tool import DuckDuckGoTool, energy_tool, folder_file_extractor, bpm_tool
# If you want to run a snippet of code before or after the crew starts,
# you can use the @before_kickoff and @after_kickoff decorators
# https://docs.crewai.com/concepts/crews#example-crew-class-with-decorators

@CrewBase
class Dj():
    """Dj crew"""

    agents: List[BaseAgent]
    tasks: List[Task]
    folder_tool=folder_file_extractor()
    # search_tool=DuckDuckGoTool()
    energy_tool=energy_tool()
    bpm_tool=bpm_tool()


    # Learn more about YAML configuration files here:
    # Agents: https://docs.crewai.com/concepts/agents#yaml-configuration-recommended
    # Tasks: https://docs.crewai.com/concepts/tasks#yaml-configuration-recommended
    
    # If you would like to add tools to your agents, you can learn more about it here:
    # https://docs.crewai.com/concepts/agents#agent-tools
    @agent
    def music_researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['radio_dj'], # type: ignore[index]
            verbose=True,
            tools=[#self.search_tool,
                   self.energy_tool, 
                   self.folder_tool, 
                   self.bpm_tool]
        )


    @agent
    def radio_dj(self) -> Agent:
        return Agent(
            config=self.agents_config['radio_dj'], # type: ignore[index]
            verbose=True,
            tools=[#self.search_tool,
                   self.energy_tool, 
                   self.folder_tool, 
                   self.bpm_tool]
        )


    # To learn more about structured task outputs,
    # task dependencies, and task callbacks, check out the documentation:
    # https://docs.crewai.com/concepts/tasks#overview-of-a-task
    @task
    def read_files(self) -> Task:
        return Task(
            config=self.tasks_config['read_files'],
        )
    # @task
    # def research_song(self) -> Task:
    #     return Task(
    #         config=self.tasks_config['research_song'],
    #         context=[self.read_files()]
    #     )

    @task
    def read_tempo(self) -> Task:
        return Task(
            config=self.tasks_config['read_tempo'],
            context=[self.read_files()],
        )
    
    @task
    def read_energy(self) -> Task:
        return Task(
            config=self.tasks_config['read_energy'], # type: ignore[index]
            context=[self.read_files()]
        )
    
    @task
    def create_playlist(self) -> Task:
        return Task(
            config=self.tasks_config['create_playlist'],
            output_file='playlist.md',
            context=[self.read_files()
                    #  ,self.research_song()
                     ,self.read_energy(),
                     self.read_tempo()] # type: ignore[index]
        )
    

    @crew
    def crew(self) -> Crew:
        """Creates the Dj crew"""
        # To learn how to add knowledge sources to your crew, check out the documentation:
        # https://docs.crewai.com/concepts/knowledge#what-is-knowledge

        return Crew(
            agents=self.agents, # Automatically created by the @agent decorator
            tasks=self.tasks, # Automatically created by the @task decorator
            process=Process.sequential,
            verbose=True,
            # process=Process.hierarchical, # In case you wanna use that instead https://docs.crewai.com/how-to/Hierarchical/
        )