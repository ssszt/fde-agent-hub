import uuid
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from app.db.session_dao import SessionDAO
from app.schemas.session_schema import (
    SessionItem, 
    CreateSessionRequest, 
    UpdateSessionRequest, 
    SessionMessagesResponse,
    MessageItem
)

router = APIRouter(prefix="/v1/sessions", tags=["Session Workbench Management"])

@router.get("", response_model=List[SessionItem], summary="获取所有历史会话列表")
async def list_sessions():
  try:
    return SessionDAO.list_sessions()
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"获取会话列表失败: {str(e)}")

@router.post("", response_model=SessionItem, status_code=status.HTTP_201_CREATED, summary="新建排查会话")
async def create_session(req:CreateSessionRequest):
  try:
    # 如果未传入 session_id，自动生成易于辨识的带时间戳短 ID
    session_id = req.session_id or f"sess-{uuid.uuid4().hex[:8]}"
    session = SessionDAO.create_session(session_id=session_id, title=req.title or "新排查会话")
    return session
  except Exception as e:
    raise HTTPException(status_code=500, detail=f"创建会话失败: {str(e)}")


@router.get("/{session_id}/messages", response_model=SessionMessagesResponse, summary="获取指定会话的历史消息流")
async def get_session_messages(session_id: str):
  session = SessionDAO.get_sessions(session_id)
  if not session:
    raise HTTPException(status_code=404, detail=f"未找到会话 {session_id}")
  raw_messages = SessionDAO.get_messages(session_id)

  return SessionMessagesResponse(
    session_id=session_id,
    messages=[MessageItem(**msg) for msg in raw_messages]
  )

@router.patch("/{session_id}", summary="修改会话标题")
async def update_session_title(session_id: str, req: UpdateSessionRequest):
  success = SessionDAO.update_session_title(session_id, req.title)
  if not success:
    raise HTTPException(status_code=404, detail=f"未找到会话 {session_id}")
  return {"message": "标题更新成功", "session_id": session_id, "new_title": req.title}


@router.delete("/{session_id}", summary="删除指定会话")
async def delete_session(session_id: str):
    success = SessionDAO.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"未找到会话 {session_id}")
    return {"message": f"会话 {session_id} 及其关联记录已完全清除"}


