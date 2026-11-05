import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_PATH = "factory_data.db"

class SessionDAO:
  """
  工业级会话与消息审计数据访问对象（DAO）
  统一封装sqlite 会话生命周期与消息记录管理
  """

  @staticmethod
  def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # 启用外键级联删除约束
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn
  @classmethod
  def init_tables(cls):
    # 初始化会话系统所需的数据表与索引
    with cls.get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
              session_id TEXT PRIMARY KEY,
              title TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
          )
      ''')
      cursor.execute('''
        CREATE TABLE IF NOT EXISTS session_messages (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              session_id TEXT NOT NULL,
              role TEXT NOT NULL,
              content TEXT NOT NULL,
              tool_calls TEXT,
              created_at TEXT NOT NULL,
              FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
          )
      ''')
      cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_messages_session 
          ON session_messages(session_id)
      ''')
      cursor.execute('''
          CREATE INDEX IF NOT EXISTS idx_sessions_updated 
          ON sessions(updated_at DESC)
      ''')
      conn.commit()
  
  @classmethod
  def create_session(cls, session_id: str, title: str="新排查会话") -> Dict[str, Any]:
    """新建一个排查会话"""
    now = datetime.now().isoformat()
    with cls.get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute('''
            INSERT INTO sessions (session_id, title, created_at, updated_at)
                VALUES (?, ?, ?, ?)
            ''', (session_id, title, now, now))
      conn.commit()
      return {
        "session_id": session_id,
        "title": title,
        "created_at": now,
        "updated_at": now
      }

  @classmethod
  def list_sessions(cls) -> List[Dict[str, Any]]:
    """获取所有历史会话列表，按最后更新时间倒序排列"""
    with cls.get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute('''
        SELECT session_id, title, created_at, updated_at
          FROM sessions
          ORDER BY updated_at DESC
      ''')
      rows = cursor.fetchall()
      return [dict(row) for row in rows]
  @classmethod
  def get_sessions(cls, session_id: str) -> Optional[Dict[str, Any]]:
    """获取单个会话元数据"""
    with cls.get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute('''
          SELECT session_id, title, created_at, updated_at
          FROM sessions
          WHERE session_id = ?
      ''', (session_id,))
      row = cursor.fetchone()
      return dict(row) if row else None
  @classmethod
  def update_session_title(cls, session_id: str, new_title: str) -> bool:
    """更新会话标题并刷新更新时间"""
    now = datetime.now().isoformat()  # 👈 【核心修复】：补上这一行时间戳定义！
    with cls.get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute('''
          UPDATE sessions 
          SET title = ?, updated_at = ?
          WHERE session_id = ?
      ''', (new_title, now, session_id))
      conn.commit()
      return cursor.rowcount > 0
  @classmethod
  def delete_session(cls, session_id: str) -> bool:
     """删除指定会话（依托外键级联，关联的消息会自动清空）"""
     with cls.get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
      conn.commit()
      return cursor.rowcount > 0
  
  @classmethod
  def save_message(cls, 
      session_id: str, 
      role: str, 
      content: str, 
      tool_calls: Optional[List[Dict[str, Any]]] = None) -> int:
      """持久化单条消息，若会话不存在则自动创建，并同步更新会话的 updated_at"""
      now = datetime.now().isoformat()
      tool_calls_json = json.dumps(tool_calls, ensure_ascii=False) if tool_calls else None
      with cls.get_connection() as conn:
        cursor = conn.cursor()
        # 1. 确保 session 存在（保底兼容旧请求）
        cursor.execute('SELECT 1 FROM sessions WHERE session_id = ?', (session_id,))
        if not cursor.fetchone():
          cursor.execute('''
                    INSERT INTO sessions (session_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?)
                ''', (session_id, "新排查会话", now, now))
        else:
          cursor.execute('UPDATE sessions SET updated_at = ? WHERE session_id = ?', (now, session_id))
        # 2.插入消息记录
        cursor.execute('''
            INSERT INTO session_messages (session_id, role, content, tool_calls, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (session_id, role, content, tool_calls_json, now))
        conn.commit()
        return cursor.lastrowid
  @classmethod
  def get_messages(cls, session_id: str) -> List[Dict[str, Any]]:
    """按时间正序回放指定会话的所有历史消息与工具轨迹"""
    with cls.get_connection() as conn:
      cursor = conn.cursor()
      cursor.execute('''
          SELECT id, session_id, role, content, tool_calls, created_at
          FROM session_messages
          WHERE session_id = ?
          ORDER BY id ASC
      ''', (session_id,))
      rows = cursor.fetchall()
      messages = []
      for row in rows:
        item = dict(row)
        if item["tool_calls"]:
          try:
            item["tool_calls"] = json.loads(item["tool_calls"])
          except Exception:
            pass
        messages.append(item)
      return messages


