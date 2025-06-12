import os
import httpx
import asyncio
from openai import AsyncOpenAI
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 配置信息
API_BASE_URL = "http://localhost:8001/v1"  # FastAPI服务地址
TEST_MODEL = "DeepSeek-V3-W8A8"

# 设置虚拟的API密钥以满足OpenAI客户端要求
os.environ["OPENAI_API_KEY"] = "dummy-key"

# 初始化客户端 - 添加虚拟API密钥
async_client = AsyncOpenAI(
    base_url=API_BASE_URL,
    api_key=os.environ["OPENAI_API_KEY"]  # 添加虚拟密钥
)

async def test_non_streaming():
    """测试非流式调用"""
    logger.info("\n=== 测试非流式调用 ===")
    
    try:
        response = await async_client.chat.completions.create(
            model=TEST_MODEL,
            messages=[{"role": "user", "content": "你是"}],
            temperature=0.7,
            max_tokens=500,
            stream=False
        )
        
        logger.info(f"响应ID: {response.id}")
        logger.info(f"模型: {response.model}")
        logger.info(f"回复内容: \n{response.choices[0].message.content}")
        logger.info(f"Token使用: {response.usage}")
        return True
    except Exception as e:
        logger.error(f"非流式调用失败: {str(e)}")
        return False

async def test_streaming():
    """测试流式调用 - 增强错误处理"""
    logger.info("\n=== 测试流式调用 ===")
    
    try:
        stream = await async_client.chat.completions.create(
            model=TEST_MODEL,
            messages=[{"role": "user", "content": "你是"}],
            temperature=0.7,
            max_tokens=500,
            stream=True
        )
        
        logger.info("实时流式输出:")
        full_response = ""
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                print(content, end="", flush=True)
                full_response += content
        
        logger.info(f"\n\n完整回复长度: {len(full_response)}字符")
        return True
    except Exception as e:
        logger.error(f"流式调用失败: {str(e)}")
        return False

def test_direct_http():
    """测试直接HTTP请求"""
    logger.info("\n=== 测试直接HTTP请求 ===")
    
    # 非流式
    try:
        response = httpx.post(
            f"{API_BASE_URL}/chat/completions",
            json={
                "model": TEST_MODEL,
                "messages": [{"role": "user", "content": "法国的首都是哪里？"}],
                "temperature": 0.5
            },
            timeout=10.0
        )
        logger.info(f"[非流式] 状态码: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            logger.info(f"[非流式] 响应ID: {data.get('id')}")
            logger.info(f"[非流式] 内容: {data['choices'][0]['message']['content']}")
        else:
            logger.info(f"[非流式] 错误: {response.text}")
    except Exception as e:
        logger.error(f"非流式HTTP请求失败: {str(e)}")
    
    # 流式 - 使用更健壮的处理方式
    try:
        with httpx.Client(timeout=None) as client:  # 禁用超时
            with client.stream(
                "POST",
                f"{API_BASE_URL}/chat/completions",
                json={
                    "model": TEST_MODEL,
                    "messages": [{"role": "user", "content": "请用三句话介绍你自己"}],
                    "stream": True
                }
            ) as response:
                logger.info(f"[流式] 状态码: {response.status_code}")
                logger.info("流式内容:")
                for chunk in response.iter_lines():
                    if chunk.strip():
                        logger.info(chunk)
        return True
    except Exception as e:
        logger.error(f"流式HTTP请求失败: {str(e)}")
        return False

async def test_concurrent_requests():
    """测试并发请求"""
    logger.info("\n=== 测试并发请求 ===")
    
    async def make_request(i):
        try:
            response = await async_client.chat.completions.create(
                model=TEST_MODEL,
                messages=[{"role": "user", "content": f"这是第{i}个并发请求，请返回数字{i}"}],
                temperature=0.1
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"请求失败: {str(e)}"
    
    tasks = [make_request(i) for i in range(3)]
    results = await asyncio.gather(*tasks)
    
    for i, result in enumerate(results):
        logger.info(f"请求{i}结果: {result}")
    
    return True

async def test_error_handling():
    """测试错误处理"""
    logger.info("\n=== 测试错误处理 ===")
    
    success = True
    
    # 测试无效模型
    try:
        await async_client.chat.completions.create(
            model="invalid-model",
            messages=[{"role": "user", "content": "这应该会失败"}]
        )
        logger.error("无效模型测试没有失败，不符合预期")
        success = False
    except Exception as e:
        logger.info(f"1. 无效模型错误: {type(e).__name__}: {e}")
    
    # 测试无效消息
    try:
        await async_client.chat.completions.create(
            model=TEST_MODEL,
            messages=[{"role": "invalid-role", "content": ""}]
        )
        logger.error("无效消息测试没有失败，不符合预期")
        success = False
    except Exception as e:
        logger.info(f"2. 无效消息错误: {type(e).__name__}: {e}")
    
    return success

async def main():
    logger.info("开始API测试...")
    
    test_results = {
        # "非流式": await test_non_streaming(),
        "流式": await test_streaming(),
        # "直接HTTP": test_direct_http(),
        # "并发请求": await test_concurrent_requests(),
        # "错误处理": await test_error_handling()
    }
    
    logger.info("\n测试结果汇总:")
    for test_name, success in test_results.items():
        status = "成功" if success else "失败"
        logger.info(f"{test_name}测试: {status}")
    
    logger.info("\n所有测试完成!")

if __name__ == "__main__":
    asyncio.run(main())