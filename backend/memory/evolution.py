"""Self-evolution system — JARVIS can learn, adapt, and expand its capabilities."""

import json
import time
from pathlib import Path
from backend.memory.store import memory_store
from backend.config import ENABLE_SELF_EVOLUTION, EVOLUTION_LOG_PATH


class EvolutionEngine:
    """Tracks performance, learns from interactions, and suggests self-improvements."""

    def __init__(self):
        self.enabled = ENABLE_SELF_EVOLUTION
        self.log_path = Path(EVOLUTION_LOG_PATH)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.stats = {
            "total_tasks": 0,
            "successful_tasks": 0,
            "failed_tasks": 0,
            "tools_used": {},
            "agents_spawned": {},
            "common_requests": {},
        }

    def track_task(self, task: str, success: bool, tools_used: list[str], agents_used: list[str]):
        if not self.enabled:
            return

        self.stats["total_tasks"] += 1
        if success:
            self.stats["successful_tasks"] += 1
        else:
            self.stats["failed_tasks"] += 1

        for tool in tools_used:
            self.stats["tools_used"][tool] = self.stats["tools_used"].get(tool, 0) + 1
        for agent in agents_used:
            self.stats["agents_spawned"][agent] = self.stats["agents_spawned"].get(agent, 0) + 1

        # Track common request patterns
        words = task.lower().split()[:5]
        pattern = " ".join(words)
        self.stats["common_requests"][pattern] = self.stats["common_requests"].get(pattern, 0) + 1

        memory_store.log_evolution("task_completed", json.dumps({
            "task": task[:200], "success": success,
            "tools": tools_used, "agents": agents_used,
        }))

    def learn_shortcut(self, trigger: str, actions: list[dict]):
        """Learn a new shortcut/macro from repeated user actions."""
        memory_store.save(
            key=f"shortcut:{trigger}",
            content=json.dumps(actions),
            category="skill",
        )
        memory_store.log_evolution("learned_shortcut", f"Trigger: {trigger}")

    def get_learned_shortcuts(self) -> list[dict]:
        return memory_store.get_all(category="skill")

    def suggest_improvements(self) -> list[str]:
        suggestions = []
        total = self.stats["total_tasks"]
        if total == 0:
            return ["No data yet — keep using JARVIS to enable learning!"]

        fail_rate = self.stats["failed_tasks"] / total
        if fail_rate > 0.3:
            suggestions.append(
                f"High failure rate ({fail_rate:.0%}). Consider checking tool availability and permissions."
            )

        # Suggest automation for repeated tasks
        for pattern, count in sorted(
            self.stats["common_requests"].items(), key=lambda x: -x[1]
        ):
            if count >= 3:
                suggestions.append(
                    f'Repeated request pattern: "{pattern}" ({count} times). Consider creating a shortcut.'
                )

        if not suggestions:
            suggestions.append(f"Running well! {self.stats['successful_tasks']}/{total} tasks succeeded.")

        return suggestions

    def get_stats(self) -> dict:
        return {**self.stats, "success_rate": (
            self.stats["successful_tasks"] / max(self.stats["total_tasks"], 1)
        )}

    def create_custom_agent_spec(self, name: str, description: str, tools: list[str], prompt: str):
        """Allow JARVIS to define new agent types dynamically."""
        spec = {
            "name": name,
            "description": description,
            "tools": tools,
            "system_prompt": prompt,
            "created_at": time.time(),
        }
        memory_store.save(
            key=f"custom_agent:{name}",
            content=json.dumps(spec),
            category="skill",
        )
        memory_store.log_evolution("created_agent", f"New agent: {name}")
        return spec


evolution = EvolutionEngine()
