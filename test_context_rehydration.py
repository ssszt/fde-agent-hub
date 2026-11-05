import asyncio
from app.db.session_dao import SessionDAO
from app.services.agent_service import FactoryAgentService, SESSION_CHATS

async def test_rehydration_lifecycle():
    print("🚀 开始阶段 3 验证：大模型上下文冷启动回放测试...\n")
    
    test_session_id = "sess-rehydration-test"
    SessionDAO.delete_session(test_session_id) # 清理环境

    # 1. 模拟第 1 轮对话：告知关键个人信息与设备
    print("👉 第 1 轮对话发送中...")
    first_prompt = "你好，我是车间交接班主管张工，今天现场排查重点是3号机DEV-003。"
    async for _ in FactoryAgentService.run_dispatch_loop(first_prompt, session_id=test_session_id):
        pass
    print("✅ 第 1 轮排查交互完成，已流式持久化至数据库。")

    # 2. 模拟灾难性后端故障 / 重启：暴力清空内存缓存！
    print("\n💥 模拟突发状况：后端服务强杀重启，内存会话池被瞬间抹除！")
    SESSION_CHATS.clear()
    assert len(SESSION_CHATS) == 0, "内存未能成功清空！"
    print("✅ 确认内存中已没有任何会话实例：SESSION_CHATS 为空！")

    # 3. 模拟第 2 轮追问：测试大模型能否从 SQLite 回放中找回记忆
    print("\n👉 第 2 轮追问（冷启动恢复测试）...")
    second_prompt = "请问我是谁？我们今天要重点关注哪台设备？"
    round2_reply = ""
    async for event in FactoryAgentService.run_dispatch_loop(second_prompt, session_id=test_session_id):
        if event.startswith("event: delta"):
            # 提取文本
            import json
            data_str = event.split("data: ")[1].strip()
            data_obj = json.loads(data_str)
            round2_reply += data_obj.get("text", "")

    print(f"\n🤖 大模型冷启动回放后的回答：\n{round2_reply.strip()}\n")

    # 4. 断言验证记忆
    assert "张工" in round2_reply or "张" in round2_reply, "大模型未回忆起主管姓名！"
    assert "3号机" in round2_reply or "DEV-003" in round2_reply, "大模型未回忆起目标设备！"
    print("🎉 恭喜！Context Rehydration 验证 100% 成功！即使内存清空，模型依然精准找回记忆！")

if __name__ == "__main__":
    asyncio.run(test_rehydration_lifecycle())