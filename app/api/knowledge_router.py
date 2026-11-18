from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.services.knowledge_service import KnowledgeService
from typing import Optional
import os
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/v1/knowledge", tags=["RAG Knowledge Base"])

class KnowledgeChatRequest(BaseModel):
  query: str=Field(..., example="DEV-003 高温异常且报 E-401 故障时，现场第一步该怎么排查？")
  device_id: Optional[str] = Field(default="DEV-003", description="设备ID前置过滤")

class IngestDocRequest(BaseModel):
  file_path: Optional[str] = Field(default=None, description="要入库的本地 Markdown 文件绝对/相对路径")
  device_id: str=Field(default="DEV-003", description="关联的设备编号")

@router.post("/ingest")
async def ingest_document(req: IngestDocRequest):
  """
  手动触发文档入库（默认解析 data/docs/DEV-003_冷却系统维保规程.md）
  """
  try:
    target_path = req.file_path
    if not target_path:
      # 默认路径
      base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
      target_path = os.path.join(base_dir, "data", "docs", "DEV-003_冷却系统维保规程.md")
    result = KnowledgeService.ingest_markdown_file(file_path=target_path, device_id=req.device_id)
    return {"success": True, "data": result, "message": "文档切片与向量入库完成！"}
    pass
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"入库失败: {str(e)}")

@router.post("/chat")
async def knowledge_chat_stream(req: KnowledgeChatRequest):
  """
  流式知识库问答 (SSE 协议: 包含 citation 参考来源与 delta 文本增量)
  """
  try:
    return StreamingResponse(
      KnowledgeService.stream_rag_chat(query=req.query, device_id=req.device_id),
      media_type="text/event-stream"
    )
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"知识库问答失败: {str(e)}")