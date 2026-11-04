import asyncio
from google.genai import types
from app.tools.registry import ToolRegistry, ToolResult


async def run_tests():
    print("🚀 开始 ToolRegistry 单元测试...")
    registry = ToolRegistry()

    # 1. 测试常规同步工具注册与调用
    @registry.register(
        name="mock_sync_tool",
        description="测试同步工具",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "msg": types.Schema(type=types.Type.STRING, description="测试消息")
            },
            required=["msg"]
        )
    )
    def mock_sync_tool(msg: str):
        return {"echo": msg, "len": len(msg)}

    # 2. 测试返回 ToolResult (带 display_text) 的工具
    @registry.register(
        name="mock_ui_tool",
        description="测试带 UI 渲染标记的工具",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "data_id": types.Schema(type=types.Type.STRING)
            }
        )
    )
    def mock_ui_tool(data_id: str = "default"):
        return ToolResult(
            result_data={"data_id": data_id, "val": 42},
            display_text=f"**【动态时序看板】**\nID: {data_id}"
        )

    # 3. 测试故意报错的工具 (验证 Error Boundary 安全防波堤)
    @registry.register(
        name="mock_failing_tool",
        description="测试故障工具",
        parameters=types.Schema(type=types.Type.OBJECT)
    )
    def mock_failing_tool():
        raise ConnectionResetError("模拟数据库连接超时！")

    # ---- 检验 1: 工具列表与导出 ----
    tools = registry.get_gemini_tools()
    assert len(tools) == 1, "get_gemini_tools 必须返回包含一个 Tool 对象的列表"
    decls = tools[0].function_declarations
    assert len(decls) == 3, f"声明数量应为 3，实际为 {len(decls)}"
    print("✅ [检验 1 通过] 工具声明生成正确，符合 GenAI SDK 规范。")

    # ---- 检验 2: 同步工具执行 ----
    res1, part1 = await registry.dispatch("mock_sync_tool", {"msg": "hello world"})
    assert not res1.is_error
    assert res1.result_data["echo"] == "hello world"
    assert part1.function_response.name == "mock_sync_tool"
    print("✅ [检验 2 通过] 同步工具正常分发，结果自动封装入 Part。")

    # ---- 检验 3: ToolResult 与 display_text 传递 ----
    res2, part2 = await registry.dispatch("mock_ui_tool", {"data_id": "DEV-999"})
    assert res2.display_text == "**【动态时序看板】**\nID: DEV-999"
    assert res2.result_data["val"] == 42
    print("✅ [检验 3 通过] ToolResult 契约保留了 display_text 渲染属性。")

    # ---- 检验 4: 安全防波堤拦截异常 ----
    res3, part3 = await registry.dispatch("mock_failing_tool", {})
    assert res3.is_error is True
    assert res3.result_data["status"] == "error"
    assert "ConnectionResetError" in res3.result_data["error_type"]
    assert part3.function_response.name == "mock_failing_tool"
    print("✅ [检验 4 通过] 防波堤成功拦截异常，没有崩溃，优雅降级生成了回填 Part！")

    print("\n🎉 全部 4 项核心测试全部通过！ToolRegistry 骨架稳固可用。")


if __name__ == "__main__":
    asyncio.run(run_tests())
