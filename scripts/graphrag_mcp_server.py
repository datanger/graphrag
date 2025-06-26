#!/usr/bin/env python3
"""
GraphRAG MCP Server

This module provides a Model Context Protocol (MCP) server that wraps GraphRAG's
search capabilities, making them available to AI assistants like Continue in VSCode.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

# Add project root to path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolRequest,
    CallToolResult,
    ListToolsRequest,
    ListToolsResult,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    LoggingLevel,
    Text,
    Image,
    EmbeddedResourceReference,
    Resource,
    ReadResourceRequest,
    ReadResourceResult,
    ListResourcesRequest,
    ListResourcesResult,
)

# Import GraphRAG components
from graphrag.api import (
    local_search,
    global_search,
    drift_search,
    basic_search
)
from graphrag.config.models.graph_rag_config import GraphRagConfig
from graphrag.config.create_graphrag_config import create_graphrag_config
from graphrag.logger.factory import LoggerFactory, LoggerType

# Initialize logger
logger = LoggerFactory.create_logger(LoggerType.RICH)

# Global config storage
config = None
data = None

# Configuration and data loading functions
def load_config(config_path: str) -> GraphRagConfig:
    """Load GraphRAG configuration from file"""
    if config_path is None:
        config_path = os.getenv("GRAPHRAG_CONFIG_PATH", "settings.yaml")
    else:
        os.environ["GRAPHRAG_CONFIG_PATH"] = config_path
    
    import yaml
    with open(config_path, "r", encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
    return create_graphrag_config(values=config_data)

def load_data(config: GraphRagConfig) -> Dict[str, Any]:
    """Load GraphRAG data from parquet files"""
    import pandas as pd
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
        logger.error(f"Data loading failed: {str(e)}")
        raise Exception(f"Data loading failed: {str(e)}")

# Initialize MCP server
server = Server("graphrag-mcp")

@server.list_tools()
async def handle_list_tools() -> ListToolsResult:
    """List available GraphRAG search tools"""
    tools = [
        Tool(
            name="graphrag_local_search",
            description="Perform local search within specific communities in the knowledge graph. Best for focused queries about specific topics or entities.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to execute"
                    },
                    "community_level": {
                        "type": "integer",
                        "description": "Community level to search within (default: 1)",
                        "default": 1
                    },
                    "response_type": {
                        "type": "string",
                        "enum": ["json", "text"],
                        "description": "Response format type",
                        "default": "json"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="graphrag_global_search",
            description="Perform global search across all communities in the knowledge graph. Best for broad queries that may span multiple topics.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to execute"
                    },
                    "community_level": {
                        "type": "integer",
                        "description": "Community level to search within (default: 1)",
                        "default": 1
                    },
                    "dynamic_community_selection": {
                        "type": "boolean",
                        "description": "Whether to dynamically select communities based on query relevance",
                        "default": True
                    },
                    "response_type": {
                        "type": "string",
                        "enum": ["json", "text"],
                        "description": "Response format type",
                        "default": "json"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="graphrag_drift_search",
            description="Perform drift search to identify concept drift and changes in knowledge over time. Best for analyzing temporal patterns and evolution.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to execute"
                    },
                    "community_level": {
                        "type": "integer",
                        "description": "Community level to search within (default: 1)",
                        "default": 1
                    },
                    "response_type": {
                        "type": "string",
                        "enum": ["json", "text"],
                        "description": "Response format type",
                        "default": "json"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="graphrag_basic_search",
            description="Perform basic text-based search without graph structure. Best for simple keyword searches.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to execute"
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="graphrag_health_check",
            description="Check the health and status of the GraphRAG system",
            inputSchema={
                "type": "object",
                "properties": {},
                "additionalProperties": False
            }
        )
    ]
    return ListToolsResult(tools=tools)

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> CallToolResult:
    """Handle tool calls for GraphRAG search operations"""
    global config, data
    
    try:
        # Ensure config and data are loaded
        if config is None:
            config_path = os.getenv("GRAPHRAG_CONFIG_PATH", "settings.yaml")
            config = load_config(config_path)
            logger.info(f"Loaded GraphRAG config from: {config_path}")
        
        if data is None:
            data = load_data(config)
            logger.info("Loaded GraphRAG data")
        
        if name == "graphrag_health_check":
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps({
                            "status": "healthy",
                            "config_loaded": config is not None,
                            "data_loaded": data is not None,
                            "available_tools": [
                                "graphrag_local_search",
                                "graphrag_global_search", 
                                "graphrag_drift_search",
                                "graphrag_basic_search"
                            ]
                        }, indent=2)
                    )
                ]
            )
        
        # Extract query from arguments
        query = arguments.get("query")
        if not query:
            raise ValueError("Query parameter is required")
        
        # Common parameters
        common_params = {
            'config': config,
            'query': query,
            'community_level': arguments.get('community_level', 1),
            'response_type': arguments.get('response_type', 'json')
        }
        
        # Execute the appropriate search function
        if name == "graphrag_local_search":
            response, _ = await local_search(**common_params, **data)
        elif name == "graphrag_global_search":
            response, _ = await global_search(
                **common_params,
                dynamic_community_selection=arguments.get('dynamic_community_selection', True),
                **data
            )
        elif name == "graphrag_drift_search":
            response, _ = await drift_search(**common_params, **data)
        elif name == "graphrag_basic_search":
            response, _ = await basic_search(
                config=config,
                query=query,
                text_units=data.get('text_units')
            )
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        # Format response
        if isinstance(response, str):
            response_text = response
        else:
            response_text = json.dumps(response, indent=2, ensure_ascii=False)
        
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=response_text
                )
            ]
        )
    
    except Exception as e:
        logger.error(f"Error in tool call {name}: {str(e)}")
        return CallToolResult(
            content=[
                TextContent(
                    type="text",
                    text=f"Error executing {name}: {str(e)}"
                )
            ],
            isError=True
        )

@server.list_resources()
async def handle_list_resources() -> ListResourcesResult:
    """List available resources (config files, data sources, etc.)"""
    resources = []
    
    # Add config file if it exists
    config_path = os.getenv("GRAPHRAG_CONFIG_PATH", "settings.yaml")
    if os.path.exists(config_path):
        resources.append(
            Resource(
                uri=f"file://{os.path.abspath(config_path)}",
                name="GraphRAG Configuration",
                description="GraphRAG configuration file",
                mimeType="application/x-yaml"
            )
        )
    
    # Add data directory if it exists
    data_dir = "examples_notebooks/inputs/operation dulce"
    if os.path.exists(data_dir):
        resources.append(
            Resource(
                uri=f"file://{os.path.abspath(data_dir)}",
                name="GraphRAG Data Directory",
                description="Directory containing GraphRAG data files",
                mimeType="inode/directory"
            )
        )
    
    return ListResourcesResult(resources=resources)

@server.read_resource()
async def handle_read_resource(uri: str) -> ReadResourceResult:
    """Read resource content"""
    try:
        if uri.startswith("file://"):
            file_path = uri[7:]  # Remove "file://" prefix
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Determine MIME type based on file extension
                if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                    mime_type = "application/x-yaml"
                elif file_path.endswith('.json'):
                    mime_type = "application/json"
                elif file_path.endswith('.md'):
                    mime_type = "text/markdown"
                else:
                    mime_type = "text/plain"
                
                return ReadResourceResult(
                    contents=[
                        TextContent(
                            type="text",
                            text=content
                        )
                    ],
                    mimeType=mime_type
                )
        
        return ReadResourceResult(
            contents=[
                TextContent(
                    type="text",
                    text=f"Resource not found or not accessible: {uri}"
                )
            ],
            isError=True
        )
    
    except Exception as e:
        return ReadResourceResult(
            contents=[
                TextContent(
                    type="text",
                    text=f"Error reading resource {uri}: {str(e)}"
                )
            ],
            isError=True
        )

async def main():
    """Main entry point for the MCP server"""
    # Set up logging
    logging.basicConfig(level=logging.INFO)
    
    # Initialize server
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="graphrag-mcp",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=None,
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main()) 