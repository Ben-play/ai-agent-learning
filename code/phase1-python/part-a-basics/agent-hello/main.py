"""我的第一个 Agent 项目骨架"""
from dotenv import load_dotenv
from pydantic import BaseModel
import os

# 加载环境变量
load_dotenv()

class Message(BaseModel):
    """消息模型 - 后续 Agent 的基础数据结构"""
    role: str
    content: str

def main():
    # 验证环境
    api_key = os.getenv("OPENAI_API_KEY", "not-set")
    print("✅ 项目初始化成功！")
    print(f"✅ API Key: {api_key[:10]}..." if len(api_key) > 10 else f"⚠️ API Key: {api_key}")

    # 验证 Pydantic
    msg = Message(role="user", content="Hello, Agent!")
    print(f"✅ Pydantic 工作正常: {msg.model_dump()}")

    # 验证类型提示
    def greet(name: str) -> str:
        return f"你好, {name}! 准备好学 Agent 了吗？"

    print(f"✅ {greet('同学')}")

if __name__ == "__main__":
    main()