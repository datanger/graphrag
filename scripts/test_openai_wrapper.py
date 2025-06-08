import openai
import asyncio
import sys
import os

# Add parent directory to path to import from graphrag_server
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure the OpenAI client to use our local server
client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="dummy_key"  # Not used by our wrapper
)

def test_chat_completion():
    """Test the chat completion endpoint"""
    try:
        response = client.chat.completions.create(
            model="local_search",  # Will use global_search
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "这个项目代码的作用"}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        print("Chat Completion Response:")
        print(response.choices[0].message.content)
        return True
    except Exception as e:
        print(f"Error in chat completion: {e}")
        return False

async def test_streaming():
    """Test the streaming chat completion"""
    try:
        stream = client.chat.completions.create(
            model="local_search",  # Will use drift_search
            messages=[
                {"role": "user", "content": "这个项目代码的作用"}
            ],
            stream=True
        )
        
        print("\nStreaming Response:")
        for chunk in stream:
            content = chunk.choices[0].delta.content or ""
            print(content, end="", flush=True)
        print("\n")
        return True
    except Exception as e:
        print(f"Error in streaming: {e}")
        return False

if __name__ == "__main__":
    print("==== Testing OpenAI Compatible API ====")
    
    # Test regular chat completion
    print("\n[1/2] Testing chat completion...")
    success = test_chat_completion()
    
    # Test streaming
    print("\n[2/2] Testing streaming...")
    success_stream = asyncio.run(test_streaming())
    
    print("\n==== Test Summary ====")
    print(f"Chat Completion: {'✓' if success else '✗'}")
    print(f"Streaming: {'✓' if success_stream else '✗'}")
