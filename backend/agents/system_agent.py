"""System agent — full system control: shell, files, processes, system info."""

import asyncio
import os
import platform
import shutil
from pathlib import Path
from typing import Any

import psutil

from backend.agents.base_agent import BaseAgent
from backend.llm.tools import SYSTEM_TOOLS


class SystemAgent(BaseAgent):
    agent_type = "system"
    description = "System control agent — executes shell commands, manages files, monitors processes and system resources."

    @property
    def tools(self) -> list[dict]:
        return SYSTEM_TOOLS

    async def execute_tool(self, name: str, inp: dict) -> Any:
        match name:
            case "run_shell":
                return await self._run_shell(inp["command"], inp.get("timeout", 60))
            case "read_file":
                return self._read_file(inp["path"])
            case "write_file":
                return self._write_file(inp["path"], inp["content"])
            case "list_directory":
                return self._list_directory(inp.get("path", "."))
            case "search_files":
                return await self._search_files(
                    inp.get("directory", "."), inp.get("pattern"), inp.get("content")
                )
            case "manage_process":
                return self._manage_process(inp)
            case "system_info":
                return self._system_info(inp.get("category", "all"))
            case _:
                return f"Unknown tool: {name}"

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
            output += f"\n[Exit code: {proc.returncode}]"
            return output[:10000]
        except asyncio.TimeoutError:
            proc.kill()
            return f"Command timed out after {timeout}s"
        except Exception as e:
            return f"Error: {e}"

    def _read_file(self, path: str) -> str:
        try:
            p = Path(path).expanduser()
            if not p.exists():
                return f"File not found: {path}"
            if p.stat().st_size > 5_000_000:
                return f"File too large ({p.stat().st_size} bytes). Reading first 100KB."
            content = p.read_text(errors="replace")
            return content[:100_000]
        except Exception as e:
            return f"Error reading file: {e}"

    def _write_file(self, path: str, content: str) -> str:
        try:
            p = Path(path).expanduser()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"Written {len(content)} bytes to {p}"
        except Exception as e:
            return f"Error writing file: {e}"

    def _list_directory(self, path: str) -> str:
        try:
            p = Path(path).expanduser()
            if not p.is_dir():
                return f"Not a directory: {path}"
            entries = []
            for item in sorted(p.iterdir()):
                kind = "DIR" if item.is_dir() else "FILE"
                size = item.stat().st_size if item.is_file() else ""
                entries.append(f"  {kind}  {item.name}  {size}")
            return f"Contents of {p}:\n" + "\n".join(entries[:200])
        except Exception as e:
            return f"Error: {e}"

    async def _search_files(self, directory: str, pattern: str | None, content: str | None) -> str:
        results = []
        p = Path(directory).expanduser()
        if not p.is_dir():
            return f"Not a directory: {directory}"

        glob_pattern = pattern or "*"
        count = 0
        for fp in p.rglob(glob_pattern):
            if count >= 100:
                results.append("... (truncated at 100 results)")
                break
            if fp.is_file():
                if content:
                    try:
                        text = fp.read_text(errors="replace")
                        if content.lower() in text.lower():
                            results.append(str(fp))
                            count += 1
                    except Exception:
                        pass
                else:
                    results.append(str(fp))
                    count += 1
        return f"Found {len(results)} matches:\n" + "\n".join(results)

    def _manage_process(self, inp: dict) -> str:
        action = inp["action"]
        if action == "list":
            filt = inp.get("filter", "").lower()
            procs = []
            for p in psutil.process_iter(["pid", "name", "cpu_percent", "memory_info", "status"]):
                try:
                    info = p.info
                    if filt and filt not in info["name"].lower():
                        continue
                    mem = info["memory_info"].rss // 1024 // 1024 if info["memory_info"] else 0
                    procs.append(f"PID {info['pid']:>6}  {info['name']:<25} CPU:{info['cpu_percent']}%  MEM:{mem}MB  {info['status']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return "\n".join(procs[:50]) or "No matching processes."

        elif action == "kill":
            pid = inp.get("pid")
            if not pid:
                return "PID required"
            try:
                psutil.Process(pid).terminate()
                return f"Process {pid} terminated."
            except Exception as e:
                return f"Error: {e}"

        elif action == "start":
            cmd = inp.get("command")
            if not cmd:
                return "Command required"
            import subprocess
            proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return f"Started process PID {proc.pid}"

        return f"Unknown action: {action}"

    def _system_info(self, category: str) -> str:
        info = {}
        if category in ("all", "os"):
            info["os"] = {
                "system": platform.system(),
                "release": platform.release(),
                "version": platform.version(),
                "machine": platform.machine(),
                "hostname": platform.node(),
            }
        if category in ("all", "cpu"):
            info["cpu"] = {
                "cores_physical": psutil.cpu_count(logical=False),
                "cores_logical": psutil.cpu_count(logical=True),
                "usage_percent": psutil.cpu_percent(interval=0.5),
                "freq_mhz": psutil.cpu_freq().current if psutil.cpu_freq() else "N/A",
            }
        if category in ("all", "memory"):
            mem = psutil.virtual_memory()
            info["memory"] = {
                "total_gb": round(mem.total / 1e9, 2),
                "available_gb": round(mem.available / 1e9, 2),
                "used_percent": mem.percent,
            }
        if category in ("all", "disk"):
            disk = psutil.disk_usage("/")
            info["disk"] = {
                "total_gb": round(disk.total / 1e9, 2),
                "free_gb": round(disk.free / 1e9, 2),
                "used_percent": disk.percent,
            }
        if category in ("all", "network"):
            nets = psutil.net_if_addrs()
            info["network"] = {iface: [a.address for a in addrs] for iface, addrs in nets.items()}

        import json
        return json.dumps(info, indent=2)
