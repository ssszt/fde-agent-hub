import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google import genai
from fastapi.responses import StreamingResponse

# 1.加载本地.env文件中的环境变量
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("请在.env文件中配置 GEMINI_API_KEY ！")


# 2.初始化Gemini客户端

ai_client = genai.Client(api_key=api_key)

# 3.创建 fastapi 应用
app = FastAPI(
    title = "FDE Agent Hub Gateway",
    description= "企业级智能体网关 - 已接入GEMINI 核心模型",
    version = "0.2.0"
)

# 4.定义请求与响应的数据模型

class AskAgentRequset(BaseModel):
    prompt: str
    system_instruction: str = "你是一个专业、冷静的企业级 FDE 前沿部署工程师助手，回答条理清晰、技术严谨。"

class AskAgentResponse(BaseModel):
    user_prompt: str
    reply: str
    model: str
# 5.编写真正的AI对话接口

@app.post("/v1/agent/chat", response_model=AskAgentResponse)

async def chat_with_gemini(req: AskAgentRequset):
    try:
        response = await ai_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=req.prompt,
            config= {
                "system_instruction": req.system_instruction,
                "temperature": 0.7
            }
        )

        return AskAgentResponse(
            user_prompt= req.prompt,
            reply= response.text,
            model= "gemini-2.5-flash"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI服务调用异常：{str(e)}")

# 异步生成器：逐块向客户端输出数据流
async def generate_gemini_stream(prompt:str, system_instruction: str):
    try:
        # 使用官方sdk提供的异步流式生成接口
        response_stream = await ai_client.aio.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "temperature": 0.7
            }
        )
        # 遍历流式反悔的每一个chunk
        async for chunk in response_stream:
            if chunk.text:
                # 遵循标准sse格式：每行以data开头， 以\n\n结尾
                yield f"data:{chunk.text}\n\n"
    except Exception as e:
        yield f"data:[ERROR]: {str(e)}\n\n"

# 定义流式接口
@app.post("/v1/agent/chat/stream")
async def chat_with_gemini_stream(req: AskAgentRequset):
    return StreamingResponse(
        generate_gemini_stream(req.prompt, req.system_instruction),
        media_type="text/event-stream"
    )