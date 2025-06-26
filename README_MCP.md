# GraphRAG MCP Integration - Quick Start Guide

This guide shows you how to quickly set up and use GraphRAG with the Model Context Protocol (MCP) for VSCode Continue integration.

## 🚀 Quick Setup

### 1. Install Dependencies

```bash
# Install MCP dependency
poetry add mcp

# Or if using pip
pip install mcp
```

### 2. Configure VSCode Continue

The project includes a pre-configured `.continue/config.json` file. If you need to customize it:

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

### 3. Start Using GraphRAG in VSCode

1. Open VSCode with the Continue extension installed
2. Open a conversation with Continue
3. Ask questions like:
   - "Search for diabetes information using GraphRAG local search"
   - "What are the symptoms of diabetes? Use GraphRAG to find out"
   - "How do different medical conditions relate to each other? Use GraphRAG global search"

## 🛠️ Available Tools

### Local Search
- **Best for**: Focused queries about specific topics
- **Usage**: "Use GraphRAG local search to find information about diabetes symptoms"

### Global Search  
- **Best for**: Broad queries spanning multiple topics
- **Usage**: "Use GraphRAG global search to understand how different medical conditions relate"

### Drift Search
- **Best for**: Analyzing temporal patterns and concept evolution
- **Usage**: "Use GraphRAG drift search to see how diabetes treatment has evolved"

### Basic Search
- **Best for**: Simple keyword searches
- **Usage**: "Use GraphRAG basic search to find diabetes management information"

## 🧪 Testing

### Test the MCP Server

```bash
# Run the test script
python scripts/test_mcp_server.py

# Or use the poetry command
poetry run graphrag-mcp-test
```

### Run Usage Example

```bash
# Run the example
python examples/mcp_usage_example.py

# Or use the poetry command
poetry run graphrag-mcp
```

## 🔧 Manual Server Launch

If you need to run the MCP server manually:

```bash
# Basic usage
python scripts/run_mcp_server.py

# With custom config
python scripts/run_mcp_server.py --config path/to/config.yaml

# With debug logging
python scripts/run_mcp_server.py --debug
```

## 📋 Prerequisites

- Python 3.10+
- GraphRAG configuration file (`settings.yaml`)
- GraphRAG data indexed and available
- VSCode with Continue extension

## 🐛 Troubleshooting

### Common Issues

1. **"Configuration not loaded"**
   - Ensure `settings.yaml` exists and is properly configured
   - Check the `GRAPHRAG_CONFIG_PATH` environment variable

2. **"Data not loaded"**
   - Verify that GraphRAG data is indexed and accessible
   - Check data paths in your configuration

3. **"Import errors"**
   - Make sure all dependencies are installed: `poetry install`
   - Verify Python path includes the project root

### Debug Mode

Enable debug logging for more detailed information:

```bash
python scripts/run_mcp_server.py --debug
```

### Health Check

Test system status:

```bash
# In VSCode Continue, ask:
"Check GraphRAG system health using the health check tool"
```

## 📚 More Information

- [Full MCP Integration Documentation](docs/mcp_integration.md)
- [GraphRAG Documentation](docs/index.md)
- [Model Context Protocol Specification](https://modelcontextprotocol.io/)

## 🤝 Contributing

To add new tools or improve the MCP integration:

1. Modify `scripts/graphrag_mcp_server.py`
2. Update the documentation
3. Add tests in `scripts/test_mcp_server.py`
4. Submit a pull request

## 📄 License

This MCP integration is part of GraphRAG and follows the same MIT license. 