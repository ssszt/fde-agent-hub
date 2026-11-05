import json
from typing import Any
from google.genai import types
from app.core.config  import ai_client
import app.tools.factory_tools
from app.tools.registry import tool_registry
from app.db.session_dao import SessionDAO

# 全局会话记忆池、基于 session_id 缓存各会话的活跃 Chat 实例
SESSION_CHATS: dict[str, any] = {}
FDE_SYSTEM_INSTRUCTION=(
    "你是一个工业物联网现场交付工程师专家助手（FDE Agent）。 \n"
    "【标准排查作业闭环流程】\n"
    "1.当用户要求排查设备时，必须先调用 query_device_history 查询设备的近期历史遥测数据。\n"
    "2.获得历史数据后，仔细检查：若设备温度高于85°C或存在CRITICAL_FAULT， 你必须立即调用 search_maintenance_sop 查询该设备专属的维保应急标准作业规程（SOP）。 \n"
    "3.充分研读SOP内容后，调用 create_work_order 派发紧急工单（EMERGENCY），工单的reason中必须概括SOP指出的根本原因与处置方向。 \n"
    "4.工单创建成功后，调用 send_sms_alert 向车间主管（手机号13800000000）发送紧急短信通知。\n"
    "5.最终输出结构严谨的排查终局报告：必须详细罗列 SOP 规程中的具体排查步骤(如阀门编号、 工具规格)、安全警告以及创建的工单号与短信回执。\n"
    "6.【上下文连续记忆规则】：当用户进行连续多轮询问（如询问上轮工单号、对比两台设备状态等）时，请结合历史对话上下文作答：若用户的问题无需再次查库或派单，直接基于上文记忆给出解答。"
)

class FactoryAgentService:
    @staticmethod
    def get_or_create_chat(session_id):
        # 若内存中没有该会话，自动从 SQLite 数据底座回放并重构 Gemini 历史上下文
        if session_id not in SESSION_CHATS:
            db_messages = SessionDAO.get_messages(session_id)
            rehydrated_history: List[types.Content] = []

            for msg in db_messages:
                # 转换角色：用户是 "user"，助手在 Gemini SDK 中需映射为 "model"
                gemini_role = "user" if msg["role"] == "user" else "model"
                if msg["content"]:
                    rehydrated_history.append(
                        types.Content(
                            role=gemini_role,
                            parts=[types.Part.from_text(text=msg["content"])]
                        )
                    )
            # 🛡️ 防御性守卫：Gemini 要求 history 必须以 model 结尾（或者为空）
            # 若历史最后一条不幸是悬空的 user（例如上次进程在中途崩溃未生成回复），将其弹出以保证严格交替
            if rehydrated_history and rehydrated_history[-1].role == "user":
                rehydrated_history.pop()

            config=types.GenerateContentConfig(
                system_instruction = FDE_SYSTEM_INSTRUCTION,
                tools=tool_registry.get_gemini_tools(),
                temperature=0.2,
            )
            # 注入历史回放，实现断点续接记忆唤醒
            SESSION_CHATS[session_id] = ai_client.aio.chats.create(
                model="gemini-2.5-flash", 
                config=config,
                history= rehydrated_history if rehydrated_history else None
            )
        return SESSION_CHATS[session_id]
    @staticmethod
    async def run_dispatch_loop(user_prompt:str, session_id:str = "default_session"):
        """
        核心调度中枢：基于 Tool Registry 的自愈式流式分发引擎
        """
        # 确保会话存在并写入用户提问
        session = SessionDAO.get_sessions(session_id)
        if not session:
            SessionDAO.create_session(session_id, title=user_prompt[:20] or "新排查会话")
        elif session["title"] in ["新排查会话", "string"]:
            # 首轮智能标题提取：自动以提问前 20 字更新标题
            SessionDAO.update_session_title(session_id, user_prompt[:20])
        # 取出或恢复上下文实例 、不再每次都新建chat，而是从会话池中取出该session的活跃chat
        chat = FactoryAgentService.get_or_create_chat(session_id)
        # C. 随后安全地将本次用户提问写入数据库
        SessionDAO.save_message(session_id=session_id, role="user", content=user_prompt)
        # 循环控制：设置 max_turns 熔断保护，防止模型陷入死循环（WLB 保障）
        max_turns = 5
        turn = 0
        current_input:Any = user_prompt
        full_assistant_text = ""
        recorded_tool_calls: List[Dict[str, Any]] = []
        try:
            while turn < max_turns:
                turn += 1
                response_stream = await chat.send_message_stream(current_input)
                pending_tool_calls = []
                async for chunk in response_stream:
                    # 拦截模型提出的所有工具调用意图
                    if chunk.function_calls:
                        for call in chunk.function_calls:
                            call_name = call.name
                            call_args = dict(call.args)
                            pending_tool_calls.append((call_name, call_args))
                            recorded_tool_calls.append({
                                "tool_name": call_name,
                                "arguments": call_args
                            })
                            # SSE 实时通知前端：升起对应的底层调度雷达卡片
                            tool_event_payload = json.dumps({
                                "tool_name": call_name,
                                "arguments": call_args
                            },ensure_ascii=False)
                            yield f"event: tool_call\ndata: {tool_event_payload}\n\n"
                    # 拦截普通分析文本，流式推送打字机效果
                    text_val = ''
                    try:
                        text_val = chunk.text
                    except Exception:
                        pass
                    if text_val:
                        data = json.dumps({"text": text_val},ensure_ascii=False)
                        yield f"event: delta\ndata: {data}\n\n"
                    # 如果这一轮流式结束后，模型没有发起任何工具调用，说明思考和输出完全结束，退出循环
                if not pending_tool_calls:
                    break
                # 阶段 3（核心突破）：本地执行物理操作，并将真实结果打包回填给 Gemini 大脑！统一分发调度并回填结果
                tool_responses = []
                for call_name, call_args in pending_tool_calls:
                    tool_result, part = await tool_registry.dispatch(call_name, call_args)
                    # 若该工具生成了 Generative UI 标记（如时序看板），直接通过 delta 推给前端
                    if tool_result.display_text:
                        data_payload = json.dumps({"text": tool_result.display_text}, ensure_ascii=False)
                        yield f"event: delta\ndata: {data_payload}\n\n"
                    tool_responses.append(part)
                current_input = tool_responses
        finally:
            # 流式结束后、安全将助手回复与工具轨迹落库
            if full_assistant_text or recorded_tool_calls:
                SessionDAO.save_message(session_id, role="assistant", content=full_assistant_text, tool_calls=recorded_tool_calls)
    
