import asyncio
from pydantic import BaseModel
from fastapi import FastAPI
app = FastAPI(
    title= "FDE Agent Hub Gatewagy",
    description = "企业级智能知识库与业务交互平台 - API网关",
    version = '0.1.0'
)

@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "FDE Hub Backend",
        "message": "Hello From FastAPI Gateway!"
    }
@app.get("/health")
async def health_check():
    return {"status": "health", "database": "ready"}

@app.get("/simulate-ai")
async def simulate_ai():
    await asyncio.sleep(2)
    return {"reply": "这是大模型模拟返回的异步结果"}

@app.post("/ask")

class ChatRequset(BaseModel):
    massage: str
async def ask(req: ChatRequset):
    return {
        "recevied": req.massage,
        "reply": f"后端已收到你的消息：'{req.massage}', 准备调用大模型！"
    }
