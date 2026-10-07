import sqlite3

def init_mock_db():
    # 连接到sqllite数据库，不存在会自动创建
    conn = sqlite3.connect('factory_data.db')
    cursor = conn.cursor()


    # 创建一张设备遥测历史表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS device_telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            temperature REAL NOT NULL,
            status TEXT NOT NULL,
            data TEXT
        )
    ''')

    # 清空旧数据，防止重复运行导致数据堆积
    cursor.execute('DELETE FROM device_telemetry')

    # 插入3号机发生故障前后的模拟数据
    mock_data = [
        ('DEV-003', '2026-10-05 08:00:00', 65.2, 'NORMAL'),
        ('DEV-003', '2026-10-05 09:00:00', 68.5, 'NORMAL'),
        ('DEV-003', '2026-10-05 10:00:00', 75.1, 'WARNING'),
        ('DEV-003', '2026-10-05 11:00:00', 88.3, 'CRITICAL_FAULT'),
        ('DEV-003', '2026-10-06 22:30:00', 98.0, 'CRITICAL_FAULT')
    ]

    cursor.executemany('''
        INSERT INTO device_telemetry (device_id, timestamp, temperature, status)
            VALUES (?, ?, ?, ?)
        ''', mock_data)

    conn.commit()
    conn.close()
    print("✅ 本地业务数据库 (factory_data.db) 初始化完成！共写入 5 条历史记录。")


if __name__ == "__main__":
    init_mock_db()