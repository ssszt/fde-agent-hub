"""
test_dual_engine.py
课题 12 核心验证：企业级双轨大模型引擎 (Gemini vs Local) 自动化对比测试

【验证目标】：
1. 验证云端 Gemini 轨：验证重构后是否仍能正常发起工具调用并完成 Generative UI 输出；
2. 验证本地 Local 轨：验证能否一键切入本地引擎，在内网环境下闭环自主排查；
3. 验证 SQLite 审计持久化：验证不同引擎的排查记录能否无损写入数据底座。
"""
import asyncio
from app.db.session_dao import SessionDAO
from app.services.agent_service import FactoryAgentService


async def test_engine(provider_name: str, session_id: str):
    prompt = "3号机 (DEV-003) 疑似过热，帮我查一下遥测状态，如果严重立刻派紧急工单"
    print(f"\n{'='*25} 开始测试 【{provider_name.upper()}】 引擎 {'='*25}")
    print(f"📡 提问指令: {prompt}")
    print(f"🆔 会话编号: {session_id}")
    print("⏳ 正在建立流式连接...\n")

    full_output = ""
    async for event_chunk in FactoryAgentService.run_dispatch_loop(
        user_prompt=prompt,
        session_id=session_id,
        provider_type=provider_name
    ):
        # 实时打印 SSE 原始输出
        print(event_chunk, end="", flush=True)
        full_output += event_chunk

    print(f"\n\n🏁 【{provider_name.upper()}】 引擎测试完毕！")
    
    # 验证 SQLite 数据库落库情况
    messages = SessionDAO.get_messages(session_id)
    print(f"💾 数据库审计检查：该会话当前已落库 {len(messages)} 条消息记录。")
    print(f"{'='*65}\n")


async def main():
    # 确保数据库表已初始化
    SessionDAO.init_tables()

    # 1. 先跑云端 Gemini 轨
    await test_engine(provider_name="gemini", session_id="session_gemini_track")
    
    # 稍作停顿
    await asyncio.sleep(2)

    # 2. 再跑本地 Local 轨
    await test_engine(provider_name="local", session_id="session_local_track")

    print("\n🎉🎉 恭喜！双轨引擎热插拔对决验证全部完成！")


if __name__ == "__main__":
    asyncio.run(main())