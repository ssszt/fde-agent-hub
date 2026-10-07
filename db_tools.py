import sqlite3
import json

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