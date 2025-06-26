#!/usr/bin/env python3
"""
Example usage of GraphRAG MCP Server

This example demonstrates how to use the GraphRAG MCP server programmatically.
"""

import asyncio
import json
import subprocess
import sys
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

async def example_mcp_usage():
    """Example of using the GraphRAG MCP server"""
    
    print("GraphRAG MCP Server Usage Example")
    print("=" * 50)
    
    # Start the MCP server
    process = subprocess.Popen(
        [sys.executable, "scripts/graphrag_mcp_server.py"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"GRAPHRAG_CONFIG_PATH": "settings.yaml"}
    )
    
    try:
        # Wait for server to start
        await asyncio.sleep(2)
        
        # Example 1: Health check
        print("\n1. Checking system health...")
        health_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "graphrag_health_check",
                "arguments": {}
            }
        }
        
        process.stdin.write(json.dumps(health_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        if response:
            result = json.loads(response)
            if "result" in result:
                health_data = json.loads(result["result"]["content"][0]["text"])
                print(f"✓ System Status: {health_data['status']}")
                print(f"  - Config loaded: {health_data['config_loaded']}")
                print(f"  - Data loaded: {health_data['data_loaded']}")
        
        # Example 2: Local search
        print("\n2. Performing local search...")
        local_search_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "graphrag_local_search",
                "arguments": {
                    "query": "What are the symptoms of diabetes?",
                    "community_level": 1,
                    "response_type": "json"
                }
            }
        }
        
        process.stdin.write(json.dumps(local_search_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        if response:
            result = json.loads(response)
            if "result" in result:
                content = result["result"]["content"][0]["text"]
                print(f"✓ Local search completed")
                print(f"  - Response length: {len(content)} characters")
                # Print first 200 characters of response
                print(f"  - Preview: {content[:200]}...")
        
        # Example 3: Global search
        print("\n3. Performing global search...")
        global_search_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "graphrag_global_search",
                "arguments": {
                    "query": "How do different medical conditions relate to each other?",
                    "dynamic_community_selection": True,
                    "response_type": "json"
                }
            }
        }
        
        process.stdin.write(json.dumps(global_search_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        if response:
            result = json.loads(response)
            if "result" in result:
                content = result["result"]["content"][0]["text"]
                print(f"✓ Global search completed")
                print(f"  - Response length: {len(content)} characters")
                print(f"  - Preview: {content[:200]}...")
        
        # Example 4: Basic search
        print("\n4. Performing basic search...")
        basic_search_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "graphrag_basic_search",
                "arguments": {
                    "query": "diabetes management"
                }
            }
        }
        
        process.stdin.write(json.dumps(basic_search_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        if response:
            result = json.loads(response)
            if "result" in result:
                content = result["result"]["content"][0]["text"]
                print(f"✓ Basic search completed")
                print(f"  - Response length: {len(content)} characters")
                print(f"  - Preview: {content[:200]}...")
        
        print("\n✓ All examples completed successfully!")
        
    except Exception as e:
        print(f"✗ Example failed with error: {e}")
    
    finally:
        # Clean up
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()

def main():
    """Main entry point"""
    # Check if settings.yaml exists
    if not Path("settings.yaml").exists():
        print("✗ settings.yaml not found. Please ensure you have a valid GraphRAG configuration.")
        return
    
    # Run the example
    asyncio.run(example_mcp_usage())

if __name__ == "__main__":
    main() 