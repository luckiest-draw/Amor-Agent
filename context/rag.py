"""RAG 检索 — ChromaDB 向量存储 + 检索.

切分: HanLP 中文语义切分 + 表格整块保护
向量: BGE 模型（本地推理，中文检索专训）
"""

import re
import chromadb
from chromadb.utils import embedding_functions
from pathlib import Path
from context.reader import read_file

# BGE 中文向量模型（本地跑，不花钱）
_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="BAAI/bge-large-zh-v1.5",
    device="cpu",
)

_client = chromadb.PersistentClient(path="./chroma_data")
_collection = _client.get_or_create_collection(
    name="documents",
    embedding_function=_ef,
)


def _hanlp_split(text: str) -> list[str]:
    """HanLP 语义切分，中文 NLP 模型判断句子边界。"""
    import hanlp
    tokenizer = hanlp.load(hanlp.pretrained.tok.COARSE_ELECTRA_SMALL_ZH)
    sentences: list[str] = tokenizer(text)
    # 按 500 字合块，50 字重叠
    chunks = []
    current = ""
    for s in sentences:
        if len(current) + len(s) <= 500:
            current += s
        else:
            if current:
                chunks.append(current)
            current = current[-50:] + s if len(current) > 50 else s
    if current:
        chunks.append(current)
    return chunks


async def add_document(path: str | Path) -> None:
    """解析 → 表格保护 → HanLP 切分 → BGE embedding → ChromaDB."""
    text = await read_file(path)
    filename = str(Path(path).name)

    # 1. 保护 HTML 表格
    tables: list[str] = []
    table_pattern = re.compile(r"<table>[\s\S]*?</table>", re.IGNORECASE)

    def _protect(match):
        tables.append(match.group())
        return f"{{TABLE_{len(tables) - 1}}}"

    protected_text = table_pattern.sub(_protect, text)

    # 2. HanLP 语义切分
    chunks = _hanlp_split(protected_text)

    # 3. 还原表格
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
    """BGE 向量检索最相关文档片段."""
    results = _collection.query(query_texts=[query_text], n_results=top_k)
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    return [
        {"text": doc, "source": meta.get("source", "unknown")}
        for doc, meta in zip(documents, metadatas)
    ]
