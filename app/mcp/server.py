"""
FDE 工业智能运维 - 标准 MCP (Model Context Protocol) 服务端
支持 stdio 传输协议，可直接挂载至 Cursor / Claude Desktop / 外部智能体
"""
import os 
import sys

# 确保项目根目录在 sys.path 中，方便以独立脚本运行时正确导入 app/db 模块
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))

if project_root not in sys.path:
  sys.path.insert(0, project_root)

from mcp.server.mcpserver import MCPServer
from db_tools import query_device_history, insert_work_order
from app.services.knowledge_service import KnowledgeService

# 实例化标准mcp服务节点
mcp = MCPServer("FDE-Industrial-Hub")

DOCS_DIR = os.path.join(project_root,"data", "docs")

# ==========================================
# 原语 1: Tools (大模型主动调用的确定性函数)
# ==========================================

@mcp.tool()
def get_device_telemetry(device_id:str, limit: int=5) -> str:
  """
  【物理时序遥测】查询指定工业设备的历史运行温度、时间戳和运行状态记录。
  常用于排查设备近期是否存在超温趋势或严重故障(CRITICAL_FAULT)。
  """
  return query_device_history(device_id=device_id, limit=limit)


@mcp.tool()
def search_maintenance_sop(device_id: str, query: str) -> str:
  """
  【SOP向量检索】在企业私有 ChromaDB 知识库中向量检索指定设备的标准应急处置规程。
  返回精确包含扳手工具规格、机械泄压防烫警告及步骤的维保片段。
  """
  search_query = query.strip() if (query and query.strip()) else f"{device_id}冷却系统故障应急处置规程"
  citations = KnowledgeService.search_similar_chunks(
    query=search_query,
    device_id=device_id,
    top_k=2,
    min_similarity=0.4
  )
  if not citations:
    return f"知识库未检索到设备 {device_id} 的相关 SOP"
  result_lines = []
  for c in citations:
    result_lines.append(
      f"【来源: {c['source']} | 章节: {c['section']} (置信度: {c['similarity']})】\n{c['content']}"
    )
  return "\n\n---\n\n".join(result_lines)

@mcp.tool()
def dispatch_emergency_work_order(device_id: str, reason: str, priority: str="EMERGENCY") -> str:
  """
  【MES工单派发】当设备温度高于85°C或存在严重故障时，在企业系统为指定设备创建真实紧急维修工单。
  """
  import random
  from datetime import datetime
  order_id = f"WO-{datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

  record = insert_work_order(
    order_id=order_id,
    device_id=device_id,
    reason=reason,
    priority=priority
  )

  return json.dumps({
    "status": "SUCCESS",
    "order_id": order_id,
    "detail": f"工单已成功进入调度中心，设备: {device_id}, 原因: {reason}"
  }, ensure_ascii=False)

# ==========================================
# 原语 2: Resources (只读上下文资源，支持以 URI 协议读取)
# ==========================================

@mcp.resource("sop://{device_id}")
def read_device_sop_resource(device_id: str) -> str:
  """
  【企业只读资源】以 URI 协议读取指定设备的原始 Markdown SOP 全文。
  外部客户端可直接通过 URI 'sop://DEV-003' 挂载并读取原始维保文档。
  """
  file_name = f"{device_id}_冷却系统维保规程.md"
  file_path = os.path.join(DOCS_DIR, file_name)
  if not os.path.exists(file_path):
    return f"# 未找到设备 {device_id} 的专属维保规程文档"
  with open(file_path, "r", encoding="utf-8") as f:
    return f.read()

  
# 启动入口（默认 stdio 标准输入输出传输协议）
if __name__ == "__main__":
    mcp.run(transport="stdio")
