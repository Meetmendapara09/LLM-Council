"""FastAPI backend for LLM Council."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio

from . import storage
from . import memory
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings

app = FastAPI(title="LLM Council API")

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.get("/api/conversations/{conversation_id}/memory")
async def get_conversation_memory(conversation_id: str):
    """Return the memory (short entries and summary) for a conversation."""
    try:
        mem = memory.get_memory(conversation_id)
        return mem
    except Exception:
        raise HTTPException(status_code=404, detail="Conversation not found")


@app.post("/api/conversations/{conversation_id}/memory/clear")
async def clear_conversation_memory(conversation_id: str):
    """Clear a conversation's memory."""
    try:
        memory.clear_memory(conversation_id)
        return {"status": "ok"}
    except Exception:
        raise HTTPException(status_code=404, detail="Conversation not found")


@app.get("/api/memory/mode")
async def get_memory_mode():
    """Return the current runtime memory mode and local settings."""
    from .config import MEMORY_LOCAL_MAX_SENTENCES
    try:
        mode = memory.get_runtime_mode()
        return {"mode": mode, "local_max_sentences": MEMORY_LOCAL_MAX_SENTENCES}
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to retrieve memory mode")


@app.post("/api/memory/mode")
async def set_memory_mode(payload: Dict[str, str]):
    """Set the runtime memory mode. Body: {"mode": "local"|"model"} """
    mode = payload.get("mode")
    if mode not in ("local", "model"):
        raise HTTPException(status_code=400, detail="mode must be 'local' or 'model'")
    try:
        memory.set_runtime_mode(mode)
        return {"status": "ok", "mode": mode}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=500, detail="Unable to set memory mode")


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Build message list for the council from conversation history + new user message
    # We include prior assistant final responses (stage3) as assistant messages so models have context
    messages = []
    for msg in conversation["messages"]:
        if msg.get('role') == 'user':
            messages.append({"role": "user", "content": msg.get('content', '')})
        elif msg.get('role') == 'assistant':
            # Use the Stage 3 synthesized answer as assistant message content when available
            stage3 = msg.get('stage3') or {}
            assistant_content = stage3.get('response', '') if isinstance(stage3, dict) else ''
            if assistant_content:
                messages.append({"role": "assistant", "content": assistant_content})

    # Append the new user message (most recent)
    messages.append({"role": "user", "content": request.content})

    # Get existing memory summary and pass it into the council
    try:
        mem = memory.get_memory(conversation_id)
        memory_summary = mem.get("summary", "")
    except Exception:
        memory_summary = ""

    # Run the 3-stage council process with conversation context and memory
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(messages, memory_summary)

    # Add assistant message with all stages
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result
    )

    # Update the conversation-level memory in the background (do not block the response)
    try:
        asyncio.create_task(memory.add_exchange_and_update_summary(
            conversation_id,
            request.content,
            stage3_result.get("response", "") if isinstance(stage3_result, dict) else ""
        ))
    except Exception:
        # Non-fatal if memory update fails
        pass

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Build message list for the council using conversation history + new user message
            messages = []
            for msg in conversation["messages"]:
                if msg.get('role') == 'user':
                    messages.append({"role": "user", "content": msg.get('content', '')})
                elif msg.get('role') == 'assistant':
                    stage3 = msg.get('stage3') or {}
                    assistant_content = stage3.get('response', '') if isinstance(stage3, dict) else ''
                    if assistant_content:
                        messages.append({"role": "assistant", "content": assistant_content})
            messages.append({"role": "user", "content": request.content})

            # Get existing memory summary and pass it into the council
            try:
                mem = memory.get_memory(conversation_id)
                memory_summary = mem.get("summary", "")
            except Exception:
                memory_summary = ""

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(messages)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(messages, stage1_results, memory_summary)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(messages, stage1_results, stage2_results, memory_summary)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result
            )

            # Update memory in the background
            try:
                asyncio.create_task(memory.add_exchange_and_update_summary(
                    conversation_id,
                    request.content,
                    stage3_result.get("response", "") if isinstance(stage3_result, dict) else ""
                ))
            except Exception:
                pass

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
