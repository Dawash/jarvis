"""Tool definitions that agents can use — Anthropic tool-use format."""

SYSTEM_TOOLS = [
    {
        "name": "run_shell",
        "description": "Execute a shell command on the system and return its output. Use for any OS-level operation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 60)", "default": 60},
            },
            "required": ["command"],
        },
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative path to the file"},
            },
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file, creating directories as needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to write the file"},
                "content": {"type": "string", "description": "Content to write"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and directories at the given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path to list", "default": "."},
            },
        },
    },
    {
        "name": "search_files",
        "description": "Search for files matching a pattern or content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {"type": "string", "description": "Directory to search in", "default": "."},
                "pattern": {"type": "string", "description": "Filename glob pattern (e.g. *.py)"},
                "content": {"type": "string", "description": "Search inside files for this text"},
            },
        },
    },
    {
        "name": "manage_process",
        "description": "List, start, or kill system processes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["list", "kill", "start"],
                    "description": "Action to perform",
                },
                "pid": {"type": "integer", "description": "Process ID (for kill)"},
                "command": {"type": "string", "description": "Command to start (for start)"},
                "filter": {"type": "string", "description": "Filter processes by name (for list)"},
            },
            "required": ["action"],
        },
    },
    {
        "name": "system_info",
        "description": "Get system information: CPU, memory, disk, network, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": ["all", "cpu", "memory", "disk", "network", "os"],
                    "default": "all",
                },
            },
        },
    },
]

WEB_TOOLS = [
    {
        "name": "fetch_url",
        "description": "Fetch content from a URL and return it as text or markdown.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to fetch"},
                "extract_text": {"type": "boolean", "description": "Extract text from HTML", "default": True},
            },
            "required": ["url"],
        },
    },
    {
        "name": "web_search",
        "description": "Search the web using a search engine.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "num_results": {"type": "integer", "description": "Number of results", "default": 5},
            },
            "required": ["query"],
        },
    },
]

CODE_TOOLS = [
    {
        "name": "write_code",
        "description": "Write code to a file with the given language and content.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to write"},
                "content": {"type": "string", "description": "Code content"},
                "language": {"type": "string", "description": "Programming language"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "run_code",
        "description": "Execute code in a given language and return output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Code to execute"},
                "language": {"type": "string", "enum": ["python", "javascript", "bash", "ruby"], "default": "python"},
            },
            "required": ["code"],
        },
    },
]

AGENT_TOOLS = [
    {
        "name": "spawn_agent",
        "description": "Spawn a new specialized sub-agent to handle a specific task in parallel.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_type": {
                    "type": "string",
                    "enum": ["system", "web", "code", "file", "research"],
                    "description": "Type of agent to spawn",
                },
                "task": {"type": "string", "description": "Task description for the agent"},
                "context": {"type": "string", "description": "Additional context or data for the agent"},
            },
            "required": ["agent_type", "task"],
        },
    },
    {
        "name": "save_memory",
        "description": "Save important information to long-term memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Memory key/label"},
                "content": {"type": "string", "description": "Content to remember"},
                "category": {"type": "string", "description": "Category (preference, fact, skill, task)", "default": "fact"},
            },
            "required": ["key", "content"],
        },
    },
    {
        "name": "recall_memory",
        "description": "Recall information from long-term memory.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to search for in memory"},
                "category": {"type": "string", "description": "Filter by category"},
            },
            "required": ["query"],
        },
    },
]

ALL_TOOLS = SYSTEM_TOOLS + WEB_TOOLS + CODE_TOOLS + AGENT_TOOLS
