# GraphRAG MCP Integration

This document describes how to use GraphRAG with the Model Context Protocol (MCP) to enable integration with VSCode Continue plugin and other AI assistants.

## Overview

The GraphRAG MCP server provides a standardized interface for AI assistants to interact with GraphRAG's search capabilities. It supports:

- **Local Search**: Search within specific communities in the knowledge graph
- **Global Search**: Search across all communities with dynamic community selection
- **Drift Search**: Analyze concept drift and temporal patterns
- **Basic Search**: Simple text-based search without graph structure
- **Health Check**: Verify system status and configuration

## Installation

1. Install the MCP dependency:
```bash
poetry add mcp
```

2. Ensure your GraphRAG configuration is set up in `settings.yaml`

## Usage with VSCode Continue

### Automatic Setup

The project includes a pre-configured `.continue/config.json` file that automatically sets up the MCP server:

```json
{
  "mcpServers": {
    "graphrag": {
      "command": "python",
      "args": ["scripts/graphrag_mcp_server.py"],
      "env": {
        "GRAPHRAG_CONFIG_PATH": "settings.yaml"
      }
    }
  }
}
```

### Manual Setup

If you need to customize the configuration:

1. Open VSCode settings
2. Search for "Continue MCP"
3. Add the GraphRAG MCP server configuration

## Available Tools

### graphrag_local_search

Perform focused searches within specific communities.

**Parameters:**
- `query` (required): The search query
- `community_level` (optional): Community level to search within (default: 1)
- `response_type` (optional): Response format - "json" or "text" (default: "json")

**Example:**
```json
{
  "query": "What are the key features of diabetes management?",
  "community_level": 1,
  "response_type": "json"
}
```

### graphrag_global_search

Search across all communities with dynamic community selection.

**Parameters:**
- `query` (required): The search query
- `community_level` (optional): Community level to search within (default: 1)
- `dynamic_community_selection` (optional): Enable dynamic community selection (default: true)
- `response_type` (optional): Response format - "json" or "text" (default: "json")

**Example:**
```json
{
  "query": "How do different medical conditions relate to each other?",
  "dynamic_community_selection": true,
  "response_type": "json"
}
```

### graphrag_drift_search

Analyze concept drift and temporal patterns in the knowledge graph.

**Parameters:**
- `query` (required): The search query
- `community_level` (optional): Community level to search within (default: 1)
- `response_type` (optional): Response format - "json" or "text" (default: "json")

**Example:**
```json
{
  "query": "How has diabetes treatment evolved over time?",
  "response_type": "json"
}
```

### graphrag_basic_search

Simple text-based search without graph structure.

**Parameters:**
- `query` (required): The search query

**Example:**
```json
{
  "query": "diabetes symptoms"
}
```

### graphrag_health_check

Check the health and status of the GraphRAG system.

**Parameters:** None

**Example:**
```json
{}
```

## Running the MCP Server

### Using the Launcher Script

```bash
# Basic usage with default config
python scripts/run_mcp_server.py

# With custom config
python scripts/run_mcp_server.py --config path/to/config.yaml

# With debug logging
python scripts/run_mcp_server.py --debug
```

### Direct Execution

```bash
python scripts/graphrag_mcp_server.py
```

## Environment Variables

- `GRAPHRAG_CONFIG_PATH`: Path to the GraphRAG configuration file (default: settings.yaml)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR)

## Troubleshooting

### Common Issues

1. **Configuration not found**: Ensure `settings.yaml` exists and is properly configured
2. **Data not loaded**: Check that the data paths in your configuration are correct
3. **Import errors**: Make sure all GraphRAG dependencies are installed

### Debug Mode

Enable debug logging to get more detailed information:

```bash
python scripts/run_mcp_server.py --debug
```

### Health Check

Use the health check tool to verify system status:

```json
{
  "tool": "graphrag_health_check",
  "arguments": {}
}
```

## Integration Examples

### VSCode Continue

Once configured, you can use GraphRAG tools directly in VSCode Continue:

1. Open a conversation with Continue
2. Ask questions like "Search for diabetes information using GraphRAG"
3. Continue will automatically use the appropriate GraphRAG tool

### Other MCP Clients

The MCP server can be used with any MCP-compatible client:

```bash
# Example with a generic MCP client
mcp-client --server python --args scripts/graphrag_mcp_server.py
```

## Development

### Adding New Tools

To add new tools to the MCP server:

1. Define the tool in `handle_list_tools()`
2. Implement the tool logic in `handle_call_tool()`
3. Update the documentation

### Testing

Test the MCP server:

```bash
# Test health check
echo '{"method": "tools/call", "params": {"name": "graphrag_health_check", "arguments": {}}}' | python scripts/graphrag_mcp_server.py
```

## Resources

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [VSCode Continue Documentation](https://continue.dev/docs)
- [GraphRAG Documentation](../index/README.md) 