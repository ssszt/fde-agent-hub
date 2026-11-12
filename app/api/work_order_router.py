import csv
import io
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from db_tools import list_work_orders, resolve_work_order

router = APIRouter(prefix="/v1/work-orders", tags=["Work Order Ledger"])

@router.get("", summary="获取历史工单台账")
async def get_work_orders():
  return list_work_orders()

@router.patch("/{order_id}/resolve", summary="确认工单已处理闭环")
async def mark_work_order_resolved(order_id: str):
  ok = resolve_work_order(order_id)
  if not ok:
    raise HTTPException(status_code=404, detail=f"未找到工单 {order_id}")
  return {"message": f"工单 {order_id} 已标记为已闭环", "order_id": order_id, "status": "RESOLVED"}

@router.get("/export", summary="导出工单台账 CSV 报表")
async def export_work_orders_csv():
  orders = list_work_orders()
  output = io.StringIO()
  writer = csv.writer(output)
  writer.writerow(["工单编号", "设备编号", "故障原因", "优先级", "当前状态", "创建时间"])
  for row in orders:
    writer.writerow([
      row["order_id"],
      row["device_id"],
      row["reason"],
      row["priority"],
      row["status"],
      row["created_at"],
    ])
  # 加上 utf-8-sig BOM 头，确保 Excel 打开中文不乱码
  csv_bytes = output.getvalue().encode("utf-8-sig")
  return Response(
    content=csv_bytes,
    media_type="text/csv; charset=utf-8",
    headers={"Content-Disposition": "attachment; filename=work_orders.csv"}
  )