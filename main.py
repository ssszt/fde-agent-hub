from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.agent_router import router as agent_router

app = FastAPI(
    title="FDE Industrial Agent Platform",
    description="企业级工业智能运维与业务工单闭环网关",
    version="1.0.0"
)

# 挂在跨域中间件，方便后续前端项目无缝调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# 挂载智能体路由
app.include_router(agent_router)

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "fde-agent-hub"}