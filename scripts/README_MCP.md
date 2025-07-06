# GraphRAG MCP Server

这个目录包含了GraphRAG的MCP (Model Context Protocol) 服务器实现，允许VSCode插件如Continue通过标准化的MCP协议调用GraphRAG API。

## 文件说明

- `graphrag_mcp_server.py` - 完整的MCP服务器实现（需要mcp包）
- `graphrag_mcp_simple.py` - 简化的MCP服务器实现（独立运行）
- `mcp_config.json` - MCP配置文件示例
- `README_MCP.md` - 本说明文档

## 快速开始

### 1. 启动GraphRAG API服务器

首先启动GraphRAG的OpenAI兼容API服务器：

```bash
# 在项目根目录下
python scripts/graphrag_openai_wrapper.py --config settings.yaml
```

### 2. 测试MCP服务器

测试MCP服务器是否正常工作：

```bash
python scripts/graphrag_mcp_simple.py --test
```

### 3. 配置Continue插件

在Continue插件的配置文件中添加MCP服务器配置：

```json
{
  "mcpServers": {
    "graphrag": {
      "command": "python",
      "args": ["/path/to/graphrag/scripts/graphrag_mcp_simple.py"],
      "env": {
        "GRAPHRAG_API_URL": "http://localhost:8000"
      }
    }
  }
}
```

### 4. 使用MCP服务器

配置完成后，Continue插件就可以通过MCP协议调用GraphRAG的功能：

- `graphrag_search` - 执行GraphRAG搜索
- `graphrag_health_check` - 检查API健康状态

## 可用的工具

### graphrag_search

执行GraphRAG搜索查询。

**参数：**
- `query` (必需): 搜索查询字符串
- `search_type` (可选): 搜索类型，可选值：
  - `basic` - 基础搜索
  - `local` - 本地搜索
  - `global` - 全局搜索
  - `drift` - 漂移搜索

**示例：**
```json
{
  "name": "graphrag_search",
  "arguments": {
    "query": "What is GraphRAG?",
    "search_type": "basic"
  }
}
```

### graphrag_health_check

检查GraphRAG API服务器的健康状态。

**参数：** 无

**示例：**
```json
{
  "name": "graphrag_health_check",
  "arguments": {}
}
```

## 环境变量

- `GRAPHRAG_API_URL` - GraphRAG API服务器地址（默认：http://localhost:8000）
- `GRAPHRAG_API_KEY` - API密钥（可选）
- `GRAPHRAG_TIMEOUT` - 请求超时时间（默认：30秒）

## 故障排除

### 1. API服务器未启动

确保GraphRAG API服务器正在运行：

```bash
curl http://localhost:8000/v1/health
```

### 2. MCP服务器连接失败

检查MCP服务器配置和路径是否正确。

### 3. 搜索失败

检查API服务器日志以获取详细错误信息。

## 开发

### 添加新工具

在`graphrag_mcp_simple.py`中添加新的工具方法，并在`_define_tools()`中注册。

### 自定义配置

修改`GraphRAGConfig`类以支持更多配置选项。

## 相关链接

- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
- [Continue插件](https://continue.dev/)
- [GraphRAG文档](../README.md) 