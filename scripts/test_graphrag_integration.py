import requests
import json
import argparse

# 配置 GraphRAG 服务地址
def get_server_url():
    return "http://localhost:8000"

def test_index_codebase(config_path=None):
    url = f"{get_server_url()}/graphrag/index"
    payload = {
        "root_path": "./workspace/ragtest"
    }
    headers = {}
    if config_path:
        headers["GRAPHRAG_CONFIG_PATH"] = config_path
    response = requests.post(url, json=payload, headers=headers)
    print("[索引构建] 状态码:", response.status_code)
    print("[索引构建] 返回:", response.text)

def test_query(config_path=None):
    url = f"{get_server_url()}/graphrag/local_search_streaming"
    payload = {
        "query": "这个文章的内容是什么",
        "n_results": 5
    }
    headers = {}
    if config_path:
        headers["GRAPHRAG_CONFIG_PATH"] = config_path
    response = requests.post(url, json=payload, headers=headers)
    print("[查询] 状态码:", response.status_code)
    try:
        results = response.json()
        print("[查询] 返回结果:", results)
    except Exception as e:
        print("[查询] 解析失败:", e)
        print(response.text)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test GraphRAG integration.")
    parser.add_argument('--config', type=str, default=None, help='Path to GRAPHRAG_CONFIG_PATH (default: settings.yaml)')
    args = parser.parse_args()
    print("==== 测试 GraphRAG 索引构建 ====")
    test_index_codebase(args.config)
    print("\n==== 测试 GraphRAG 查询 ====")
    test_query(args.config)