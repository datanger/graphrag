#!/usr/bin/env python3
"""
Test script for GraphRAG MCP Server

This script tests the MCP server functionality by sending test requests.
"""

import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

# Add project root to path
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

async def test_mcp_server():
    """Test the MCP server with various requests"""
    
    print("Starting GraphRAG MCP Server test...")
    
    # Start the MCP server as a subprocess
    process = subprocess.Popen(
        [sys.executable, str(Path("scripts/graphrag_mcp_server.py"))],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env={"GRAPHRAG_CONFIG_PATH": str(Path("settings.yaml"))}
    )
    
    try:
        # Wait a moment for server to start
        await asyncio.sleep(2)
        
        # Test 1: List tools
        print("\n1. Testing list tools...")
        list_tools_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {}
        }
        
        process.stdin.write(json.dumps(list_tools_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        if response:
            result = json.loads(response)
            print(f"✓ Tools listed: {len(result.get('result', {}).get('tools', []))} tools found")
        else:
            print("✗ No response from server")
            return
        
        # Test 2: Health check
        print("\n2. Testing health check...")
        health_check_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "graphrag_health_check",
                "arguments": {}
            }
        }
        
        process.stdin.write(json.dumps(health_check_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        if response:
            result = json.loads(response)
            if "result" in result:
                print("✓ Health check passed")
                health_status = json.loads(result["result"]["content"][0]["text"])
                print(f"  - Config loaded: {health_status.get('config_loaded', False)}")
                print(f"  - Data loaded: {health_status.get('data_loaded', False)}")
            else:
                print(f"✗ Health check failed: {result.get('error', 'Unknown error')}")
        else:
            print("✗ No response from health check")
        
        # Test 3: Basic search
        print("\n3. Testing basic search...")
        basic_search_request = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "graphrag_basic_search",
                "arguments": {
                    "query": "diabetes"
                }
            }
        }
        
        process.stdin.write(json.dumps(basic_search_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        if response:
            result = json.loads(response)
            if "result" in result:
                print("✓ Basic search completed")
                content = result["result"]["content"][0]["text"]
                print(f"  - Response length: {len(content)} characters")
            else:
                print(f"✗ Basic search failed: {result.get('error', 'Unknown error')}")
        else:
            print("✗ No response from basic search")
        
        # Test 4: List resources
        print("\n4. Testing list resources...")
        list_resources_request = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "resources/list",
            "params": {}
        }
        
        process.stdin.write(json.dumps(list_resources_request) + "\n")
        process.stdin.flush()
        
        response = process.stdout.readline()
        if response:
            result = json.loads(response)
            if "result" in result:
                resources = result["result"]["resources"]
                print(f"✓ Resources listed: {len(resources)} resources found")
                for resource in resources:
                    print(f"  - {resource['name']}: {resource['uri']}")
            else:
                print(f"✗ List resources failed: {result.get('error', 'Unknown error')}")
        else:
            print("✗ No response from list resources")
        
        print("\n✓ All tests completed!")
        
    except Exception as e:
        print(f"✗ Test failed with error: {e}")
    
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
    print("GraphRAG MCP Server Test")
    print("=" * 40)
    
    # Check if settings.yaml exists
    if not Path("settings.yaml").exists():
        print("✗ settings.yaml not found. Please ensure you have a valid GraphRAG configuration.")
        return
    
    # Run the test
    asyncio.run(test_mcp_server())

if __name__ == "__main__":
    main() 