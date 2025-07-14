#!/usr/bin/env python3
"""
<<<<<<< HEAD
GraphRAG MCP Server

This module provides a Model Context Protocol (MCP) server that wraps GraphRAG's
search capabilities, making them available to AI assistants like Continue in VSCode.
=======
GraphRAG MCP Server with Debug Logging

This version includes detailed logging to verify MCP calls from Continue.
>>>>>>> d350dfe17e38aa01fa23e35fe3b1c04b1eae4e85
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
<<<<<<< HEAD
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
=======
from typing import Any, Dict, List, Optional
import httpx
from dataclasses import dataclass
from datetime import datetime

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('mcp_debug.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class GraphRAGConfig:
    api_base_url: str = "http://localhost:8000"
    timeout: int = 30

class MCPServer:
    """MCP server with detailed logging"""
    
    def __init__(self, config: GraphRAGConfig):
        self.config = config
        self.tools = self._define_tools()
        self.request_count = 0
        logger.info("=== MCP Server Initialized ===")
        logger.info(f"API Base URL: {config.api_base_url}")
        logger.info(f"Available tools: {[tool['name'] for tool in self.tools]}")
    
    def _define_tools(self) -> List[Dict[str, Any]]:
        """Define available tools"""
        return [
            {
                "name": "graphrag_search",
                "description": "Search through knowledge graph using GraphRAG",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "The search query to execute"
                        },
                        "search_type": {
                            "type": "string",
                            "enum": ["local", "global", "drift", "basic"],
                            "description": "Type of search to perform",
                            "default": "basic"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "graphrag_health_check",
                "description": "Check the health status of the GraphRAG API server",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]
    
    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP requests with detailed logging"""
        self.request_count += 1
        method = request.get("method")
        request_id = request.get("id", 1)
        
        logger.info(f"=== MCP Request #{self.request_count} ===")
        logger.info(f"Timestamp: {datetime.now().isoformat()}")
        logger.info(f"Method: {method}")
        logger.info(f"Request ID: {request_id}")
        logger.info(f"Full request: {json.dumps(request, indent=2)}")
        
        if method == "initialize":
            logger.info("Handling initialize request")
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "graphrag-mcp",
                        "version": "1.0.0"
                    }
                }
            }
            logger.info(f"Initialize response: {json.dumps(response, indent=2)}")
            return response
        
        elif method == "tools/list":
            logger.info("Handling tools/list request")
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"tools": self.tools}
            }
            logger.info(f"Tools list response: {json.dumps(response, indent=2)}")
            return response
        
        elif method == "tools/call":
            params = request.get("params", {})
            name = params.get("name")
            arguments = params.get("arguments", {})
            
            logger.info(f"=== Tool Call: {name} ===")
            logger.info(f"Arguments: {json.dumps(arguments, indent=2)}")
            
            result = await self._call_tool(name, arguments)
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
            logger.info(f"Tool call response: {json.dumps(response, indent=2)}")
            return response
        
        else:
            logger.warning(f"Unknown method: {method}")
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
            logger.info(f"Error response: {json.dumps(response, indent=2)}")
            return response
    
    async def _call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool with detailed logging"""
        logger.info(f"=== Calling Tool: {name} ===")
        logger.info(f"Arguments: {arguments}")
        
        try:
            if name == "graphrag_search":
                result = await self._handle_search(arguments)
            elif name == "graphrag_health_check":
                result = await self._handle_health_check()
            else:
                raise ValueError(f"Unknown tool: {name}")
            
            logger.info(f"Tool {name} completed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Error in tool call {name}: {str(e)}")
            return {
                "content": [{"type": "text", "text": f"Error: {str(e)}"}]
            }
    
    async def _handle_search(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Handle GraphRAG search requests with detailed logging"""
        query = arguments.get("query", "")
        search_type = arguments.get("search_type", "basic")
        
        logger.info(f"=== GraphRAG Search ===")
        logger.info(f"Query: {query}")
        logger.info(f"Search Type: {search_type}")
        
        # Map search type to model
        model_mapping = {
            "local": "local_search",
            "global": "global_search", 
            "drift": "drift_search",
            "basic": "basic_search"
        }
        
        model = model_mapping.get(search_type, "basic_search")
        logger.info(f"Using model: {model}")
        
        # Prepare request payload
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": query}],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        headers = {"Content-Type": "application/json"}
        
        logger.info(f"Calling GraphRAG API: {self.config.api_base_url}/v1/chat/completions")
        logger.info(f"Payload: {json.dumps(payload, indent=2)}")
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(
                    f"{self.config.api_base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers
                )
                
                logger.info(f"API Response Status: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    content = result["choices"][0]["message"]["content"]
                    
                    logger.info(f"Search successful, content length: {len(content)}")
                    logger.info(f"Content preview: {content[:200]}...")
                    
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"**GraphRAG Search Result**\n\n**Query:** {query}\n**Search Type:** {search_type}\n**Model:** {model}\n\n{content}"
                        }]
                    }
                else:
                    error_msg = f"API request failed with status {response.status_code}: {response.text}"
                    logger.error(error_msg)
                    return {"content": [{"type": "text", "text": error_msg}]}
                    
        except Exception as e:
            error_msg = f"Error calling GraphRAG API: {str(e)}"
            logger.error(error_msg)
            return {"content": [{"type": "text", "text": error_msg}]}
    
    async def _handle_health_check(self) -> Dict[str, Any]:
        """Handle health check requests with detailed logging"""
        logger.info("=== GraphRAG Health Check ===")
        
        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.get(f"{self.config.api_base_url}/v1/health")
                
                logger.info(f"Health check response status: {response.status_code}")
                
                if response.status_code == 200:
                    health_data = response.json()
                    status_text = "✅ Healthy" if health_data.get("status") == "ok" else "❌ Unhealthy"
                    
                    logger.info(f"Health check successful: {health_data}")
                    
                    content = f"**GraphRAG Health Check**\n\n{status_text}\n\n**Details:**\n{json.dumps(health_data, indent=2)}"
                else:
                    content = f"❌ Health check failed with status {response.status_code}: {response.text}"
                    logger.error("Health check failed")
                
                return {"content": [{"type": "text", "text": content}]}
                
        except Exception as e:
            error_msg = f"Error checking health: {str(e)}"
            logger.error(error_msg)
            return {"content": [{"type": "text", "text": error_msg}]}

async def run_mcp_server():
    """Run the MCP server with detailed logging"""
    config = GraphRAGConfig()
    server = MCPServer(config)
    
    logger.info("=== Starting GraphRAG MCP Server ===")
    logger.info(f"API Base URL: {config.api_base_url}")
    logger.info("Waiting for MCP requests...")
    
    try:
        while True:
            # Read line from stdin
            line = sys.stdin.readline()
            if not line:
                logger.info("No more input, shutting down")
                break
            
            line = line.strip()
            if not line:
                continue
            
            logger.debug(f"Raw input: {line}")
            
            try:
                request = json.loads(line)
                response = await server.handle_request(request)
                
                # Write response to stdout
                response_line = json.dumps(response) + '\n'
                sys.stdout.write(response_line)
                sys.stdout.flush()
                
                logger.debug(f"Sent response: {response_line.strip()}")
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON: {e}")
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "Parse error"
                    }
                }
                error_line = json.dumps(error_response) + '\n'
                sys.stdout.write(error_line)
                sys.stdout.flush()
                
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server error: {e}")

async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="GraphRAG MCP Server with Debug Logging")
    parser.add_argument("--api-base-url", default="http://localhost:8000")
    parser.add_argument("--test", action="store_true")
    
    args = parser.parse_args()
    
    if args.test:
        # Test mode
        print("Testing GraphRAG MCP server...")
        config = GraphRAGConfig(api_base_url=args.api_base_url)
        server = MCPServer(config)
        
        # Test health check
        health_result = await server._handle_health_check()
        print(f"Health check: {json.dumps(health_result, indent=2)}")
        
        # Test search
        search_result = await server._handle_search({
            "query": "What is GraphRAG?",
            "search_type": "basic"
        })
        print(f"Search result: {json.dumps(search_result, indent=2)}")
        
    else:
        # Run MCP server
        await run_mcp_server()

if __name__ == "__main__":
    asyncio.run(main())
>>>>>>> d350dfe17e38aa01fa23e35fe3b1c04b1eae4e85
