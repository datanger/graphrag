#!/usr/bin/env python3
"""
GraphRAG MCP Server Launcher

This script launches the GraphRAG MCP server for use with VSCode Continue plugin.
"""

import argparse
import os
import sys
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="Launch GraphRAG MCP Server")
    parser.add_argument(
        '--config', 
        type=str, 
        default='settings.yaml',
        help='Path to GraphRAG configuration file (default: settings.yaml)'
    )
    parser.add_argument(
        '--debug', 
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Set environment variables
    os.environ["GRAPHRAG_CONFIG_PATH"] = args.config
    
    if args.debug:
        os.environ["LOG_LEVEL"] = "DEBUG"
    
    # Add project root to Python path
    project_root = str(Path(__file__).parent.parent)
    if project_root not in sys.path:
        sys.path.append(project_root)
    
    # Import and run the MCP server
    from scripts.graphrag_mcp_server import main as run_mcp_server
    
    print(f"Starting GraphRAG MCP Server with config: {args.config}")
    print("Press Ctrl+C to stop the server")
    
    try:
        import asyncio
        asyncio.run(run_mcp_server())
    except KeyboardInterrupt:
        print("\nMCP Server stopped by user")
    except Exception as e:
        print(f"Error running MCP server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 