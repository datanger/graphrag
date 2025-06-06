import os
import sys
import uvicorn

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union, Literal
import json
import asyncio
from contextlib import asynccontextmanager
import argparse

# Import from the same directory
from scripts.graphrag_server import (
    SearchRequest, 
    local_search, 
    global_search, 
    drift_search, 
    basic_search,
    local_search_streaming,
    global_search_streaming,
    drift_search_streaming,
    basic_search_streaming,
    load_config,
    load_data
)

# Import from graphrag package
import sys
from pathlib import Path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.logger.factory import LoggerFactory, LoggerType

# Initialize logger
logger = LoggerFactory.create_logger(LoggerType.RICH)

# OpenAI compatible models
OPENAI_COMPATIBLE_MODELS = [
    "gpt-3.5-turbo",
    "gpt-4",
    "gpt-4-turbo-preview"
]

# Store config globally
config: Optional[GraphRagConfig] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle application startup and shutdown"""
    global config
    config_path = os.getenv("GRAPHRAG_CONFIG_PATH", "settings.yaml")
    config = load_config(config_path)
    logger.info(f"GraphRAG OpenAI wrapper initialized with config: {config_path}")
    yield
    # Clean up resources if needed
    config = None

# Initialize the app with lifespan
app = FastAPI(
    title="GraphRAG OpenAI Compatible API",
    lifespan=lifespan
)

# OpenAI compatible request models
class ChatCompletionMessage(BaseModel):
    role: Literal["system", "user", "assistant", "function"]
    content: str
    name: Optional[str] = None

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatCompletionMessage]
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 1.0
    n: Optional[int] = 1
    stream: Optional[bool] = False
    stop: Optional[Union[str, List[str]]] = None
    max_tokens: Optional[int] = None
    presence_penalty: Optional[float] = 0.0
    frequency_penalty: Optional[float] = 0.0
    logit_bias: Optional[Dict[str, float]] = None
    user: Optional[str] = None

class ChatCompletionResponseChoice(BaseModel):
    index: int
    message: Dict[str, Any]
    finish_reason: str

class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: List[ChatCompletionResponseChoice]
    usage: Dict[str, int]

class ChatCompletionChunkResponse(BaseModel):
    id: str
    object: str = "chat.completion.chunk"
    created: int
    model: str
    choices: List[Dict[str, Any]]

# Health check endpoint with config status
@app.get("/v1/health")
async def health_check() -> Dict[str, Any]:
    """Check if the service is healthy and config is loaded"""
    status = {
        "status": "ok" if config is not None else "error",
        "config_loaded": config is not None,
        "models": OPENAI_COMPATIBLE_MODELS
    }
    if config is None:
        status["error"] = "Configuration not loaded"
    return status

# List models endpoint
@app.get("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [{"id": model, "object": "model", "created": 1625097600, "owned_by": "graphrag"} 
                for model in OPENAI_COMPATIBLE_MODELS]
    }

# Chat completion endpoint
@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    try:
        # Extract query from messages
        query = ""
        for message in request.messages:
            if message.role == "user":
                query = message.content
                break
        
        if not query:
            raise HTTPException(status_code=400, detail="No user message found in the request")
        
        # Check if config is loaded
        if config is None:
            logger.error("Configuration not loaded when processing request")
            raise HTTPException(
                status_code=500, 
                detail="Service configuration not loaded. Please check the service logs."
            )
            
        try:
            # Load data
            data = load_data(config)
            
            # Choose search function based on model
            search_func = {
                "local_search": local_search,
                "global_search": global_search,
                "drift_search": drift_search,
                "basic_search": basic_search
            }.get(request.model, basic_search)
            
            if search_func is None:
                raise ValueError(f"No search function found for model: {request.model}")
                
        except Exception as e:
            logger.error(f"Error initializing search: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to initialize search: {str(e)}"
            )
        
        # Stream response if requested
        if request.stream:
            async def generate():
                # Initialize response_data with an empty string
                response_data = ""
                
                # For streaming, we need to use the streaming version of the search function
                search_func_name = search_func.__name__.replace('_streaming', '')
                streaming_func = {
                    'local_search': local_search_streaming,
                    'global_search': global_search_streaming,
                    'drift_search': drift_search_streaming,
                    'basic_search': basic_search_streaming
                }.get(search_func_name, basic_search_streaming)
                
                # Prepare common parameters
                common_params = {
                    'config': config,
                    'query': query,
                    'community_level': 1,
                    'response_type': 'json'
                }
                
                # Call the appropriate search function with the correct parameters
                if search_func_name == 'local_search':
                    response_stream = streaming_func(
                        **common_params,
                        **data
                    )
                elif search_func_name == 'global_search':
                    response_stream = streaming_func(
                        **common_params,
                        dynamic_community_selection=True,
                        **data
                    )
                elif search_func_name == 'drift_search':
                    response_stream = streaming_func(
                        **common_params,
                        **data
                    )
                else:  # basic_search
                    response_stream = streaming_func(
                        config=config,
                        query=query,
                        text_units=data.get('text_units')
                    )
                
                # Send response as SSE
                async for chunk in response_stream:
                    chunk_data = {
                        'id': 'chatcmpl-123',
                        'object': 'chat.completion.chunk',
                        'created': 0,
                        'model': request.model,
                        'choices': [{
                            'index': 0,
                            'delta': {'content': chunk},
                            'finish_reason': None
                        }]
                    }
                    response_data = f"data: {json.dumps(chunk_data)}\n\n"
                    yield response_data
                    await asyncio.sleep(0.02)  # Small delay to prevent overwhelming the client
                
                # Send done signal
                yield "data: [DONE]\n\n"
            
            return StreamingResponse(generate(), media_type="text/event-stream")
        
        # Prepare common parameters for non-streaming
        common_params = {
            'config': config,
            'query': query,
            'community_level': 1,
            'response_type': 'json'
        }
        
        # Call the appropriate search function with the correct parameters
        if search_func.__name__ == 'local_search':
            response, _ = await search_func(
                **common_params,
                **data
            )
        elif search_func.__name__ == 'global_search':
            response, _ = await search_func(
                **common_params,
                dynamic_community_selection=True,
                **data
            )
        elif search_func.__name__ == 'drift_search':
            response, _ = await search_func(
                **common_params,
                **data
            )
        else:  # basic_search
            response, _ = await search_func(
                config=config,
                query=query,
                text_units=data.get('text_units')
            )
        
        return {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 0,
            "model": request.model,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response if isinstance(response, str) else str(response)
                },
                "finish_reason": "stop"
            }],
            "usage": {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }
        }
    
    except Exception as e:
        logger.error(f"Error in chat completion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Run the server
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start GraphRAG FastAPI server.")
    parser.add_argument('--config', type=str, default=None, help='Path to GRAPHRAG_CONFIG_PATH (default: settings.yaml)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run the server on')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    args = parser.parse_args()

    os.environ["GRAPHRAG_CONFIG_PATH"] = args.config
    
    uvicorn.run(
        "graphrag_openai_wrapper:app",
        host=args.host,
        port=args.port,
        reload=True,
        log_level="info"
    )
