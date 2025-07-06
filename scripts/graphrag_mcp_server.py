#!/usr/bin/env python3
"""
GraphRAG MCP Server with Debug Logging

This version includes detailed logging to verify MCP calls from Continue.
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path
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