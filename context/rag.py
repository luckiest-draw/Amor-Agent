"""RAG 检索 — ChromaDB 向量存储 + 检索.

切分策略: 表格 → 整块保护（不切），文本 → LangChain TextSplitter 智能切
"""

import re
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path
from context.reader import read_file

# OpenAI embeddings（与 LiteLLM 共用 API Key）
_default_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=None,
    model_name="text-embedding-3-small",
)

_client = chromadb.PersistentClient(path="./chroma_data")
_collection = _client.get_or_create_collection(
    name="documents",
    embedding_function=_default_ef,
)

# LangChain 的 RecursiveCharacterTextSplitter
# 优先在段落/换行处切，不行再降级到句号，最后才硬切
_splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,
    chunk_overlap=50,
    separators=["\n\n", "\n", "。", ".", "？", "?", "！", "!", "；", ";", " ", ""],
)


async def add_document(path: str | Path) -> None:
    """解析文件 → 表格保护 → 只切文本 → embedding → 存入 ChromaDB."""
    text = await read_file(path)
    filename = str(Path(path).name)

    # 1. 把 HTML 表格完整保护起来，不切
    tables: list[str] = []
    table_pattern = re.compile(r"<table>[\s\S]*?</table>", re.IGNORECASE)

    def _protect_table(match):
        tables.append(match.group())
        return f"{{TABLE_{len(tables) - 1}}}"

    protected_text = table_pattern.sub(_protect_table, text)

    # 2. 只切非表格的文本
    chunks = _splitter.split_text(protected_text)

    # 3. 把表格还原回去
    for i, table_html in enumerate(tables):
        chunks = [c.replace(f"{{TABLE_{i}}}", table_html) for c in chunks]

    # 4. 存入 ChromaDB
    for i, chunk in enumerate(chunks):
        if not chunk.strip():
            continue
        _collection.add(
            documents=[chunk],
            metadatas=[{"source": filename, "chunk": i}],
            ids=[f"{filename}_{i}"],
        )


async def query(query_text: str, top_k: int = 5) -> list[dict]:
    """检索与查询最相关的文档片段."""
    results = _collection.query(query_texts=[query_text], n_results=top_k)

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]

    return [
        {"text": doc, "source": meta.get("source", "unknown")}
        for doc, meta in zip(documents, metadatas)
    ]