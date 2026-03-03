"""JARVIS — Personal AI Assistant Server."""

import asyncio
import base64
import json
import uuid
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from backend.config import HOST, PORT, UPLOAD_DIR, api_keys
from backend.agents.orchestrator import Orchestrator
from backend.memory.store import memory_store
from backend.memory.evolution import evolution
from backend.llm.provider import llm

app = FastAPI(title="JARVIS", version="1.0.0")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Global orchestrator per session
sessions: dict[str, Orchestrator] = {}


def get_orchestrator(session_id: str) -> Orchestrator:
    if session_id not in sessions:
        sessions[session_id] = Orchestrator()
    return sessions[session_id]


# ─── API Key management ─────────────────────────────────────────────────

@app.get("/api/keys/status")
async def keys_status():
    """Return which keys are configured (masked) and whether JARVIS is ready."""
    return JSONResponse(api_keys.to_status())


class KeysUpdate(BaseModel):
    anthropic: str | None = None
    openai: str | None = None
    google: str | None = None


@app.post("/api/keys/save")
async def keys_save(body: KeysUpdate):
    """Save API keys from the UI. Only non-empty values are updated."""
    updated = {}
    if body.anthropic is not None and body.anthropic.strip():
        updated["anthropic"] = body.anthropic.strip()
    if body.openai is not None and body.openai.strip():
        updated["openai"] = body.openai.strip()
    if body.google is not None and body.google.strip():
        updated["google"] = body.google.strip()

    if not updated:
        return JSONResponse({"ok": False, "error": "No keys provided"}, status_code=400)

    api_keys.update(**updated)

    # Reset orchestrators so they pick up new keys
    sessions.clear()

    return JSONResponse({"ok": True, "status": api_keys.to_status()})


@app.post("/api/keys/validate")
async def keys_validate(body: KeysUpdate):
    """Validate API keys by making a test call."""
    results = {}
    if body.anthropic and body.anthropic.strip():
        results["anthropic"] = await llm.validate_anthropic_key(body.anthropic.strip())
    if body.openai and body.openai.strip():
        results["openai"] = await llm.validate_openai_key(body.openai.strip())
    return JSONResponse({"results": results})


@app.post("/api/keys/clear")
async def keys_clear():
    """Clear all saved API keys."""
    api_keys.update(anthropic="", openai="", google="")
    sessions.clear()
    return JSONResponse({"ok": True, "status": api_keys.to_status()})


# ─── WebSocket — real-time chat with streaming ──────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_chat(websocket: WebSocket, session_id: str):
    await websocket.accept()
    orch = get_orchestrator(session_id)

    async def stream_events(event):
        try:
            await websocket.send_json(event.to_dict())
        except Exception:
            pass

    orch.on_event(stream_events)

    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type", "chat")

            if msg_type == "chat":
                # Guard: check if keys are configured
                if not api_keys.has_any:
                    await websocket.send_json({
                        "type": "error",
                        "error": "No API key configured. Please click the gear icon to set up your API keys.",
                    })
                    continue

                user_msg = data.get("message", "")
                attachments = data.get("attachments", [])

                memory_store.save_conversation(session_id, "user", user_msg)

                # Re-get orchestrator in case keys were reset
                orch = get_orchestrator(session_id)
                # Ensure event forwarding
                if stream_events not in orch.event_callbacks:
                    orch.on_event(stream_events)

                response = await orch.chat(user_msg, attachments if attachments else None)

                memory_store.save_conversation(session_id, "assistant", response)

                await websocket.send_json({
                    "type": "final_response",
                    "content": response,
                    "agents": [a.to_dict() for a in orch.sub_agents[-5:]],
                })

            elif msg_type == "voice":
                if not api_keys.openai:
                    await websocket.send_json({
                        "type": "error",
                        "error": "OpenAI API key required for voice. Set it in Settings (gear icon).",
                    })
                    continue

                audio_b64 = data.get("audio", "")
                audio_bytes = base64.b64decode(audio_b64)
                try:
                    transcript = await llm.transcribe_audio(audio_bytes, data.get("format", "webm"))
                    await websocket.send_json({"type": "transcript", "text": transcript})

                    orch = get_orchestrator(session_id)
                    if stream_events not in orch.event_callbacks:
                        orch.on_event(stream_events)

                    response = await orch.chat(transcript)
                    memory_store.save_conversation(session_id, "user", f"[voice] {transcript}")
                    memory_store.save_conversation(session_id, "assistant", response)
                    await websocket.send_json({
                        "type": "final_response",
                        "content": response,
                    })
                except Exception as e:
                    await websocket.send_json({"type": "error", "error": f"Voice error: {e}"})

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        pass


# ─── REST endpoints ─────────────────────────────────────────────────────

@app.post("/api/chat")
async def chat_endpoint(message: str = Form(...), session_id: str = Form("default")):
    if not api_keys.has_any:
        return JSONResponse({"error": "No API key configured"}, status_code=400)
    orch = get_orchestrator(session_id)
    response = await orch.chat(message)
    return JSONResponse({"response": response})


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form("default"),
    message: str = Form(""),
):
    content = await file.read()
    save_path = UPLOAD_DIR / f"{uuid.uuid4().hex}_{file.filename}"
    save_path.write_bytes(content)

    attachment = {"type": "file", "name": file.filename, "path": str(save_path)}

    if file.content_type and file.content_type.startswith("image/"):
        attachment = {
            "type": "image",
            "name": file.filename,
            "media_type": file.content_type,
            "data": base64.b64encode(content).decode(),
        }
    else:
        try:
            attachment["content"] = content.decode("utf-8", errors="replace")[:50000]
        except Exception:
            attachment["content"] = f"[Binary file: {file.filename}, {len(content)} bytes]"

    user_msg = message or f"I've uploaded a file: {file.filename}. Please analyze it."
    orch = get_orchestrator(session_id)
    response = await orch.chat(user_msg, [attachment])

    return JSONResponse({
        "response": response,
        "file": {"name": file.filename, "path": str(save_path), "size": len(content)},
    })


@app.get("/api/memory")
async def list_memories(category: str | None = None):
    return JSONResponse({"memories": memory_store.get_all(category)})


@app.get("/api/evolution/stats")
async def evolution_stats():
    return JSONResponse({
        "stats": evolution.get_stats(),
        "suggestions": evolution.suggest_improvements(),
    })


@app.get("/api/agents")
async def list_agents(session_id: str = "default"):
    orch = get_orchestrator(session_id)
    return JSONResponse({
        "agents": {aid: a.to_dict() for aid, a in orch.active_agents.items()},
    })


@app.get("/api/providers")
async def list_providers():
    return JSONResponse({"providers": llm.available_providers})


# ─── Serve frontend ────────────────────────────────────────────────────

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@app.get("/")
async def serve_index():
    index = FRONTEND_DIR / "index.html"
    return HTMLResponse(index.read_text())


app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


# ─── Entry point ────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host=HOST, port=PORT, reload=True)
