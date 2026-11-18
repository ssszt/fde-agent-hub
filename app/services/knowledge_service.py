import os
import re
import json
import chromadb
from typing import List, Dict, Any,Optional, AsyncGenerator
from app.core.config import ai_client
from google.genai import types

CHROMA_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data",
"chroma_db")

os.makedirs(CHROMA_DATA_DIR, exist_ok=True)

class KnowledgeService:
  """
  企业级RAG知识库与向量检索服务
  """
  _chroma_client = None
  _collection = None

  @classmethod
  def get_collection(cls):
    if cls._collection is None:
      cls._chroma_client = chromadb.PersistentClient(path=CHROMA_DATA_DIR)
      cls._collection = cls._chroma_client.get_or_create_collection(
        name="industrial_sop_kb",
        metadata={"hnsw:space": "cosine"} # 使用余弦相似度空间
      )
    return cls._collection

  @staticmethod
  def chunk_markdown_by_section(content: str, source_name: str, device_id: str) -> List[Dict[str, Any]]:
    """
    章节语义切片
    按markdown 二级标题（##）切分，确保一个章节的‘步骤+警告+现象’作为一个独立chunk,绝不机械截断
    """
    chunks = []
    #按二级标题切分
    sections = re.split(r'\n(?=##\s+)', content)

    for index, section in enumerate(sections):
      section_text = section.strip()
      if not section_text:
        continue
      # 提取小节标题
      title_match = re.match(r'##\s+(.+)', section_text)
      section_title = title_match.group(1).strip() if title_match else f"第{index + 1}节"

      chunk_id = f"{device_id}_{os.path.splitext(source_name)[0]}_chunk_{index}"
      chunks.append({
        "id": chunk_id,
        "text": section_text,
        "metadata": {
          "source": source_name,
          "device_id": device_id,
          "section": section_title
        }
      })
    return chunks

  @classmethod
  def get_embedding(cls, text: str) -> List[float]:
    """
    利用现有的 Google text-embedding-004 进行文本向量化 (768维)
    """
    response = ai_client.models.embed_content(
      model="gemini-embedding-001",
      contents=text
    )
    return response.embeddings[0].values
  
  @classmethod
  def ingest_markdown_file(cls, file_path: str, device_id: str) -> Dict[str, Any]:
    """
    将本地 Markdown 工业手册解析、切片、向量化并持久化至 ChromaDB
    """
    if not os.path.exists(file_path):
      raise FileNotFoundError(f"文件不存在：{file_path}")
    file_name = os.path.basename(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
      content = f.read()
    
    chunks = cls.chunk_markdown_by_section(content, source_name=file_name, device_id=device_id)
    collection = cls.get_collection()

    ids = []
    documents = []
    metadatas = []
    embeddings = []

    for chunk in chunks:
      ids.append(chunk["id"])
      documents.append(chunk["text"])
      metadatas.append(chunk["metadata"])
      embeddings.append(cls.get_embedding(chunk["text"]))
    
    collection.upsert(
      ids=ids,
      documents=documents,
      metadatas=metadatas,
      embeddings=embeddings
    )

    return {
      "success": True,
      "file_name": file_name,
      "device_id": device_id,
      "chunks_count": len(chunks)
    }

  @classmethod
  def search_similar_chunks(cls, query: str, device_id: Optional[str] = None, top_k: int=3, min_similarity: float=0.5) -> List[Dict[str, Any]]:
    """
    元数据过滤 + 余弦相似度检索
    """
    collection = cls.get_collection()
    query_vector = cls.get_embedding(query)

    where_filter = {"device_id": device_id} if device_id else None

    results = collection.query(
      query_embeddings= [query_vector],
      n_results=top_k,
      where=where_filter
    )

    citations = []
    if results and results["documents"] and len(results["documents"][0]) > 0:
      docs = results["documents"][0]
      metas = results["metadatas"][0]
      distances = results["distances"][0]

      for i in range(len(docs)):
        # 余弦空间中：相似度 = 1 - 距离
        similarity = round(1-distances[i], 3)
        if similarity > min_similarity:
          citations.append({
            "source": metas[i].get("source", "未知文件"),
            "section": metas[i].get("section", "未知章节"),
            "device_id": metas[i].get("device_id", ""),
            "similarity": similarity,
            "content": docs[i]
          })
    return citations

  @classmethod
  async def stream_rag_chat(cls, query: str, device_id: Optional[str]=None) -> AsyncGenerator[str, None]:
    """
    SSE 双通道流式问答：
    1. event: citation 先发溯源结构化片段
    2. event: delta 流式输出严格受控的回答
    """
    citations = cls.search_similar_chunks(query=query, device_id=device_id, top_k=3, min_similarity=0.45)
    # 通道1：推送参考来源（Citations
    citation_payload = json.dumps({"citations": citations}, ensure_ascii=False)
    yield f"event: citation\ndata: {citation_payload}\n\n"

    # 若未检测到任何有效内容，触发拒答防线（绝不强行瞎编）
    if not citations:
      fallback_text=f"【知识库检索提示】在企业维保手册中未检索到与“{query}”直接相关的标准操作规程。出于安全防范考虑，请直接查阅原始纸质档案或联络设备厂商。"
      data_payload = json.dumps({"text": fallback_text}, ensure_ascii=False)
      yield f"event: delta\ndata: {data_payload}\n\n"
      return
    
    # 组装带严密 Grounding 的上下文
    context_str="\n\n---\n\n".join([
      f"【参考来源: {c['source']} | 章节: {c['section']} (置信度: {c['similarity']})】\n{c['content']}"
      for c in citations
    ])

    system_instruction = (
      "你是一个工业设备应急排查与维保规范专家助手。\n"
      "【严苛合规守则】：\n"
      "1. 你必须严格依据下方提供的【企业维保手册参考片段】回答现场工程师的提问。\n"
      "2. 回答应精确引用其中的工器具编号（如扳手规格）、阀门仪表编号以及安全防护要求。\n"
      "3. 如果参考片段中未提及某些细节，必须如实告知'手册未记载'，严禁凭空推测或给出不负责任的维修建议。"
    )

    user_prompt = f"参考维保手册】：\n{context_str}\n\n【工程师提问】：{query}\n\n请结合参考手册输出专业排查指导："

    # 调用 Gemini 流式接口
    config = types.GenerateContentConfig(
      system_instruction=system_instruction,
      temperature=0.1 # 极致低温，杜绝幻觉
    )

    response_stream = await ai_client.aio.models.generate_content_stream(
      model="gemini-2.5-flash",
      contents=user_prompt,
      config=config
    )

    # 通道2 流式推送文本增量
    async for chunk in response_stream:
      text_val = ""
      try:
        text_val = chunk.text
      except Exception:
        pass

      if text_val:
        data_payload = json.dumps({"text": text_val}, ensure_ascii=False)
        yield f"event: delta\ndata: {data_payload}\n\n"