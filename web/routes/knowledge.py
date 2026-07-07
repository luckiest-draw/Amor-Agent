"""知识库 API — 上传文档、管理 RAG."""

from fastapi import APIRouter, Request, UploadFile, File
from pathlib import Path
import shutil

router = APIRouter()

UPLOAD_DIR = Path("knowledge")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/knowledge/upload")
async def upload_document(request: Request, file: UploadFile = File(...)):
    """上传文档到知识库，自动解析 + 向量化存入 ChromaDB."""
    from context.rag import add_document

    # 保存到本地
    file_path = UPLOAD_DIR / file.filename
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 解析 + 切分 + embedding → ChromaDB
    await add_document(file_path)

    return {"filename": file.filename, "status": "indexed"}


@router.get("/knowledge/files")
async def list_files():
    """列出已上传的文件."""
    if not UPLOAD_DIR.exists():
        return {"files": []}
    return {"files": [f.name for f in UPLOAD_DIR.iterdir() if f.is_file()]}
