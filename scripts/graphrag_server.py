import sys
import os
import json
import numpy as np
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder as fastapi_jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import pandas as pd
import yaml
from graphrag.api import (
    build_index, local_search, global_search, drift_search, basic_search,
    generate_indexing_prompts, local_search_streaming, global_search_streaming,
    drift_search_streaming, basic_search_streaming, multi_index_local_search,
    multi_index_global_search, multi_index_drift_search, multi_index_basic_search
)
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.config.create_graphrag_config import create_graphrag_config
from graphrag.logger.factory import LoggerFactory, LoggerType
from fastapi.responses import StreamingResponse
import json
import argparse

# 自定义 JSON 编码器处理 NumPy 类型
def custom_json_serializer(obj: Any) -> Any:
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.bool_):
        return bool(obj)
    elif isinstance(obj, (np.ndarray, np.generic)):
        return obj.tolist()
    elif hasattr(obj, 'dict'):
        return obj.dict()
    elif hasattr(obj, '__dict__'):
        return vars(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

# 创建 FastAPI 应用
app = FastAPI(default_response_class=JSONResponse)

# 覆盖默认的 JSON 响应处理
@app.middleware("http")
async def add_custom_serializer(request, call_next):
    response = await call_next(request)
    if hasattr(response, 'body') and hasattr(response, 'status_code') and response.status_code < 400:
        if hasattr(response, 'body') and response.body:
            try:
                response_data = json.loads(response.body.decode())
                response.body = json.dumps(
                    response_data,
                    default=custom_json_serializer,
                    ensure_ascii=False
                ).encode('utf-8')
                response.headers['content-length'] = str(len(response.body))
            except (json.JSONDecodeError, TypeError):
                pass
    return response

# 配置管理
def load_config(config_path: str) -> GraphRagConfig:
    if config_path is None:
        config_path = os.getenv("GRAPHRAG_CONFIG_PATH", "settings.yaml")
    else:
        os.environ["GRAPHRAG_CONFIG_PATH"] = config_path
    with open(config_path, "r", encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
    return create_graphrag_config(values=config_data)

# 数据模型
class SearchRequest(BaseModel):
    query: str
    n_results: int = 10
    community_level: Optional[int] = 1
    response_type: Optional[str] = "json"

class IndexRequest(BaseModel):
    root_path: str

class PromptTuneRequest(BaseModel):
    root: str
    chunk_size: int = 1200
    overlap: int = 100
    limit: int = 15
    selection_method: str = "RANDOM"
    domain: Optional[str] = None
    language: Optional[str] = None
    max_tokens: int = 2048
    discover_entity_types: bool = True
    min_examples_required: int = 2
    n_subset_max: int = 300
    k: int = 15

# 数据加载
def load_data(config: GraphRagConfig) -> Dict[str, Optional[pd.DataFrame]]:
    root_dir = config.root_dir
    try:
        return {
            "entities": pd.read_parquet(f"{root_dir}/.graphrag/output/entities.parquet"),
            "communities": pd.read_parquet(f"{root_dir}/.graphrag/output/communities.parquet"),
            "community_reports": pd.read_parquet(f"{root_dir}/.graphrag/output/community_reports.parquet"),
            "text_units": pd.read_parquet(f"{root_dir}/.graphrag/output/text_units.parquet"),
            "relationships": pd.read_parquet(f"{root_dir}/.graphrag/output/relationships.parquet"),
            "covariates": pd.read_parquet(f"{root_dir}/.graphrag/output/covariates.parquet") if os.path.exists(f"{root_dir}/.graphrag/output/covariates.parquet") else None
        }
    except Exception as e:
        logger.error(f"数据加载失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"数据加载失败: {str(e)}")

@app.post("/graphrag/local_search")
async def local_search_api(request: SearchRequest):
    try:
        data = load_data(config)
        if data["entities"] is None:
            raise HTTPException(status_code=500, detail="Failed to load entities data")
            
        response, context = await local_search(
            config=config,
            **data,
            community_level=request.community_level if request.community_level is not None else 1,
            response_type=request.response_type if request.response_type is not None else "json",
            query=request.query
        )
        print("response:", response)
        print(context)
        return JSONResponse(content={"response": response})
    except Exception as e:
        logger.error(f"本地搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/graphrag/global_search")
async def global_search_api(request: SearchRequest):
    try:
        data = load_data(config)
        
        # Check if required data is missing
        if data["entities"] is None:
            raise HTTPException(status_code=400, detail="Entities data is missing. Please ensure the data is properly indexed.")
        if data["communities"] is None:
            raise HTTPException(status_code=400, detail="Communities data is missing. Please ensure the data is properly indexed.")
        if data["community_reports"] is None:
            raise HTTPException(status_code=400, detail="Community reports data is missing. Please ensure the data is properly indexed.")
            
        response, context = await global_search(
            config=config,
            entities=data["entities"],
            communities=data["communities"],
            community_reports=data["community_reports"],
            community_level=request.community_level if request.community_level is not None else 1,
            dynamic_community_selection=True,
            response_type=request.response_type if request.response_type is not None else "json",
            query=request.query
        )
        return JSONResponse(content={"response": response, "context": context})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Global search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An error occurred during global search: {str(e)}")

@app.post("/graphrag/drift_search")
async def drift_search_api(request: SearchRequest):
    try:
        data = load_data(config)
        # Ensure community_level is an integer, defaulting to 1 if None
        community_level = request.community_level if request.community_level is not None else 1
        response, context = await drift_search(
            config=config,
            **data,
            community_level=community_level,
            response_type=request.response_type,
            query=request.query
        )
        return JSONResponse(content={"response": response, "context": context})
    except Exception as e:
        logger.error(f"漂移搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/graphrag/basic_search")
async def basic_search_api(request: SearchRequest):
    try:
        data = load_data(config)
        print(data)
        response, context = await basic_search(
            config=config,
            text_units=data["text_units"],
            query=request.query
        )
        return JSONResponse(content={"response": response, "context": context})
    except Exception as e:
        logger.error(f"基础搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/graphrag/generate_indexing_prompts")
async def generate_indexing_prompts_api(request: PromptTuneRequest):
    try:
        from graphrag.prompt_tune.types import DocSelectionType
        selection_method = getattr(DocSelectionType, request.selection_method, DocSelectionType.RANDOM)
        prompts = await generate_indexing_prompts(
            config=config,
            logger=logger,
            root=request.root,
            chunk_size=request.chunk_size,
            overlap=request.overlap,
            limit=request.limit,
            selection_method=selection_method,
            domain=request.domain,
            language=request.language,
            max_tokens=request.max_tokens,
            discover_entity_types=request.discover_entity_types,
            min_examples_required=request.min_examples_required,
            n_subset_max=request.n_subset_max,
            k=request.k
        )
        return JSONResponse(content={"prompts": prompts})
    except Exception as e:
        logger.error(f"生成索引提示失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/graphrag/index")
async def index(request: IndexRequest):
    try:
        import copy
        new_config = copy.deepcopy(config)
        new_config.input.base_dir = request.root_path
        logger.info(f"开始索引构建: {request.root_path}")
        await build_index(config=new_config)
        logger.info("索引构建完成")
        return JSONResponse(content={"status": "success"})
    except Exception as e:
        logger.error(f"索引构建失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# 流式搜索 API
@app.post("/graphrag/local_search_streaming")
async def local_search_streaming_api(request: SearchRequest):
    try:
        data = load_data(config)
        async def generate():
            async for response in local_search_streaming(
                config=config,
                **data,
                community_level=request.community_level if request.community_level is not None else 1,
                response_type=request.response_type,
                query=request.query
            ):
                yield response
        return StreamingResponse(generate(), media_type="application/json")
    except Exception as e:
        logger.error(f"流式搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Start GraphRAG FastAPI server.")
    parser.add_argument('--config', type=str, default=None, help='Path to GRAPHRAG_CONFIG_PATH (default: settings.yaml)')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run the server on')
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on')
    args = parser.parse_args()

    config = load_config(args.config)
    logger = LoggerFactory.create_logger(LoggerType.RICH)

    import uvicorn
    uvicorn.run("scripts.graphrag_server:app", host=args.host, port=args.port, reload=False)
