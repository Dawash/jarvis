"""Code agent — writes, runs, and analyzes code."""

import asyncio
import tempfile
from pathlib import Path
from typing import Any

from backend.agents.base_agent import BaseAgent
from backend.llm.tools import CODE_TOOLS, SYSTEM_TOOLS


class CodeAgent(BaseAgent):
    agent_type = "code"
    description = "Code writing agent — writes, executes, debugs, and analyzes code in multiple languages."

    @property
    def tools(self) -> list[dict]:
        return CODE_TOOLS + [SYSTEM_TOOLS[0]]  # run_shell too

    async def execute_tool(self, name: str, inp: dict) -> Any:
        match name:
            case "write_code":
                return self._write_code(inp["path"], inp["content"])
            case "run_code":
                return await self._run_code(inp["code"], inp.get("language", "python"))
            case "run_shell":
                return await self._run_shell(inp["command"], inp.get("timeout", 60))
            case _:
                return f"Unknown tool: {name}"

    def _write_code(self, path: str, content: str) -> str:
        try:
            p = Path(path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Written {len(content)} bytes to {p}"
        except Exception as e:
            return f"Error: {e}"

    async def _run_code(self, code: str, language: str) -> str:
        runners = {
            "python": ("python3", ".py"),
            "javascript": ("node", ".js"),
            "bash": ("bash", ".sh"),
            "ruby": ("ruby", ".rb"),
        }
        if language not in runners:
            return f"Unsupported language: {language}"

        cmd, ext = runners[language]
        with tempfile.NamedTemporaryFile(mode="w", suffix=ext, delete=False) as f:
            f.write(code)
            f.flush()
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                cmd, tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode(errors="replace")
            if stderr:
                output += "\nSTDERR:\n" + stderr.decode(errors="replace")
            output += f"\n[Exit code: {proc.returncode}]"
            return output[:10000]
        except asyncio.TimeoutError:
            return "Code execution timed out (30s)"
        except Exception as e:
            return f"Execution error: {e}"
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    async def _run_shell(self, command: str, timeout: int = 60) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            output = stdout.decode(errors="replace")
            if stderr:
                output += "\nSTDERR:\n" + stderr.decode(errors="replace")
            return output[:10000]
        except asyncio.TimeoutError:
            return f"Timed out after {timeout}s"
        except Exception as e:
            return f"Error: {e}"
