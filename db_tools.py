import sqlite3
import json
from datetime import datetime

def init_work_orders_table():
    """初始化工单台账表"""
    conn = sqlite3.connect('factory_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS work_orders (
            order_id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            reason TEXT NOT NULL,
            priority TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'OPEN',
            created_at TEXT NOT NULL
        )
        ''')
    conn.commit()
    conn.close()

def insert_work_order(order_id: str, device_id: str, reason: str, priority: str) -> dict:
    """将 AI 派发的工单真实写入 SQLite"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn = sqlite3.connect('factory_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO work_orders (order_id, device_id, reason, priority, status, created_at)
        VALUES (?, ?, ?, ?, 'OPEN', ?)
    ''', (order_id, device_id, reason, priority, now))
    conn.commit()
    conn.close()
    return {
        "order_id": order_id,
        "device_id": device_id,
        "reason": reason,
        "priority": priority,
        "status": "OPEN",
        "created_at": now
    }

def list_work_orders() -> list:
    """按最新时间倒序查询所有历史工单"""
    conn = sqlite3.connect('factory_data.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT order_id, device_id, reason, priority, status, created_at
        FROM work_orders
        ORDER BY created_at DESC, rowid DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def resolve_work_order(order_id: str) -> bool:
    """将指定工单标记为已闭环"""
    conn = sqlite3.connect('factory_data.db')
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE work_orders
        SET status = 'RESOLVED'
        WHERE order_id = ?
    ''', (order_id,))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated
def query_device_history(device_id: str, limit: int = 5) -> str:
    """
    根据设备 ID 查询该设备的近期运行温度和状态历史。
    返回值将作为 JSON 字符串返回给大模型进行分析。
    """
    try:
        conn = sqlite3.connect('factory_data.db')
        # 设置 row_factory 以便能够像字典一样通过列名访问数据
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 执行 SQL 查询，按时间倒序获取该设备的最新记录
        cursor.execute('''
            SELECT timestamp, temperature, status 
            FROM device_telemetry 
            WHERE device_id = ? 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (device_id, limit))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return json.dumps({"error": f"未找到设备 {device_id} 的历史数据"})
            
        # 将查询结果转换为字典列表，再转成大模型能看懂的 JSON 字符串
        result = [dict(row) for row in rows]
        return json.dumps({"device_id": device_id, "history": result}, ensure_ascii=False)
        
    except Exception as e:
        return json.dumps({"error": f"数据库查询失败: {str(e)}"})

# 可以在文件底部加个简单的本地测试
if __name__ == "__main__":
    print("工具测试结果:", query_device_history("DEV-003", 3))