from app.db.session_dao import SessionDAO

def test_session_lifecycle():
  print("🚀 开始阶段 1 单元测试：SessionDAO 持久化测试...")
  
  # 1.初始化表
  SessionDAO.init_tables()
  print("✅ 表结构初始化成功！")

  # 2.创建会话
  test_sid = "test-session-dev003"
  SessionDAO.delete_session(test_sid) # 清理历史残余
  session = SessionDAO.create_session(test_sid, "DEV-003 超温故障排查")
  print(f"✅ 创建会话成功: {session['title']} (ID: {session['session_id']})")

  # 3.记录第一轮用户提问
  SessionDAO.save_message(
    session_id=test_sid,
    role="user",
    content="请排查3号机当前的运行状态并给出建议"
  )

  # 4. 记录第 1 轮：助理回复（包含工具调用足迹）
  mock_tools = [
      {"tool_name": "query_device_history", "arguments": {"device_id": "DEV-003"}},
      {"tool_name": "create_work_order", "arguments": {"device_id": "DEV-003", "priority": "EMERGENCY"}}
  ]
  SessionDAO.save_message(
      session_id=test_sid,
      role="assistant",
      content="发现 DEV-003 温度高达 98°C，已为您派发紧急工单 WO-20261006-001。",
      tool_calls=mock_tools
  )
  print("✅ 消息与工具调用轨迹入库成功！")

  # 5. 回放消息历史
  history = SessionDAO.get_messages(test_sid)
  assert len(history) == 2, f"期望 2 条消息，实际获取到 {len(history)} 条"
  assert history[1]["tool_calls"][0]["tool_name"] == "query_device_history"
  print(f"✅ 历史消息回放验证通过！共回溯 {len(history)} 条对话，工具轨迹还原准确。")
  # 6. 会话列表检索
  sessions = SessionDAO.list_sessions()
  target = next((s for s in sessions if s["session_id"] == test_sid), None)
  assert target is not None
  print(f"✅ 历史会话列表获取成功，当前总会话数: {len(sessions)}")
  # 7. 级联删除验证
  SessionDAO.delete_session(test_sid)
  cleared_history = SessionDAO.get_messages(test_sid)
  assert len(cleared_history) == 0, "级联删除失败，子表消息未被清空！"
  print("✅ 级联清理测试通过，外键约束运转正常！")
  
  print("\n🎉 阶段 1 数据底座与 DAO 封装 100% 验收通过！")
if __name__ == "__main__":
    test_session_lifecycle()