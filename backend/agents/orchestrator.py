"""Orchestrator — the master agent that understands user intent and spawns/coordinates sub-agents."""

import asyncio
import json
from typing import Any

from backend.agents.base_agent import BaseAgent, AgentStatus
from backend.agents.system_agent import SystemAgent
from backend.agents.web_agent import WebAgent
from backend.agents.code_agent import CodeAgent
from backend.llm.provider import llm
from backend.llm.tools import ALL_TOOLS
from backend.memory.store import memory_store


AGENT_REGISTRY = {
    "system": SystemAgent,
    "web": WebAgent,
    "code": CodeAgent,
}


class Orchestrator(BaseAgent):
    agent_type = "orchestrator"
    description = (
        "Master orchestrator — understands user intent, breaks tasks into subtasks, "
        "spawns specialized agents, coordinates results, and manages memory."
    )

    def __init__(self):
        super().__init__("orchestrator_main")
        self.active_agents: dict[str, BaseAgent] = {}
        self.conversation: list[dict] = []

    @property
    def system_prompt(self) -> str:
        memories = memory_store.get_recent(10)
        memory_context = ""
        if memories:
            memory_context = "\n\nYour memories:\n" + "\n".join(
                f"- [{m['category']}] {m['key']}: {m['content']}" for m in memories
            )

        agent_list = ", ".join(AGENT_REGISTRY.keys())

        return f"""You are JARVIS — a powerful personal AI assistant with full system control.
You can spawn specialized sub-agents to work in parallel: {agent_list}.

Your capabilities:
1. **System Control**: Run shell commands, manage files, monitor processes, get system info
2. **Web**: Fetch URLs, extract content, search the web
3. **Code**: Write, execute, and debug code in multiple languages
4. **Memory**: Remember user preferences, facts, and learned skills
5. **Multi-Agent**: Spawn multiple agents to work on subtasks in parallel

Guidelines:
- For simple tasks, use tools directly
- For complex tasks, spawn specialized agents
- Always explain what you're doing
- Remember important user preferences and information
- Be proactive — suggest improvements and anticipate needs
- When you spawn an agent, the result will come back to you — summarize it for the user
{memory_context}"""

    @property
    def tools(self) -> list[dict]:
        return ALL_TOOLS

    async def execute_tool(self, name: str, inp: dict) -> Any:
        # Agent spawning
        if name == "spawn_agent":
            return await self._spawn_agent(inp["agent_type"], inp["task"], inp.get("context", ""))

        # Memory
        if name == "save_memory":
            memory_store.save(inp["key"], inp["content"], inp.get("category", "fact"))
            return f"Saved to memory: {inp['key']}"
        if name == "recall_memory":
            results = memory_store.search(inp["query"], inp.get("category"))
            if not results:
                return "No memories found."
            return "\n".join(f"- [{r['category']}] {r['key']}: {r['content']}" for r in results)

        # Delegate to specialized agent for tool execution
        agent = self._get_agent_for_tool(name)
        if agent:
            return await agent.execute_tool(name, inp)

        return f"Unknown tool: {name}"

    def _get_agent_for_tool(self, tool_name: str) -> BaseAgent | None:
        """Find which agent can handle this tool."""
        from backend.llm.tools import SYSTEM_TOOLS, WEB_TOOLS, CODE_TOOLS
        system_names = {t["name"] for t in SYSTEM_TOOLS}
        web_names = {t["name"] for t in WEB_TOOLS}
        code_names = {t["name"] for t in CODE_TOOLS}

        if tool_name in system_names:
            return SystemAgent()
        elif tool_name in web_names:
            return WebAgent()
        elif tool_name in code_names:
            return CodeAgent()
        return None

    async def _spawn_agent(self, agent_type: str, task: str, context: str = "") -> str:
        if agent_type not in AGENT_REGISTRY:
            return f"Unknown agent type: {agent_type}. Available: {list(AGENT_REGISTRY.keys())}"

        agent_class = AGENT_REGISTRY[agent_type]
        agent = agent_class()
        self.active_agents[agent.id] = agent
        self.sub_agents.append(agent)

        # Forward event callbacks
        for cb in self.event_callbacks:
            agent.on_event(cb)

        await self.emit("agent_spawned", {"agent_id": agent.id, "type": agent_type, "task": task})

        result = await agent.run(task, context)
        return f"[Agent {agent.id} completed]\n{result.get('content', '')}"

    async def chat(self, user_message: str, attachments: list[dict] | None = None) -> str:
        """Main entry point — process a user message."""
        self.status = AgentStatus.RUNNING

        content: Any = user_message
        if attachments:
            content = [{"type": "text", "text": user_message}]
            for att in attachments:
                if att["type"] == "image":
                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": att.get("media_type", "image/png"),
                            "data": att["data"],
                        },
                    })
                elif att["type"] == "file":
                    content.append({"type": "text", "text": f"\n[File: {att['name']}]\n{att['content']}\n"})

        self.conversation.append({"role": "user", "content": content})
        self.messages = list(self.conversation)

        try:
            max_iterations = 25
            final_response = ""

            for i in range(max_iterations):
                await self.emit("thinking", {"iteration": i + 1})

                response = await llm.chat(
                    messages=self.messages,
                    system=self.system_prompt,
                    tools=self.tools,
                    max_tokens=4096,
                    temperature=0.4,
                )

                if response.get("content"):
                    final_response = response["content"]
                    await self.emit("response", {"text": response["content"], "partial": bool(response.get("tool_calls"))})

                if not response.get("tool_calls"):
                    break

                # Build assistant message with both text and tool use
                assistant_content = []
                if response.get("content"):
                    assistant_content.append({"type": "text", "text": response["content"]})
                for tc in response["tool_calls"]:
                    assistant_content.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["input"],
                    })
                self.messages.append({"role": "assistant", "content": assistant_content})

                # Execute tools
                tool_results = []
                tasks = []
                for tc in response["tool_calls"]:
                    await self.emit("tool_call", {"name": tc["name"], "input": tc["input"]})
                    tasks.append(self._execute_and_wrap(tc))

                tool_results = await asyncio.gather(*tasks)
                self.messages.append({"role": "user", "content": list(tool_results)})

            self.conversation.append({"role": "assistant", "content": final_response})
            self.status = AgentStatus.COMPLETED
            await self.emit("status", {"status": "completed"})
            return final_response

        except Exception as e:
            self.status = AgentStatus.FAILED
            error_msg = f"Error: {e}"
            await self.emit("error", {"error": error_msg})
            return error_msg

    async def _execute_and_wrap(self, tc: dict) -> dict:
        result = await self.execute_tool(tc["name"], tc["input"])
        await self.emit("tool_result", {"name": tc["name"], "result": str(result)[:2000]})
        return {
            "type": "tool_result",
            "tool_use_id": tc["id"],
            "content": str(result),
        }

    async def spawn_parallel(self, tasks: list[dict]) -> list[str]:
        """Spawn multiple agents in parallel and collect results."""
        coros = []
        for t in tasks:
            coros.append(self._spawn_agent(t["agent_type"], t["task"], t.get("context", "")))
        results = await asyncio.gather(*coros, return_exceptions=True)
        return [str(r) for r in results]
