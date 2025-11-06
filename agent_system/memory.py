from __future__ import annotations

import logging
from typing import Any, Dict, List

from .models import Action, Goal, Memory, Observation

logger = logging.getLogger(__name__)


class MemorySystem:
    """Manages working memory and episodic memory for the agent."""

    def __init__(self, working_memory_size: int = 10):
        self.working_memory: List[Memory] = []
        self.episodic_memory: List[Memory] = []
        self.working_memory_size = working_memory_size
        self.memory_counter = 0

    def store_memory(
        self,
        goal_id: str,
        action: Action,
        observation: Observation,
        context: Dict[str, Any],
        success_score: float,
    ):
        """Store a new memory."""
        self.memory_counter += 1

        memory = Memory(
            id=f"mem_{self.memory_counter}",
            goal_id=goal_id,
            action=action,
            observation=observation,
            context=context,
            success_score=success_score,
        )

        self.working_memory.append(memory)

        if len(self.working_memory) > self.working_memory_size:
            excess = self.working_memory[self.working_memory_size :]
            self.episodic_memory.extend(excess)
            self.working_memory = self.working_memory[-self.working_memory_size :]

        logger.debug("Stored memory: %s", memory.id)

    def recall_similar_experiences(self, goal: Goal, n: int = 5) -> List[Memory]:
        """Recall similar past experiences from episodic memory."""
        goal_words = set(goal.description.lower().split())

        scored_memories: List[tuple[float, Memory]] = []
        for memory in self.episodic_memory:
            mem_goal = memory.context.get("goal_description", "")
            mem_words = set(str(mem_goal).lower().split())

            if not goal_words or not mem_words:
                similarity = 0.0
            else:
                similarity = len(goal_words & mem_words) / len(goal_words | mem_words)

            scored_memories.append((similarity, memory))

        scored_memories.sort(reverse=True, key=lambda pair: pair[0])
        return [memory for _, memory in scored_memories[:n]]

    def get_working_memory_context(self) -> Dict[str, Any]:
        """Get context from working memory."""
        context: Dict[str, Any] = {
            "recent_actions": [],
            "recent_outcomes": [],
            "success_rate": 0.0,
        }

        if not self.working_memory:
            return context

        context["recent_actions"] = [mem.action.name for mem in self.working_memory]
        context["recent_outcomes"] = [mem.observation.status.value for mem in self.working_memory]
        context["success_rate"] = sum(mem.success_score for mem in self.working_memory) / len(
            self.working_memory
        )

        return context

    def clear_working_memory(self):
        """Clear working memory (move all to episodic)."""
        self.episodic_memory.extend(self.working_memory)
        self.working_memory.clear()

    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics."""
        return {
            "working_memory_size": len(self.working_memory),
            "episodic_memory_size": len(self.episodic_memory),
            "total_memories": self.memory_counter,
            "avg_success_score": (
                sum(mem.success_score for mem in self.episodic_memory) / len(self.episodic_memory)
                if self.episodic_memory
                else 0.0
            ),
        }
