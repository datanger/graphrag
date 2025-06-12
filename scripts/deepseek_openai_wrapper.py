from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
import httpx
import json
import asyncio
import requests
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

app = FastAPI(
    title="OpenAI-Compatible API Wrapper",
    description="A wrapper for the DeepSeek-V3-W8A8 model that provides OpenAI-compatible endpoints",
    version="1.0.0"
)

# Configuration
MODEL_NAME = "DeepSeek-V3-W8A8"
BASE_URL = "http://172.16.0.80/sdw/chatbot/sysai"
API_KEY = "YOUR_TOKEN"  # Replace with your actual token

# OpenAI-compatible request models
class Message(BaseModel):
    role: str
    content: str
    name: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    model: str = MODEL_NAME
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = None
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[List[str]] = None
    max_tokens: Optional[int] = 1024
    presence_penalty: Optional[float] = 0
    frequency_penalty: Optional[float] = 0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

@app.post("/v1/chat/completions")
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completions endpoint that supports both streaming and non-streaming responses.
    """
    if request.stream:
        return StreamingResponse(
            generate_streaming_response(request),
            media_type="text/event-stream"
        )
    else:
        return await generate_standard_response(request)

async def generate_standard_response(request: ChatCompletionRequest):
    """
    Generate a standard (non-streaming) response
    """
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "messages": [msg.dict() for msg in request.messages],
        "stream": False,
        "model": request.model,
        "max_tokens": request.max_tokens,
        "temperature": request.temperature,
        "presence_penalty": request.presence_penalty
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers, verify=False)
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Backend API request failed: {response.text}"
            )
            
        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', "")
        
        return {
            "id": "chatcmpl-" + str(hash(str(request.messages))),
            "object": "chat.completion",
            "created": int(asyncio.get_event_loop().time()),
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": len(" ".join([m.content for m in request.messages])),
                "completion_tokens": len(content.split()),
                "total_tokens": len(" ".join([m.content for m in request.messages])) + len(content.split())
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error processing request: {str(e)}"
        )

async def generate_streaming_response(request: ChatCompletionRequest):
    """
    Generate a streaming response
    """
    url = f"{BASE_URL}/v1/stream/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    
    payload = {
        "model": request.model,
        "messages": [msg.dict() for msg in request.messages],
        "stream": True,
        "temperature": request.temperature,
        "max_tokens": request.max_tokens
    }
    
    async with httpx.AsyncClient(timeout=None) as client:
        try:
            async with client.stream(
                "POST",
                url,
                json=payload,
                headers=headers
            ) as response:
                if response.status_code != 200:
                    error = await response.aread()
                    yield format_error_event(
                        status_code=response.status_code,
                        message=f"Backend API request failed: {error.decode()}"
                    )
                    return
                
                buffer = ""
                async for chunk in response.aiter_text():
                    if chunk.strip():
                        buffer += chunk
                        
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            line = line.strip()
                            
                            # Skip empty lines and control info
                            if not line or line.startswith(("id:", "event:")):
                                continue
                                
                            if line.startswith("data:"):
                                data = line[5:].strip()
                                if data == "[DONE]":
                                    yield format_done_event()
                                    return

                                chunk_data = {
                                    'id': 'chatcmpl-123',
                                    'object': 'chat.completion.chunk',
                                    'created': 0,
                                    'model': request.model,
                                    'choices': [{
                                        'index': 0,
                                        'delta': {'content': data},
                                        'finish_reason': None
                                    }]
                                }
                                response_data = f"data: {json.dumps(chunk_data)}\n\n"
                                yield response_data
                                    
        except httpx.RequestError as e:
            yield format_error_event(
                status_code=500,
                message=f"Request error: {str(e)}"
            )

def format_stream_event(content: str) -> str:
    """Format a streaming event in OpenAI format"""
    event_data = {
        "id": "chatcmpl-stream",
        "object": "chat.completion.chunk",
        "created": int(asyncio.get_event_loop().time()),
        "model": MODEL_NAME,
        "choices": [{
            "index": 0,
            "delta": {"content": content},
            "finish_reason": None
        }]
    }
    return f"data: {json.dumps(event_data)}\n\n"

def format_done_event() -> str:
    """Format the [DONE] event"""
    return "data: [DONE]\n\n"

def format_error_event(status_code: int, message: str) -> str:
    """Format an error event"""
    event_data = {
        "error": {
            "code": status_code,
            "message": message
        }
    }
    return f"data: {json.dumps(event_data)}\n\n"

@app.get("/v1/models")
async def list_models():
    """List available models (OpenAI compatible)"""
    return {
        "object": "list",
        "data": [
            {
                "id": MODEL_NAME,
                "object": "model",
                "created": 1677649963,
                "owned_by": "organization-owner"
            }
        ]
    }

@app.get("/")
async def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)