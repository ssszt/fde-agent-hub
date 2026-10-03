import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise RuntimeError("缺少GEMINI_API_KEY,请检查目录下的.env文件！")

# 导出全局可用的 AI 客户端实例
ai_client = genai.Client(api_key=GEMINI_API_KEY)