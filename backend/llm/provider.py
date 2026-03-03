"""LLM provider abstraction — supports Anthropic Claude, OpenAI, and extensible to others."""

import json
import asyncio
from typing import AsyncGenerator
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI
from backend.config import api_keys


class LLMProvider:
    """Unified interface for multiple LLM backends. Re-initializes clients when keys change."""

    def __init__(self):
        self._key_snapshot: tuple = ("", "")
        self.providers: dict = {}
        self._init_clients()

    def _init_clients(self):
        """(Re)create clients from the current api_keys store."""
        self.providers = {}
        if api_keys.anthropic:
            self.providers["anthropic"] = AsyncAnthropic(api_key=api_keys.anthropic)
        if api_keys.openai:
            self.providers["openai"] = AsyncOpenAI(api_key=api_keys.openai)
        self._key_snapshot = (api_keys.anthropic, api_keys.openai)

    def _ensure_fresh(self):
        """Re-init if keys have changed since last call."""
        current = (api_keys.anthropic, api_keys.openai)
        if current != self._key_snapshot:
            self._init_clients()

    @property
    def available_providers(self) -> list[str]:
        self._ensure_fresh()
        return list(self.providers.keys())

    @property
    def ready(self) -> bool:
        self._ensure_fresh()
        return "anthropic" in self.providers

    async def chat(
        self,
        messages: list[dict],
        provider: str = "anthropic",
        model: str | None = None,
        system: str = "",
        tools: list[dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        stream: bool = False,
    ) -> dict | AsyncGenerator:
        self._ensure_fresh()

        if provider not in self.providers:
            raise RuntimeError(
                f"Provider '{provider}' not available. "
                "Please set your API key in Settings (gear icon)."
            )

        if provider == "anthropic":
            return await self._anthropic_chat(
                messages, model or "claude-sonnet-4-20250514",
                system, tools, max_tokens, temperature, stream,
            )
        elif provider == "openai":
            return await self._openai_chat(
                messages, model or "gpt-4o",
                system, tools, max_tokens, temperature, stream,
            )
        else:
            raise ValueError(f"Unknown provider: {provider}")

    async def _anthropic_chat(
        self, messages, model, system, tools, max_tokens, temperature, stream
    ) -> dict:
        client: AsyncAnthropic = self.providers["anthropic"]
        kwargs = dict(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=messages,
        )
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        if stream:
            return self._anthropic_stream(client, kwargs)

        response = await client.messages.create(**kwargs)
        return self._parse_anthropic_response(response)

    async def _anthropic_stream(self, client, kwargs) -> AsyncGenerator:
        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield {"type": "text_delta", "text": text}

    def _parse_anthropic_response(self, response) -> dict:
        result = {"role": "assistant", "content": "", "tool_calls": []}
        for block in response.content:
            if block.type == "text":
                result["content"] += block.text
            elif block.type == "tool_use":
                result["tool_calls"].append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        result["stop_reason"] = response.stop_reason
        result["usage"] = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
        }
        return result

    async def _openai_chat(
        self, messages, model, system, tools, max_tokens, temperature, stream
    ) -> dict:
        client: AsyncOpenAI = self.providers["openai"]
        oai_messages = []
        if system:
            oai_messages.append({"role": "system", "content": system})

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                parts = []
                for block in content:
                    if isinstance(block, dict):
                        if block.get("type") == "text":
                            parts.append({"type": "text", "text": block["text"]})
                        elif block.get("type") == "image":
                            parts.append({
                                "type": "image_url",
                                "image_url": {"url": block["source"]["data"]},
                            })
                oai_messages.append({"role": role, "content": parts or content})
            else:
                oai_messages.append({"role": role, "content": content})

        kwargs = dict(
            model=model,
            messages=oai_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if tools:
            kwargs["tools"] = self._convert_tools_to_openai(tools)

        response = await client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        result = {
            "role": "assistant",
            "content": choice.message.content or "",
            "tool_calls": [],
        }
        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                result["tool_calls"].append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "input": json.loads(tc.function.arguments),
                })
        return result

    def _convert_tools_to_openai(self, anthropic_tools: list[dict]) -> list[dict]:
        oai_tools = []
        for tool in anthropic_tools:
            oai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "parameters": tool.get("input_schema", {}),
                },
            })
        return oai_tools

    async def transcribe_audio(self, audio_bytes: bytes, format: str = "webm") -> str:
        """Transcribe audio using OpenAI Whisper."""
        self._ensure_fresh()
        if "openai" not in self.providers:
            raise RuntimeError("OpenAI API key required for voice transcription. Set it in Settings.")
        import io
        client: AsyncOpenAI = self.providers["openai"]
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"audio.{format}"
        transcript = await client.audio.transcriptions.create(
            model="whisper-1", file=audio_file
        )
        return transcript.text

    async def validate_anthropic_key(self, key: str) -> bool:
        """Test an Anthropic key by making a minimal API call."""
        try:
            client = AsyncAnthropic(api_key=key)
            resp = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=10,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception:
            return False

    async def validate_openai_key(self, key: str) -> bool:
        """Test an OpenAI key by making a minimal API call."""
        try:
            client = AsyncOpenAI(api_key=key)
            resp = await client.chat.completions.create(
                model="gpt-4o-mini",
                max_tokens=5,
                messages=[{"role": "user", "content": "Hi"}],
            )
            return True
        except Exception:
            return False


# Singleton
llm = LLMProvider()
