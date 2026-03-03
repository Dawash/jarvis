"""Base agent class — all specialized agents inherit from this."""

import asyncio
import uuid
import time
import traceback
from typing import Any
from backend.llm.provider import llm
from backend.config import AGENT_TIMEOUT


class AgentStatus:
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentEvent:
    """Event emitted by an agent for real-time streaming to UI."""
    def __init__(self, agent_id: str, event_type: str, data: Any):
        self.agent_id = agent_id
        self.event_type = event_type  # thinking, tool_call, tool_result, response, error, status
        self.data = data
        self.timestamp = time.time()

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "type": self.event_type,
            "data": self.data,
            "timestamp": self.timestamp,
        }


class BaseAgent:
    """Base class for all agents. Provides LLM interaction, tool execution, and event streaming."""

    agent_type: str = "base"
    description: str = "Base agent"

    def __init__(self, agent_id: str | None = None):
        self.id = agent_id or f"{self.agent_type}_{uuid.uuid4().hex[:8]}"
        self.status = AgentStatus.IDLE
        self.messages: list[dict] = []
        self.events: list[AgentEvent] = []
        self.event_callbacks: list = []
        self.result: Any = None
        self.error: str | None = None
        self.created_at = time.time()
        self.sub_agents: list["BaseAgent"] = []

    @property
    def system_prompt(self) -> str:
        return (
            f"You are a {self.agent_type} agent — part of JARVIS, a multi-agent AI assistant. "
            f"Your specialty: {self.description}. "
            "You have access to tools to accomplish tasks. Use them effectively. "
            "Be concise, accurate, and thorough. If a task requires multiple steps, "
            "execute them in sequence. Report your results clearly."
        )

    @property
    def tools(self) -> list[dict]:
        return []

    async def emit(self, event_type: str, data: Any):
        event = AgentEvent(self.id, event_type, data)
        self.events.append(event)
        for callback in self.event_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception:
                pass

    def on_event(self, callback):
        self.event_callbacks.append(callback)

    async def run(self, task: str, context: str = "") -> dict:
        """Execute a task with tool-use loop."""
        self.status = AgentStatus.RUNNING
        await self.emit("status", {"status": "running", "task": task})

        user_content = task
        if context:
            user_content = f"{task}\n\nContext:\n{context}"

        self.messages.append({"role": "user", "content": user_content})

        try:
            max_iterations = 20
            for i in range(max_iterations):
                await self.emit("thinking", {"iteration": i + 1})

                response = await llm.chat(
                    messages=self.messages,
                    system=self.system_prompt,
                    tools=self.tools if self.tools else None,
                    max_tokens=4096,
                    temperature=0.3,
                )

                self.messages.append({"role": "assistant", "content": response["content"]})

                if response.get("content"):
                    await self.emit("response", {"text": response["content"]})

                # If no tool calls, we're done
                if not response.get("tool_calls"):
                    self.result = {"content": response["content"], "iterations": i + 1}
                    self.status = AgentStatus.COMPLETED
                    await self.emit("status", {"status": "completed"})
                    return self.result

                # Execute tool calls
                tool_results = []
                for tool_call in response["tool_calls"]:
                    await self.emit("tool_call", {
                        "name": tool_call["name"],
                        "input": tool_call["input"],
                    })

                    result = await self.execute_tool(tool_call["name"], tool_call["input"])

                    await self.emit("tool_result", {
                        "name": tool_call["name"],
                        "result": str(result)[:2000],
                    })

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_call["id"],
                        "content": str(result),
                    })

                # Add tool results as user message (Anthropic format)
                self.messages.append({"role": "user", "content": tool_results})

            # Hit max iterations
            self.result = {"content": "Max iterations reached. Last response: " + response.get("content", ""), "iterations": max_iterations}
            self.status = AgentStatus.COMPLETED
            await self.emit("status", {"status": "completed", "note": "max_iterations"})
            return self.result

        except Exception as e:
            self.error = traceback.format_exc()
            self.status = AgentStatus.FAILED
            await self.emit("error", {"error": str(e), "traceback": self.error})
            return {"content": f"Agent failed: {e}", "error": self.error}

    async def execute_tool(self, name: str, input_data: dict) -> Any:
        """Override in subclasses to handle specific tools."""
        return f"Tool '{name}' not implemented in {self.agent_type} agent."

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.agent_type,
            "status": self.status,
            "created_at": self.created_at,
            "result": self.result,
            "error": self.error,
            "sub_agents": [a.to_dict() for a in self.sub_agents],
        }
