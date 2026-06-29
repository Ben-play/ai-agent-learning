from dotenv import load_dotenv
import os

load_dotenv()  # 加载 .env 文件

api_key = os.getenv("OPENAI_API_KEY")
print(f"Key loaded: {api_key[:10]}...")  # 只打印前10位