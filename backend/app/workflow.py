import sqlite3
from pathlib import Path
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class State(TypedDict):
    phase: str
    gaps: list[str]
    version: int


class Workflow:
    """Meaningful transitions only; frames and audio never enter the graph."""

    def __init__(self, directory: Path):
        self.connection = sqlite3.connect(directory / "workflow.sqlite", check_same_thread=False)
        self.connection.execute("PRAGMA secure_delete=ON")
        self.checkpointer = SqliteSaver(self.connection)
        graph = StateGraph(State)
        graph.add_node("capture", lambda state: {"phase": "capture"})
        graph.add_node("debrief", lambda state: {"phase": "debrief"})
        graph.add_node("awaiting", lambda state: {"phase": "awaiting_confirmation"})
        graph.add_node("confirmation", self.confirmation)
        graph.add_node("training", lambda state: {"phase": "training"})
        graph.add_node("results", lambda state: {"phase": "results"})
        graph.add_edge(START, "capture")
        graph.add_edge("capture", "debrief")
        graph.add_edge("debrief", "awaiting")
        graph.add_edge("awaiting", "confirmation")
        graph.add_edge("confirmation", "training")
        graph.add_edge("training", "results")
        graph.add_edge("results", END)
        self.graph = graph.compile(
            checkpointer=self.checkpointer, interrupt_after=["capture", "debrief", "training"]
        )

    @staticmethod
    def confirmation(state: State) -> dict[str, str]:
        if state["gaps"]:
            raise ValueError("Required gaps remain unresolved")
        confirmed = interrupt({"version": state["version"], "action": "expert_confirmation"})
        if confirmed is not True:
            raise ValueError("Explicit expert confirmation required")
        return {"phase": "approved_map"}

    def start(self, session_id: str) -> None:
        self.graph.invoke({"phase": "capture", "gaps": [], "version": 1}, self.config(session_id))

    @staticmethod
    def config(session_id: str) -> dict:
        return {"configurable": {"thread_id": session_id}}

    def advance(self, session_id: str, gaps: list[str], version: int) -> str:
        config = self.config(session_id)
        self.graph.update_state(config, {"gaps": gaps, "version": version})
        self.graph.invoke(None, config)
        return self.graph.get_state(config).values["phase"]

    def confirm(self, session_id: str) -> str:
        config = self.config(session_id)
        self.graph.invoke(Command(resume=True), config)
        return self.graph.get_state(config).values["phase"]

    def remove(self, session_id: str) -> None:
        self.checkpointer.delete_thread(session_id)
