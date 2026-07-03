# Amor Agent v3 实现计划（完整版）

> 每个 Task 包含完整代码。确定性模块有测试，Agent 逻辑用 MockLLM 验证。

---

## Phase 1: 数据层

### Task 1.1: 数据库引擎 + Base

你已经写完 `amor/config.py` 的 `database_url`。继续建数据库连接。

**文件:** `db/engine.py`

```python
"""PostgreSQL 异步引擎 + session 工厂."""

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from amor.config import AmorConfig

config = AmorConfig()

engine = create_async_engine(
    config.database_url,
    echo=False,          # 生产环境关掉，调试时可开 True
    pool_size=10,        # 连接池大小
    max_overflow=20,     # 超出 pool_size 后最多再开 20 个
)

async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # 异步模式必须关，否则 commit 后属性访问报错
)


async def get_db() -> AsyncSession:
    """FastAPI 依赖注入用 — 每个请求独立 session，用完自动关闭."""
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

**文件:** `db/base.py`

```python
"""SQLAlchemy 声明式基类 — 所有 Model 继承它."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

**验证:**
```bash
python -c "from db.engine import engine; from db.base import Base; print('OK')"
```

---

### Task 1.2: 数据库 Model（7 张表）

按照设计文档的表结构，逐个创建。放在 `db/models/` 下，一个表一个文件。

**`db/models/conversation.py`** — 会话表:

```python
"""会话 — 一次完整的用户对话."""

from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500), default="New Chat")
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # 关联
    messages = relationship("Message", back_populates="conversation", lazy="selectin")
    tasks = relationship("Task", back_populates="conversation", lazy="selectin")
```

**`db/models/message.py`** — 对话消息表:

```python
"""对话消息 — 一次对话中的每条消息."""

from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(50))   # user / assistant / system / tool
    content: Mapped[str] = mapped_column(Text, default="")
    tool_calls: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    token_usage: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    cost: Mapped[float | None] = mapped_column(nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation = relationship("Conversation", back_populates="messages")
```

**`db/models/memory.py`** — 持久记忆表:

```python
"""持久记忆 — 跨会话记住用户偏好与关键信息."""

from datetime import datetime
from sqlalchemy import String, Float, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict)
    importance: Mapped[float] = mapped_column(Float, default=0.5)
    last_accessed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**`db/models/task.py`** — 任务与步骤表:

```python
"""任务与步骤 — Agent 执行的任务及其拆解步骤."""

from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    plan: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    conversation = relationship("Conversation", back_populates="tasks")
    steps = relationship("TaskStep", back_populates="task", lazy="selectin")


class TaskStep(Base):
    __tablename__ = "task_steps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE")
    )
    agent_role: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    depends_on: Mapped[list[int] | None] = mapped_column(JSONB, nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    task = relationship("Task", back_populates="steps")
    executions = relationship("AgentExecution", back_populates="task_step", lazy="selectin")
```

**`db/models/agent.py`** — Agent 定义与执行记录:

```python
"""Agent 定义与执行记录."""

from datetime import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db.base import Base


class Agent(Base):
    __tablename__ = "agents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    role: Mapped[str] = mapped_column(String(100))
    system_prompt: Mapped[str] = mapped_column(nullable=True)
    tools: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("agents.id"))
    task_step_id: Mapped[int] = mapped_column(
        ForeignKey("task_steps.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String(50), default="running")
    input: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tool_calls: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[float] = mapped_column(Float, default=0.0)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error: Mapped[str | None] = mapped_column(nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    task_step = relationship("TaskStep", back_populates="executions")
```

**`db/models/checkpoint.py`** — Loop 检查点:

```python
"""检查点 — Loop 层的状态快照，挂了能恢复."""

from datetime import datetime
from sqlalchemy import Integer, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from db.base import Base


class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    state: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

**`db/models/__init__.py`** — 统一导入:

```python
from db.models.conversation import Conversation
from db.models.message import Message
from db.models.memory import Memory
from db.models.task import Task, TaskStep
from db.models.agent import Agent, AgentExecution
from db.models.checkpoint import Checkpoint
from db.base import Base

__all__ = [
    "Conversation", "Message", "Memory",
    "Task", "TaskStep",
    "Agent", "AgentExecution",
    "Checkpoint", "Base",
]
```

**验证:**
```bash
python -c "from db.models import Base, Conversation, Message; print('OK')"
```

---

### Task 1.3: LiteLLM 客户端封装

**文件:** `llm/client.py`

```python
"""LiteLLM 封装 — 统一接口，所有 LLM 调用走这里."""

import litellm
from amor.protocols.llm import LLMProtocol, Message, Thought, ToolCall, TokenUsage
from amor.logging import get_logger

logger = get_logger(__name__)


class LiteLLMClient(LLMProtocol):
    """LiteLLM 适配器，实现 LLMProtocol.

    Usage:
        client = LiteLLMClient(model="gpt-4o", api_key="sk-xxx")
        thought = await client.chat(messages)

    切换模型只需改 model 参数：
        client.model = "gemini/gemini-2.0-flash"
        client.model = "deepseek/deepseek-chat"
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens

    async def chat(self, messages: list[Message]) -> Thought:
        """发送消息，返回完整 Thought."""
        # 转换 Message(TypedDict) → 普通 dict（LiteLLM 兼容）
        formatted = [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in messages
        ]

        logger.info("llm_call", extra={"model": self.model, "msg_count": len(messages)})

        response = await litellm.acompletion(
            model=self.model,
            messages=formatted,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        choice = response.choices[0]
        usage = response.usage

        return Thought(
            content=choice.message.content or "",
            tool_calls=self._parse_tool_calls(choice.message.tool_calls),
            usage=TokenUsage(
                prompt=usage.prompt_tokens if usage else 0,
                completion=usage.completion_tokens if usage else 0,
            ),
        )

    async def stream(self, messages: list[Message]):
        """流式返回 token."""
        formatted = [
            {"role": m.get("role", "user"), "content": m.get("content", "")}
            for m in messages
        ]

        response = await litellm.acompletion(
            model=self.model,
            messages=formatted,
            api_key=self.api_key,
            stream=True,
        )

        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    def _parse_tool_calls(self, raw_tool_calls) -> list[ToolCall] | None:
        """把 LiteLLM 返回的 tool_calls 转成 Amor 的 ToolCall."""
        if not raw_tool_calls:
            return None

        result = []
        for tc in raw_tool_calls:
            import json
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            result.append(ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=args,
            ))
        return result or None
```

**文件:** `tests/test_llm_client.py`（测试用 Mock，不真正调 API）

```python
"""用 Mock 验证 LiteLLMClient 的 tool_calls 解析逻辑."""

import pytest
from llm.client import LiteLLMClient


def test_parse_tool_calls_empty():
    client = LiteLLMClient()
    assert client._parse_tool_calls(None) is None
    assert client._parse_tool_calls([]) is None


def test_lite_llm_client_init():
    client = LiteLLMClient(model="gpt-4o-mini")
    assert client.model == "gpt-4o-mini"
    assert client.temperature == 0.7
```

**验证:** `python -m pytest tests/test_llm_client.py -v`

---

## Phase 2: Prompt 层

### Task 2.1: 系统提示词 + 角色模板

**文件:** `prompt/system.py`

```python
"""Agent 系统提示词."""

SYSTEM_PROMPT = """你是一个通用 AI Agent，能够使用工具完成多种任务。

## 核心准则
1. 逐步思考：每次只做一件事，做完确认后再做下一件
2. 使用工具前说明为什么需要这个工具
3. 不确定或信息不足时主动向用户提问
4. 出错时解释原因并提出替代方案
5. 最终回答用 Markdown 格式，引用来源时注明出处

## 工具使用规范
当你需要调用工具时，输出：
```json
{"tool": "工具名", "arguments": {"参数": "值"}}
```
不要加多余文字。工具执行结果会以 [工具结果] 标签返回给你。
"""
```

**文件:** `prompt/roles.py`

```python
"""Agent 角色模板 — 每种角色有专属的 Prompt."""

ROLE_RESEARCHER = """你是**研究员 Agent**。
职责：搜索信息、收集资料、整理事实。
擅长工具：web_search, rag_query, read_file
输出要求：结构化的信息摘要，每条信息注明来源"""

ROLE_EXECUTOR = """你是**执行者 Agent**。
职责：执行具体操作——写文件、运行命令、调 API。
擅长工具：write_file, run_shell, read_file
输出要求：明确的操作结果和状态"""

ROLE_REVIEWER = """你是**审核员 Agent**。
职责：检查他人输出质量，发现错误和遗漏。
擅长：逻辑验证、事实核对、格式审查
输出要求：审核意见（✅通过 / ⚠️需修改 / ❌驳回）+ 具体理由"""

ROLE_DESIGNER = """你是**设计师 Agent**。
职责：生成图片、设计视觉内容。
擅长工具：generate_image
输出要求：生成的图片或设计说明"""

ROLES = {
    "researcher": ROLE_RESEARCHER,
    "executor": ROLE_EXECUTOR,
    "reviewer": ROLE_REVIEWER,
    "designer": ROLE_DESIGNER,
}
```

**文件:** `prompt/templates.py`

```python
"""Few-shot 示例模板."""

FEW_SHOT_EXAMPLE = """
## 示例 1：简单任务

用户：今天北京天气怎么样？

Agent 思考：这需要实时数据，我应该搜索。
```json
{"tool": "web_search", "arguments": {"query": "北京天气 今天"}}
```

[工具结果]：北京今日晴，10°C ~ 20°C，北风 2 级。

北京今天晴，气温 10°C ~ 20°C，北风 2 级，天气不错。

---

## 示例 2：多步骤任务

用户：帮我写一篇关于 Python 的短文保存到 python_intro.md

Agent 思考：这是两步任务：先搜索资料，再写文件。

```json
{"tool": "web_search", "arguments": {"query": "Python programming language introduction"}}
```

[工具结果]：Python 是...

收到资料，现在写入文件。
```json
{"tool": "write_file", "arguments": {"path": "python_intro.md", "content": "..."}}
```

[工具结果]：文件写入成功。

任务完成。文件已保存到 python_intro.md，内容涵盖 Python 的起源、特点和主要应用领域。
"""
```

**验证:**
```bash
python -c "from prompt.system import SYSTEM_PROMPT; from prompt.roles import ROLES; print('OK')"
```

---

## Phase 3: Context 层

### Task 3.1: 文件读取器

**文件:** `context/reader.py`

```python
"""文件读取 — 按类型路由到最佳解析器.

路由规则:
  .pdf, .docx → LlamaParse Cloud API (云端 LLM 看图理解，不走传统解析)
  .xlsx/.csv   → pandas → HTML 表格 (结构化数据 100% 准确)
  .pptx        → MarkItDown (兜底)
  .html        → MarkItDown
  .png/.jpg    → GPT-4o / Gemini Vision (多模态直接看图描述)
  .md/.txt     → 直接读原文
  其他          → MarkItDown (兜底)

统一后处理: 所有 Markdown 表格 → HTML 表格 (LLM 对 HTML 结构理解力最强)
"""

import base64
from pathlib import Path
from markitdown import MarkItDown
from llama_parse import LlamaParse

_md = MarkItDown()

# LlamaParse 需要 Llamacloud API Key
_llama_parser = LlamaParse(
    api_key=None,  # 从环境变量 LLAMA_CLOUD_API_KEY 读取
    result_type="markdown",
    verbose=False,
)

EXT_PARSER = {
    ".pdf": "llamaparse",
    ".docx": "llamaparse",
    ".xlsx": "pandas",
    ".xls": "pandas",
    ".csv": "pandas",
    ".pptx": "markitdown",
    ".html": "markitdown",
    ".md": "plain",
    ".txt": "plain",
    ".png": "vision",
    ".jpg": "vision",
    ".jpeg": "vision",
    ".webp": "vision",
    ".gif": "vision",
}


async def read_file(path: str | Path) -> str:
    """读任意文件，返回 Markdown 文本（含 HTML 表格）."""
    path = Path(path)
    if not path.exists():
        return f"[错误] 文件不存在: {path}"

    ext = path.suffix.lower()
    parser = EXT_PARSER.get(ext, "markitdown")

    try:
        text = await _dispatch(parser, path)
        # 统一后处理: Markdown 表格 → HTML 表格
        text = _convert_tables_to_html(text)
        return text
    except Exception as e:
        return f"[错误] 文件解析失败 ({parser}): {e}"


async def _dispatch(parser: str, path: Path) -> str:
    """路由到对应解析器."""
    match parser:
        case "llamaparse":
            documents = await _llama_parser.aload_data(str(path))
            return "\n\n".join(d.text for d in documents)
        case "pandas":
            return _parse_pandas(path)
        case "markitdown":
            result = _md.convert(str(path))
            return result.text_content
        case "vision":
            return await _vision_describe(path)
        case "plain":
            return path.read_text(encoding="utf-8", errors="replace")
        case _:
            return _md.convert(str(path)).text_content


# ── 各解析器 ────────────────────────────────────

def _parse_pandas(path: Path) -> str:
    """Excel/CSV → 直接出 HTML 表格，不做中间 Markdown 转换."""
    import pandas as pd

    if path.suffix.lower() == ".csv":
        df = pd.read_csv(str(path))
        return df.to_html(index=False) if not df.empty else "[空文件]"

    sheets = pd.read_excel(str(path), sheet_name=None)
    parts = []
    for sheet_name, df in sheets.items():
        if not df.empty:
            parts.append(f"## Sheet: {sheet_name}\n{df.to_html(index=False)}")
    return "\n\n".join(parts) if parts else "[空文件]"


async def _vision_describe(path: Path) -> str:
    """单独图片 → 多模态 LLM 直接看图描述.

    取到的是原始图片，不经任何压缩中间层。
    """
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    image_b64 = base64.b64encode(path.read_bytes()).decode()

    response = await client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "详细描述这张图片的内容。"
                        "如果是图表，列出所有具体数据。"
                        "如果是架构图/流程图，描述结构和关系。"
                        "如果是普通图片，描述画面内容。"
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/{path.suffix[1:]};base64,{image_b64}"},
                },
            ],
        }],
    )
    return response.choices[0].message.content or "[图片描述生成失败]"


# ── 表格后处理 ──────────────────────────────────

def _convert_tables_to_html(text: str) -> str:
    """Markdown 表格 → HTML 表格.

    LLM 对 HTML <table> 的结构推理能力
    远强于 Markdown |...| 表格语法。
    """
    import re

    def _md_to_html(md_table: str) -> str:
        lines = md_table.strip().split("\n")
        if len(lines) < 2:
            return md_table

        header = lines[0]
        data_lines = [l for l in lines[1:] if not re.match(r"^\|[\s\-:|]+\|$", l)]

        html = "<table>\n<thead>\n<tr>\n"
        for cell in header.split("|")[1:-1]:
            html += f"<th>{cell.strip()}</th>\n"
        html += "</tr>\n</thead>\n<tbody>\n"

        for line in data_lines:
            html += "<tr>\n"
            for cell in line.split("|")[1:-1]:
                html += f"<td>{cell.strip()}</td>\n"
            html += "</tr>\n"
        html += "</tbody>\n</table>"
        return html

    pattern = re.compile(
        r"(^\|.+\|$\n)+(^\|[\-\s:|]+\|$\n)?(^\|.+\|$\n)*", re.MULTILINE
    )
    return pattern.sub(lambda m: _md_to_html(m.group()), text)
```

**依赖安装:**
```bash
python -m pip install markitdown llama-parse pandas openpyxl openai
```

**环境变量:**
```bash
export LLAMA_CLOUD_API_KEY="llx-..."   # LlamaParse
export OPENAI_API_KEY="sk-..."         # GPT-4o Vision
```

---

### Task 3.2: 记忆存储

**文件:** `context/memory_store.py`

```python
"""记忆存储 — 实现 MemoryProtocol，存 PostgreSQL."""

from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from amor.protocols.memory import MemoryProtocol
from amor.logging import get_logger
from db.models.memory import Memory

logger = get_logger(__name__)


class PostgresMemory(MemoryProtocol):
    """基于 PostgreSQL 的持久记忆存储."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, key: str, value: Any) -> None:
        """保存或更新一条记忆."""
        stmt = select(Memory).where(Memory.key == key)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            existing.value = value
        else:
            memory = Memory(key=key, value=value)
            self.session.add(memory)

        await self.session.commit()
        logger.debug("memory_saved", extra={"key": key})

    async def query(self, key: str) -> Any | None:
        """查询记忆."""
        stmt = select(Memory).where(Memory.key == key)
        result = await self.session.execute(stmt)
        memory = result.scalar_one_or_none()
        return memory.value if memory else None

    async def delete(self, key: str) -> None:
        """删除一条记忆."""
        stmt = select(Memory).where(Memory.key == key)
        result = await self.session.execute(stmt)
        memory = result.scalar_one_or_none()
        if memory:
            await self.session.delete(memory)
            await self.session.commit()

    async def clear(self) -> None:
        """清空所有记忆."""
        from sqlalchemy import delete as sql_delete
        await self.session.execute(sql_delete(Memory))
        await self.session.commit()
```

---

### Task 3.3: RAG 检索器

**文件:** `context/rag.py`

```python
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
```

**依赖:** `python -m pip install langchain-text-splitters chromadb`

---

### Task 3.4: 网页搜索

**文件:** `context/web_search.py`

```python
"""网页搜索 — Tavily Search API."""

import os
from tavily import TavilyClient

_client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY", ""))


async def search_web(query: str, max_results: int = 5) -> list[dict]:
    """搜索网页，返回结果列表."""
    try:
        response = _client.search(query, max_results=max_results)
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""), "content": r.get("content", "")}
            for r in response.get("results", [])
        ]
    except Exception as e:
        return [{"title": "搜索失败", "url": "", "content": str(e)}]
```

---

### Task 3.5: 上下文组装器

**文件:** `context/assembler.py`

```python
"""上下文组装器 — 把零散信息拼成发给 LLM 的完整 messages."""

from amor.protocols.llm import Message
from amor.protocols.tool import ToolSchema


async def assemble_messages(
    task: str,
    system_prompt: str,
    role_prompt: str = "",
    file_paths: list[str] | None = None,
    rag_query_text: str | None = None,
    search_query: str | None = None,
    memory: "PostgresMemory | None" = None,
    history: list[Message] | None = None,
    tool_schemas: list[ToolSchema] | None = None,
) -> list[Message]:
    """拼装最终的 messages 列表.

    顺序：
    1. 系统提示词（角色 + 行为准则）
    2. 角色提示词
    3. 工具列表
    4. 文件内容
    5. RAG 结果
    6. 网页搜索结果
    7. 记忆
    8. 对话历史
    9. 用户任务
    """
    from context.reader import read_file
    from context.rag import query as rag_query
    from context.web_search import search_web

    # 构建系统消息
    system_content = system_prompt
    if role_prompt:
        system_content += f"\n\n## 本次角色\n{role_prompt}"

    # Skill Prompt 注入（Claude Code 风格 — 从 .md 文件加载）
    from harness.skills.loader import get_system_prompt_extensions
    skill_extensions = get_system_prompt_extensions()
    if skill_extensions:
        system_content += f"\n\n## 行为规则\n{skill_extensions}"

    # 工具列表
    if tool_schemas:
        tools_text = "\n".join(
            f"- {t.name}: {t.description}" for t in tool_schemas
        )
        system_content += f"\n\n## 可用工具\n{tools_text}"

    messages: list[Message] = [
        Message(role="system", content=system_content),
    ]

    # 文件内容
    if file_paths:
        files_text = "\n\n".join(
            f"### {p}\n{await read_file(p)}" for p in file_paths
        )
        messages.append(Message(role="system", content=f"## 相关文件\n{files_text}"))

    # RAG
    if rag_query_text:
        results = await rag_query(rag_query_text)
        rag_text = "\n".join(
            f"- [{r['source']}] {r['text'][:500]}" for r in results
        )
        messages.append(Message(role="system", content=f"## 知识库检索\n{rag_text}"))

    # 网页搜索
    if search_query:
        results = await search_web(search_query)
        search_text = "\n".join(
            f"- [{r['title']}]({r['url']}): {r['content'][:300]}" for r in results
        )
        messages.append(Message(role="system", content=f"## 网页搜索\n{search_text}"))

    # 记忆
    if memory:
        mem = await memory.query("user_preferences")
        if mem:
            messages.append(Message(role="system", content=f"## 用户偏好\n{mem}"))

    # 对话历史（裁剪后）
    if history:
        messages.extend(history[-20:])  # 只保留最近 20 条

    # 用户任务
    messages.append(Message(role="user", content=task))

    return messages
```

---

### Task 3.6: 窗口管理器

**文件:** `context/window.py`

```python
"""上下文窗口管理 — 对话过长时自动裁剪.

策略:
1. System Prompt 完整保留
2. 最近 keep_last_n 条消息强制保护（Agent 的 think-act 决策链不能断）
3. 只裁中间的老消息
"""

from amor.protocols.llm import Message


def estimate_tokens(messages: list[Message]) -> int:
    """粗略估算 token 数（4 字符 ≈ 1 token）."""
    total = 0
    for m in messages:
        total += len(m.get("content", "")) // 4
    return total


def trim_messages(
    messages: list[Message],
    max_tokens: int = 8000,
    keep_system: bool = True,
    keep_last_n: int = 4,
) -> list[Message]:
    """裁剪消息到 token 上限."""
    system_msgs = [m for m in messages if m.get("role") == "system"] if keep_system else []
    other_msgs = [m for m in messages if m.get("role") != "system"]

    if len(other_msgs) <= keep_last_n:
        return system_msgs + other_msgs

    protected = other_msgs[-keep_last_n:]
    trimmable = other_msgs[:-keep_last_n]

    while estimate_tokens(system_msgs + trimmable + protected) > max_tokens and trimmable:
        trimmable.pop(0)

    return system_msgs + trimmable + protected
```

**验证:**
```bash
python -c "from context.assembler import assemble_messages; from context.window import trim_messages; print('OK')"
```

---

## Phase 4: Harness 层

### Task 4.1: 工具注册表

**文件:** `harness/tool_registry.py`

```python
"""工具注册表 — 统一管理所有 Tool."""

from amor.protocols.tool import ToolProtocol, ToolSchema


class ToolRegistry:
    """工具注册中心.

    所有 Tool（内置 Skill / 用户 Skill / MCP Tool）统一注册到这里。
    Agent 通过它获取可用工具列表、调用工具。
    """

    def __init__(self):
        self._tools: dict[str, ToolProtocol] = {}

    def register(self, tool: ToolProtocol) -> None:
        """注册一个工具."""
        name = tool.schema.name
        self._tools[name] = name
        self._tools[name] = tool

    def get(self, name: str) -> ToolProtocol | None:
        """按名获取工具."""
        return self._tools.get(name)

    def get_all_schemas(self) -> list[ToolSchema]:
        """获取所有工具的 Schema，用于告诉 LLM 有哪些工具可用."""
        return [t.schema for t in self._tools.values()]

    def list_names(self) -> list[str]:
        """列出所有工具名."""
        return list(self._tools.keys())

    async def execute(self, name: str, arguments: dict) -> str:
        """执行工具并返回结果字符串."""
        tool = self._tools.get(name)
        if not tool:
            return f"[错误] 工具 '{name}' 未注册。可用工具: {self.list_names()}"
        try:
            result = await tool.execute(arguments)
            return str(result)
        except Exception as e:
            return f"[错误] 工具 '{name}' 执行失败: {e}"
```

**测试:** `tests/test_tool_registry.py`

```python
import pytest
from amor.protocols.tool import ToolProtocol, ToolSchema
from harness.tool_registry import ToolRegistry


class FakeEchoTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(name="echo", description="echo back", parameters={})

    async def execute(self, arguments):
        return arguments.get("text", "")


@pytest.mark.asyncio
async def test_register_and_execute():
    registry = ToolRegistry()
    registry.register(FakeEchoTool())
    assert "echo" in registry.list_names()
    result = await registry.execute("echo", {"text": "hello"})
    assert result == "hello"


@pytest.mark.asyncio
async def test_execute_unknown_tool():
    registry = ToolRegistry()
    result = await registry.execute("nonexistent", {})
    assert "未注册" in result
```

---

### Task 4.2: Built-in Skills

**文件:** `harness/skills/builtin/file_ops.py`

实现 `read_file`, `write_file`, `list_files` 三个 ToolProtocol:

```python
"""文件操作技能."""

from typing import Any
from pathlib import Path
from amor.protocols.tool import ToolProtocol, ToolSchema


class ReadFileTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="read_file",
            description="读取文件内容",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "文件路径"}},
                "required": ["path"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        path = Path(arguments["path"])
        if not path.exists():
            return f"文件不存在: {path}"
        return path.read_text(encoding="utf-8", errors="replace")


class WriteFileTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="write_file",
            description="写入内容到文件（覆盖写入）",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "文件路径"},
                    "content": {"type": "string", "description": "要写入的内容"},
                },
                "required": ["path", "content"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        path = Path(arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments["content"], encoding="utf-8")
        return f"文件已写入: {path} ({len(arguments['content'])} 字符)"


class ListFilesTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="list_files",
            description="列出目录内容",
            parameters={
                "type": "object",
                "properties": {"path": {"type": "string", "description": "目录路径，默认当前目录"}},
                "required": [],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        path = Path(arguments.get("path", "."))
        if not path.exists():
            return f"目录不存在: {path}"
        items = list(path.iterdir())
        return "\n".join(
            f"{'[DIR]' if i.is_dir() else '[FILE]'} {i.name}" for i in items
        )
```

**文件:** `harness/skills/builtin/shell.py`

```python
"""Shell 命令技能."""

import subprocess
from typing import Any
from amor.protocols.tool import ToolProtocol, ToolSchema


class RunShellTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="run_shell",
            description="执行 Shell 命令并返回输出",
            parameters={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "要执行的命令"},
                    "timeout": {"type": "integer", "description": "超时秒数，默认 60"},
                },
                "required": ["command"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        command = arguments["command"]
        timeout = arguments.get("timeout", 60)

        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=timeout
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}"
            return output or f"[命令执行完毕，返回码: {result.returncode}]"
        except subprocess.TimeoutExpired:
            return f"[错误] 命令超时（{timeout}秒）: {command}"
        except Exception as e:
            return f"[错误] 命令执行失败: {e}"
```

**文件:** `harness/skills/builtin/search.py`

```python
"""搜索技能 — 网页搜索 + RAG 查询."""

from typing import Any
from amor.protocols.tool import ToolProtocol, ToolSchema


class WebSearchTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="web_search",
            description="搜索互联网获取最新信息",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "搜索关键词"},
                    "max_results": {"type": "integer", "description": "最多返回几条"},
                },
                "required": ["query"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        from context.web_search import search_web
        results = await search_web(
            arguments["query"], arguments.get("max_results", 5)
        )
        return "\n\n".join(
            f"### {r['title']}\n{r['content']}\n{r['url']}" for r in results
        )


class RAGQueryTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="rag_query",
            description="从知识库中检索相关文档",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "查询内容"},
                    "top_k": {"type": "integer", "description": "返回几条"},
                },
                "required": ["query"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        from context.rag import query as rag_query
        results = await rag_query(arguments["query"], arguments.get("top_k", 5))
        return "\n\n".join(
            f"### [{r['source']}]\n{r['text']}" for r in results
        )
```

**文件:** `harness/skills/builtin/image_gen.py`

```python
"""图片生成技能."""

import os
from typing import Any
from amor.protocols.tool import ToolProtocol, ToolSchema


class GenerateImageTool(ToolProtocol):
    @property
    def schema(self):
        return ToolSchema(
            name="generate_image",
            description="用 AI 生成图片",
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string", "description": "图片描述"},
                    "size": {"type": "string", "description": "尺寸，如 1024x1024"},
                },
                "required": ["prompt"],
            },
        )

    async def execute(self, arguments: dict[str, Any]) -> str:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        response = await client.images.generate(
            model="dall-e-3",
            prompt=arguments["prompt"],
            size=arguments.get("size", "1024x1024"),
            n=1,
        )
        url = response.data[0].url
        return f"图片已生成: {url}"
```

---

### Task 4.3: Skill 基类 + Loader

**设计原则: 仿 Claude Code Superpowers — Skill 只管 Prompt 注入。**

```
Skill = 一段 Prompt 模板

工具 → 全局 ToolRegistry（不归 Skill 管）
权限 → Tool 自身的 risk_level + requires_approval（不归 Skill 管）
```

**文件:** `harness/skills/base.py`

```python
"""Skill 数据类 — 从 .md 文件解析出来的内部表示."""

from dataclasses import dataclass


@dataclass
class Skill:
    """一条 Skill = frontmatter 元数据 + Prompt 正文."""

    name: str = ""
    description: str = ""
    source_file: str = ""       # 来自哪个 .md 文件
    prompt: str = ""            # frontmatter 下面那段 Prompt 正文
```

**文件:** `harness/skills/loader.py`

```python
"""Skill 自动发现与加载 — 扫描 .md 文件，解析 frontmatter.

格式（兼容 Claude Code / Codex）:
    ---
    name: safe_shell
    description: 让 Agent 谨慎使用 Shell
    ---
    Prompt 正文（注入到 System Prompt 末尾）
"""

from pathlib import Path
from harness.skills.base import Skill

_registered_skills: list[Skill] = []


def discover_and_register() -> list[Skill]:
    """扫描 skills/builtin/ 和 skills/user/ 中的 .md 文件."""
    _registered_skills.clear()

    _scan_dir(Path("harness/skills/builtin"))
    _scan_dir(Path("harness/skills/user"))

    return _registered_skills


def get_system_prompt_extensions() -> str:
    """所有 Skill Prompt 拼接为一个字符串."""
    parts: list[str] = []
    for skill in _registered_skills:
        if skill.prompt.strip():
            parts.append(f"## {skill.name}\n{skill.prompt}")
    return "\n\n".join(parts)


def _scan_dir(directory: Path) -> None:
    """扫描目录下所有 .md 文件."""
    if not directory.exists():
        return
    for md_file in sorted(directory.glob("*.md")):
        try:
            skill = _parse_skill_file(md_file)
            if skill:
                _registered_skills.append(skill)
        except Exception as e:
            import logging
            logging.getLogger("amor").warning(
                f"Failed to parse skill file {md_file}: {e}"
            )


def _parse_skill_file(filepath: Path) -> Skill | None:
    """解析 .md 文件，分离 frontmatter 和 Prompt 正文."""
    import yaml

    content = filepath.read_text(encoding="utf-8")
    if not content.startswith("---"):
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    frontmatter_text = parts[1].strip()
    prompt = parts[2].strip()

    try:
        meta: dict = yaml.safe_load(frontmatter_text) or {}
    except yaml.YAMLError:
        meta = {}

    return Skill(
        name=meta.get("name", filepath.stem),
        description=meta.get("description", ""),
        source_file=str(filepath),
        prompt=prompt,
    )
```

**使用示例 — 用户新增 Skill:**

```bash
# 从 GitHub 扒一个 .md 文件 → 丢进 skills/user/ → 重启 → 自动生效
cp ~/Downloads/superpowers.md har ness/skills/user/
```

Skill 文件格式:
```markdown
---
name: my_skill
description: 自定义规则
---

执行任何操作前请先确认:
1. 是否需要用户审批
2. 是否有更简单的替代方案
```

`get_system_prompt_extensions()` 在 context/assembler.py 拼 messages 时调用，自动注入 System Prompt。
```

---

### Task 4.4: MCP Client

**文件:** `harness/mcp/client.py`

```python
"""MCP 客户端 — 连接外部 MCP Server，自动映射为本地 Tool.

连接生命周期:
  startup:  conn = await connect_mcp_server(...)
  runtime:  Agent 通过 ToolRegistry 调 MCP Tool
  shutdown: await conn.close()
"""

import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from amor.protocols.tool import ToolProtocol, ToolSchema
from harness.tool_registry import ToolRegistry


class MCPConnection:
    """一个长期存活的 MCP Server 连接."""

    def __init__(self, server_command: list[str]):
        self._command = server_command
        self._session: ClientSession | None = None
        self._read = None
        self._write = None

    async def connect(self) -> None:
        params = StdioServerParameters(
            command=self._command[0], args=self._command[1:],
        )
        self._read, self._write = await stdio_client(params).__aenter__()
        self._session = await ClientSession(self._read, self._write).__aenter__()
        await self._session.initialize()

    async def list_tools(self) -> list:
        return (await self._session.list_tools()).tools

    async def call_tool(self, name: str, arguments: dict) -> str:
        result = await self._session.call_tool(name, arguments)
        return json.dumps(result.content, ensure_ascii=False)

    async def close(self) -> None:
        if self._session:
            await self._session.__aexit__(None, None, None)
        if self._read:
            await self._read.__aexit__(None, None, None)


class _MCPToolWrapper(ToolProtocol):
    """把 MCP 远程 Tool 包装成 ToolProtocol."""

    def __init__(self, name: str, description: str, input_schema: dict, conn: MCPConnection):
        self._name = name
        self._description = description
        self._input_schema = input_schema
        self._conn = conn

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name=self._name, description=self._description,
            parameters=self._input_schema,
        )

    async def execute(self, arguments: dict) -> str:
        return await self._conn.call_tool(self._name, arguments)


async def connect_mcp_server(
    server_command: list[str],
    registry: ToolRegistry,
) -> MCPConnection:
    """连接 MCP Server，注册其所有 Tool.

    Returns MCPConnection，调用方在 shutdown 时 close()。
    """
    conn = MCPConnection(server_command)
    await conn.connect()

    for tool in await conn.list_tools():
        wrapper = _MCPToolWrapper(
            name=tool.name,
            description=tool.description or "",
            input_schema=tool.inputSchema or {},
            conn=conn,
        )
        registry.register(wrapper)

    return conn
```

**依赖:** `python -m pip install mcp`

---

### Task 4.5: Planner

**文件:** `harness/planner.py`

```python
"""任务规划器 — 实现 PlannerProtocol，用 LLM 拆任务."""

from typing import Any
from amor.protocols.planner import PlannerProtocol, Plan, PlanStep
from amor.protocols.llm import LLMProtocol, Message
from amor.logging import get_logger

logger = get_logger(__name__)

PLANNING_PROMPT = """你是一个任务规划专家。给定一个任务，将它拆解为 3-7 个可执行步骤。

输出格式（JSON）：
```json
{
    "steps": [
        {"id": "1", "description": "步骤描述", "tool": "可能需要用到的工具名或null", "depends_on": []},
        ...
    ]
}
```

规则：
- 步骤之间不要重复
- 每个步骤专注做一件事
- 需要用到工具时指明工具名
- depends_on 列出依赖的前置步骤 id
"""


class LLMPlanner(PlannerProtocol):
    """用 LLM 做任务规划."""

    def __init__(self, llm: LLMProtocol):
        self.llm = llm

    async def plan(self, task: str, context: dict[str, Any]) -> Plan:
        """生成执行计划."""
        messages: list[Message] = [
            Message(role="system", content=PLANNING_PROMPT),
            Message(
                role="user",
                content=f"任务: {task}\n可用工具: {context.get('tools', [])}",
            ),
        ]

        thought = await self.llm.chat(messages)

        # 解析 LLM 返回的 JSON
        import json
        try:
            # 提取 JSON 块
            content = thought.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            data = json.loads(content.strip())
            steps = [
                PlanStep(
                    id=s["id"],
                    description=s.get("description", ""),
                    tool=s.get("tool"),
                    depends_on=s.get("depends_on", []),
                )
                for s in data.get("steps", [])
            ]
        except (json.JSONDecodeError, KeyError, IndexError):
            # 解析失败 → 单步计划
            logger.warning("plan_parse_failed", extra={"content": thought.content[:200]})
            steps = [PlanStep(id="1", description=task)]

        return Plan(task=task, steps=steps)

    async def replan(
        self, original: Plan, feedback: str, progress: dict[str, Any]
    ) -> Plan:
        """根据反馈调整计划."""
        completed = progress.get("completed", [])
        remaining = [s for s in original.steps if s.id not in completed]

        # 简版：保留未完成的步骤，加一个修正步骤
        new_steps = remaining + [
            PlanStep(
                id="correction",
                description=f"根据反馈修正: {feedback}",
            )
        ]
        return Plan(task=original.task, steps=new_steps)
```

---

### Task 4.6: Agent Runner（核心 — 含中断机制）

**文件:** `harness/runner.py`

这是单 Agent 的执行循环——框架的心脏。遵循 Anthropic 的简洁哲学：不硬编码策略，模型自己决定怎么思考。

```python
"""Agent Runner — 单 Agent 的 Think → Act → Observe → Judge 循环.

设计原则 (仿 Anthropic):
- 不写死 ReAct/PlanExecute 等策略，模型自己判断怎么做
- 工具标注风险等级，高危险操作 emit INTERRUPT 等人审批
- 简单任务直接回答，复杂任务模型自然产生多轮 think-act
"""

import asyncio
from amor.protocols.llm import LLMProtocol, Message
from amor.events.bus import EventBus
from amor.events.types import Event, EventType
from amor.logging import get_logger
from harness.tool_registry import ToolRegistry
from context.assembler import assemble_messages

logger = get_logger(__name__)


class AgentConfig:
    """单个 Agent 的配置."""

    def __init__(
        self,
        name: str = "agent",
        role: str = "",
        system_prompt: str = "",
        tools: list[str] | None = None,
        model: str = "gpt-4o",
        max_steps: int = 30,
    ):
        self.name = name
        self.role = role
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model = model
        self.max_steps = max_steps


class AgentResult:
    """Agent 执行结果."""

    def __init__(self):
        self.status: str = "running"  # running / success / failed / interrupted
        self.output: str = ""
        self.steps: list[dict] = []
        self.total_tokens: int = 0
        self.total_cost: float = 0.0


async def run_agent(
    config: AgentConfig,
    task: str,
    llm: LLMProtocol,
    registry: ToolRegistry,
    event_bus: EventBus | None = None,
    interrupt_handler: "InterruptHandler | None" = None,
) -> AgentResult:
    """执行单个 Agent 的 Think-Act-Observe 循环.

    Args:
        interrupt_handler: 处理用户审批。为 None 时高危操作自动拒绝。
    """
    result = AgentResult()
    messages = await assemble_messages(
        task=task,
        system_prompt=config.system_prompt,
        role_prompt=config.role,
        tool_schemas=[
            s for s in registry.get_all_schemas()
            if s.name in config.tools
        ] if config.tools else registry.get_all_schemas(),
    )

    for step in range(config.max_steps):
        await _emit(event_bus, Event(type=EventType.NODE_START, node_id=f"{config.name}_think_{step}"))

        # 1. Think
        thought = await llm.chat(messages)
        result.total_tokens += thought.usage.total if thought.usage else 0
        messages.append(Message(role="assistant", content=thought.content))

        # 2. Judge: 没有 tool_call → 模型认为完成了
        if not thought.tool_calls:
            result.status = "success"
            result.output = thought.content
            await _emit(event_bus, Event(type=EventType.NODE_END, node_id=f"{config.name}_done"))
            break

        # 3. Act: 执行工具（先检查风险等级）
        for tc in thought.tool_calls:
            tool = registry.get(tc.name)
            tool_schema = tool.schema if tool else None

            # ═══════════════════════════════════════
            # 中断机制: 高危操作必须等人审批
            # ═══════════════════════════════════════
            if tool_schema and tool_schema.requires_approval:
                approved = await _interrupt(
                    event_bus, interrupt_handler,
                    tool_name=tc.name,
                    tool_args=tc.arguments,
                    risk_level=tool_schema.risk_level,
                    agent_name=config.name,
                )
                if not approved:
                    tool_result = (
                        f"[审批拒绝] 工具 '{tc.name}' 需要用户审批，"
                        f"但用户拒绝了该操作。请尝试其他方案。"
                    )
                    messages.append(Message(role="tool", content=tool_result, tool_call_id=tc.id))
                    result.steps.append({
                        "step": step, "thought": thought.content[:200],
                        "tool": tc.name, "result": tool_result,
                    })
                    continue  # 跳过这个 tool，继续下一个

            # 正常执行
            logger.info("tool_call", extra={"agent": config.name, "tool": tc.name})
            tool_result = await registry.execute(tc.name, tc.arguments)
            messages.append(Message(role="tool", content=str(tool_result), tool_call_id=tc.id))
            result.steps.append({
                "step": step,
                "thought": thought.content[:200],
                "tool": tc.name,
                "result": str(tool_result)[:500],
            })

        await _emit(event_bus, Event(type=EventType.NODE_END, node_id=f"{config.name}_step_{step}"))

        if step >= config.max_steps - 1:
            result.status = "failed"
            result.output = f"超过最大步数限制 ({config.max_steps})"

    return result


# ── 中断机制 ────────────────────────────────────

class InterruptEvent:
    """中断事件 — 高危操作等待用户决策."""
    def __init__(self):
        self.tool_name: str = ""
        self.tool_args: dict = {}
        self.risk_level: str = ""
        self.event = asyncio.Event()  # 用于等待用户响应
        self.approved: bool = False


class InterruptHandler:
    """管理所有待审批的中断."""
    def __init__(self):
        self._pending: dict[str, InterruptEvent] = {}

    def create(self, request_id: str, tool_name: str, tool_args: dict, risk_level: str) -> InterruptEvent:
        ie = InterruptEvent()
        ie.tool_name = tool_name
        ie.tool_args = tool_args
        ie.risk_level = risk_level
        self._pending[request_id] = ie
        return ie

    def approve(self, request_id: str):
        if request_id in self._pending:
            self._pending[request_id].approved = True
            self._pending[request_id].event.set()

    def reject(self, request_id: str):
        if request_id in self._pending:
            self._pending[request_id].approved = False
            self._pending[request_id].event.set()


async def _interrupt(
    event_bus: EventBus | None,
    handler: InterruptHandler | None,
    tool_name: str,
    tool_args: dict,
    risk_level: str,
    agent_name: str,
) -> bool:
    """中断执行，等人审批。返回 True=允许, False=拒绝."""
    import uuid
    request_id = str(uuid.uuid4())[:8]

    # 发射事件给前端
    if event_bus:
        await event_bus.emit(Event(
            type=EventType.INTERRUPT,
            node_id=agent_name,
            tool_name=tool_name,
            tool_arguments=tool_args,
            risk_level=risk_level,
        ))

    # 没有 handler → 自动拒绝
    if handler is None:
        logger.warning("no_interrupt_handler", extra={"tool": tool_name})
        return False

    # 等待用户决策（最多 5 分钟超时）
    ie = handler.create(request_id, tool_name, tool_args, risk_level)
    try:
        await asyncio.wait_for(ie.event.wait(), timeout=300.0)
    except asyncio.TimeoutError:
        logger.warning("interrupt_timeout", extra={"tool": tool_name})
        return False

    return ie.approved


async def _emit(bus: EventBus | None, event: Event) -> None:
    if bus:
        await bus.emit(event)
```

**关键变化:**
1. `run_agent()` 新增 `interrupt_handler` 参数
2. 执行工具前检查 `schema.requires_approval`
3. 需要审批 → emit INTERRUPT → 等待用户决策 → 允许/拒绝
4. 无 handler 时高危操作自动拒绝（安全优先）
```

---

### Task 4.7: Orchestrator（增强版 — 并行 + 通信 + 审核循环）

**文件:** `harness/orchestrator.py`

```python
"""Orchestrator — 多 Agent 调度中心.

三个核心能力:
1. 并行: 互不依赖的步骤同时执行 (asyncio.gather)
2. 通信: 前置步骤的输出自动注入给后续 Agent
3. 审核循环: 执行者产出 → 审核员检查 → 不通过就退回重做 (最多 3 次)
"""

import asyncio
from amor.protocols.llm import LLMProtocol, Message
from harness.runner import run_agent, AgentConfig, AgentResult
from harness.tool_registry import ToolRegistry
from harness.planner import LLMPlanner
from amor.events.bus import EventBus
from amor.logging import get_logger
from prompt.roles import ROLES

logger = get_logger(__name__)

MAX_REVIEW_RETRIES = 3  # 审核驳回最多重做次数


class StepResult:
    """单步执行结果 — 供 Agent 间通信."""

    def __init__(self):
        self.step_id: str = ""
        self.role: str = ""
        self.output: str = ""
        self.status: str = "pending"  # pending / running / success / failed
        self.tokens: int = 0
        self.retries: int = 0


class Orchestrator:
    """多 Agent 编排器.

    执行流程:
    1. 分析任务类型 → 确定需要的角色
    2. Planner 生成步骤列表（含依赖关系）
    3. 按依赖分组，组内并行，组间顺序
    4. 执行者 → 审核员 → 通过/驳回重做
    5. 汇总所有结果
    """

    def __init__(
        self,
        llm: LLMProtocol,
        registry: ToolRegistry,
        event_bus: EventBus | None = None,
    ):
        self.llm = llm
        self.registry = registry
        self.event_bus = event_bus
        self.planner = LLMPlanner(llm)
        self.results: dict[str, StepResult] = {}  # step_id → result

    # ── 主入口 ──────────────────────────────────

    async def execute(self, task: str) -> dict:
        """执行任务: 规划 → 并行分派 → 审核 → 汇总."""
        logger.info("orchestrator_start", extra={"task": task})

        # 1. LLM 分析任务，决定需要哪些 Agent 角色
        roles_needed = await self._decide_roles(task)
        logger.info("roles_decided", extra={"roles": roles_needed})

        # 2. 规划
        plan = await self.planner.plan(
            task, context={"tools": self.registry.list_names()},
        )

        # 3. 按依赖拓扑顺序执行
        remaining = list(plan.steps)
        completed_ids: set[str] = set()

        while remaining:
            # 找出所有依赖已满足的步骤（可以并行）
            ready = [
                s for s in remaining
                if all(dep in completed_ids for dep in s.depends_on)
            ]

            if not ready:
                # 死锁——有步骤的依赖永远无法满足
                stuck = [s.id for s in remaining]
                logger.error("deadlock", extra={"stuck_steps": stuck})
                break

            # 并行执行这一批
            tasks = [
                self._execute_step(s, roles_needed)
                for s in ready
            ]
            await asyncio.gather(*tasks)

            # 标记完成，移出待处理列表
            for s in ready:
                completed_ids.add(s.id)
            remaining = [s for s in remaining if s.id not in completed_ids]

        # 4. 汇总
        return self._summarize(task, roles_needed, plan)

    # ── 单步执行 ────────────────────────────────

    async def _execute_step(self, step, roles_needed: list[str]) -> StepResult:
        """执行一个步骤: 分配角色 → 注入前置结果 → 执行 → 审核."""
        role = await self._pick_role(step.description, roles_needed)

        # 收集依赖步骤的输出（Agent 间通信）
        upstream_context = self._collect_upstream_results(step.depends_on)

        # 构建任务描述（注入前置结果）
        task_with_context = step.description
        if upstream_context:
            task_with_context += "\n\n## 前置步骤的输出（供参考）\n" + upstream_context

        # Agent 配置
        agent_config = AgentConfig(
            name=f"{role}_{step.id}",
            role=ROLES.get(role, ""),
            system_prompt="You are a helpful AI agent.",
            model=self.llm.model if hasattr(self.llm, "model") else "gpt-4o",
        )

        # 执行
        result = await run_agent(
            config=agent_config,
            task=task_with_context,
            llm=self.llm,
            registry=self.registry,
            event_bus=self.event_bus,
        )

        sr = StepResult()
        sr.step_id = step.id
        sr.role = role
        sr.output = result.output
        sr.status = result.status
        sr.tokens = result.total_tokens

        # 审核循环（如果有审核员角色可用）
        if "reviewer" in roles_needed and role != "reviewer":
            sr = await self._review_loop(sr, step, roles_needed)

        self.results[step.id] = sr
        logger.info("step_done", extra={"step_id": step.id, "role": role, "status": sr.status})
        return sr

    # ── 审核循环 ────────────────────────────────

    async def _review_loop(
        self,
        sr: StepResult,
        step,
        roles_needed: list[str],
    ) -> StepResult:
        """审核员检查执行者输出，不通过就退回重做."""
        for attempt in range(MAX_REVIEW_RETRIES):
            review_result = await self._run_reviewer(sr.output, step.description)

            if review_result["verdict"] == "pass":
                sr.output = review_result.get("final_output", sr.output)
                sr.status = "success"
                break
            else:
                # 驳回 → 把审核意见注入，重新执行
                logger.warning(
                    "review_rejected",
                    extra={"step_id": step.id, "attempt": attempt + 1, "reason": review_result["reason"]},
                )
                feedback = f"审核不通过: {review_result['reason']}\n请修正后重新输出。"

                redo_config = AgentConfig(
                    name=f"executor_{step.id}_retry{attempt + 1}",
                    role=ROLES.get("executor", ""),
                    system_prompt="You are a helpful AI agent.",
                    model=self.llm.model if hasattr(self.llm, "model") else "gpt-4o",
                )
                redo_result = await run_agent(
                    config=redo_config,
                    task=f"修正以下输出:\n\n原始输出:\n{sr.output}\n\n{feedback}",
                    llm=self.llm,
                    registry=self.registry,
                    event_bus=self.event_bus,
                )
                sr.output = redo_result.output
                sr.tokens += redo_result.total_tokens
                sr.retries = attempt + 1

        else:
            # 达到最大重试次数
            sr.status = "failed_with_review"
            sr.output += f"\n\n[审核驳回 {MAX_REVIEW_RETRIES} 次，放弃]"

        return sr

    async def _run_reviewer(self, output: str, step_description: str) -> dict:
        """调审核员 Agent 检查输出质量."""
        import json

        reviewer_config = AgentConfig(
            name="reviewer",
            role=ROLES.get("reviewer", ""),
            system_prompt="You are a helpful AI agent.",
            tools=["read_file"],
            model=self.llm.model if hasattr(self.llm, "model") else "gpt-4o",
        )
        review_result = await run_agent(
            config=reviewer_config,
            task=f"审核以下步骤的输出:\n\n步骤: {step_description}\n输出:\n{output}\n\n请回复 JSON: {{\"verdict\": \"pass\"|\"reject\", \"reason\": \"...\", \"final_output\": \"...\"}} 如果通过，final_output 可以是润色后的版本。",
            llm=self.llm,
            registry=self.registry,
            event_bus=self.event_bus,
        )

        # 解析审核结果
        try:
            content = review_result.output
            if "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except (json.JSONDecodeError, KeyError):
            return {"verdict": "pass", "reason": "审核解析失败，默认通过", "final_output": output}

    # ── Agent 间通信 ────────────────────────────

    def _collect_upstream_results(self, depends_on: list[str]) -> str:
        """收集前置步骤的输出，作为当前 Agent 的上下文."""
        if not depends_on:
            return ""

        parts = []
        for dep_id in depends_on:
            if dep_id in self.results:
                r = self.results[dep_id]
                parts.append(f"### [{dep_id}] {r.role} 的输出\n{r.output[:2000]}")
        return "\n\n".join(parts)

    # ── 汇总 ────────────────────────────────────

    def _summarize(self, task: str, roles_needed: list[str], plan) -> dict:
        """汇总所有步骤结果."""
        results_list = []
        for step in plan.steps:
            r = self.results.get(step.id)
            if r:
                results_list.append({
                    "step_id": r.step_id,
                    "role": r.role,
                    "result": r.output,
                    "status": r.status,
                    "tokens": r.tokens,
                    "retries": r.retries,
                })

        summary = "\n\n".join(
            f"## 步骤 {r['step_id']} ({r['role']})\n{r['result'][:1000]}"
            for r in results_list
        )

        return {
            "task": task,
            "roles": roles_needed,
            "plan": [s.model_dump() for s in plan.steps],
            "results": results_list,
            "summary": summary,
            "total_tokens": sum(r["tokens"] for r in results_list),
        }

    # ── Agent 角色选择（LLM 判断，不靠关键词）────

    async def _decide_roles(self, task: str) -> list[str]:
        """让 LLM 判断这个任务需要哪些 Agent 角色."""
        messages = [
            Message(role="system", content=(
                "你是一个任务分析器。给定一个任务，返回需要的 Agent 角色列表。\n"
                "可用角色: researcher(搜索/研究), executor(执行/写文件/调API), "
                "reviewer(审核/检查), designer(图片/设计)。\n"
                "回复格式: JSON数组，如 [\"researcher\", \"executor\"]"
            )),
            Message(role="user", content=task),
        ]
        thought = await self.llm.chat(messages)
        import json
        try:
            content = thought.content.strip()
            if "```" in content:
                content = content.split("```")[1].split("```")[0]
            roles = json.loads(content)
            return roles if roles else ["researcher", "executor", "reviewer"]
        except (json.JSONDecodeError, KeyError):
            return ["researcher", "executor", "reviewer"]

    async def _pick_role(self, step_description: str, available_roles: list[str]) -> str:
        """让 LLM 判断这个步骤最适合哪个角色."""
        if len(available_roles) <= 1:
            return available_roles[0]
        messages = [
            Message(role="system", content=(
                "你是一个任务分配器。给定一个步骤描述和可用角色列表，"
                "返回最适合执行这个步骤的角色名。只返回角色名，不要解释。\n"
                f"可用角色: {available_roles}"
            )),
            Message(role="user", content=step_description),
        ]
        thought = await self.llm.chat(messages)
        role = thought.content.strip().lower()
        for r in available_roles:
            if r in role:
                return r
        return available_roles[0]
```

---

---

## Phase 5: Loop 层

### Task 5.1: 状态持久化

**文件:** `loop/state.py`

```python
"""Loop 状态管理 — 保存/恢复执行检查点."""

from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.models.checkpoint import Checkpoint


class LoopState:
    """执行状态快照."""

    def __init__(self, task_id: int):
        self.task_id = task_id
        self.current_step: int = 0
        self.status: str = "running"
        self.data: dict = {}

    async def save(self, session: AsyncSession) -> None:
        """保存当前状态到数据库."""
        stmt = select(Checkpoint).where(Checkpoint.task_id == self.task_id)
        result = await session.execute(stmt)
        checkpoint = result.scalar_one_or_none()

        state_data = {
            "current_step": self.current_step,
            "status": self.status,
            "data": self.data,
        }

        if checkpoint:
            checkpoint.state = state_data
            checkpoint.created_at = datetime.utcnow()
        else:
            checkpoint = Checkpoint(task_id=self.task_id, state=state_data)
            session.add(checkpoint)

        await session.commit()

    @classmethod
    async def load(cls, task_id: int, session: AsyncSession) -> "LoopState | None":
        """从数据库恢复状态."""
        stmt = select(Checkpoint).where(Checkpoint.task_id == task_id)
        result = await session.execute(stmt)
        checkpoint = result.scalar_one_or_none()

        if not checkpoint:
            return None

        state = cls(task_id)
        state.current_step = checkpoint.state.get("current_step", 0)
        state.status = checkpoint.state.get("status", "running")
        state.data = checkpoint.state.get("data", {})
        return state
```

---

### Task 5.2: 循环控制器

**文件:** `loop/controller.py`

```python
"""循环控制器 — 驱动任务持续执行直到完成."""

from sqlalchemy.ext.asyncio import AsyncSession
from harness.orchestrator import Orchestrator
from loop.state import LoopState
from amor.logging import get_logger

logger = get_logger(__name__)


async def run_task_loop(
    task_id: int,
    task: str,
    orchestrator: Orchestrator,
    session: AsyncSession,
    max_retries: int = 3,
) -> dict:
    """执行一个任务，失败自动重试，状态持久化."""

    state = await LoopState.load(task_id, session) or LoopState(task_id)

    retries = 0
    while state.status == "running" and retries < max_retries:
        logger.info("loop_step", extra={"task_id": task_id, "step": state.current_step})

        try:
            result = await orchestrator.execute(task)

            state.current_step += 1
            state.data["last_result"] = result
            state.status = "done"
            await state.save(session)

            logger.info("task_complete", extra={"task_id": task_id})
            return result

        except Exception as e:
            retries += 1
            logger.error("loop_error", extra={"task_id": task_id, "retry": retries, "error": str(e)})
            state.status = "running"
            state.data["last_error"] = str(e)
            await state.save(session)

            if retries >= max_retries:
                state.status = "failed"
                await state.save(session)
                return {"error": str(e), "retries": retries}
```

---

## Phase 6: Web UI

### Task 6.1: FastAPI 应用入口

**文件:** `web/app.py`

```python
"""Amor Agent Web 入口."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from web.routes import chat, agent, model, skill
from web.ws import websocket_endpoint

app = FastAPI(title="Amor Agent", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(agent.router, prefix="/api", tags=["agent"])
app.include_router(model.router, prefix="/api", tags=["model"])
app.include_router(skill.router, prefix="/api", tags=["skill"])

# WebSocket
app.websocket("/ws/{conversation_id}")(websocket_endpoint)

# 前端
app.mount("/", StaticFiles(directory="web/static", html=True), name="static")


@app.on_event("startup")
async def startup():
    """启动时: 1) 注册工具 2) 加载 Skill 3) 连接 MCP Server."""
    from harness.tool_registry import ToolRegistry
    from harness.skills.loader import discover_and_register
    from harness.mcp.client import connect_mcp_server

    # 工具
    registry = ToolRegistry()
    _register_builtin_tools(registry)
    _register_user_tools(registry)

    # MCP Server 连接（从环境变量读取配置）
    mcp_connections: list = []
    import os
    mcp_config = os.getenv("MCP_SERVERS", "")  # 格式: "npx:server1:/tmp,npx:server2"
    if mcp_config:
        for entry in mcp_config.split(","):
            parts = entry.strip().split(":")
            if len(parts) >= 1:
                conn = await connect_mcp_server(parts, registry)
                mcp_connections.append(conn)

    app.state.tool_registry = registry
    app.state.mcp_connections = mcp_connections

    # Skill（Prompt 注入，扫描 .md 文件）
    skills = discover_and_register()
    app.state.skills = skills


@app.on_event("shutdown")
async def shutdown():
    """关闭所有 MCP 连接."""
    for conn in getattr(app.state, "mcp_connections", []):
        await conn.close()


def _register_builtin_tools(registry):
    """注册内置工具."""
    from harness.skills.builtin.file_ops import ReadFileTool, WriteFileTool, ListFilesTool
    from harness.skills.builtin.shell import RunShellTool
    from harness.skills.builtin.search import WebSearchTool, RAGQueryTool
    from harness.skills.builtin.image_gen import GenerateImageTool

    for tool_cls in [ReadFileTool, WriteFileTool, ListFilesTool, RunShellTool,
                     WebSearchTool, RAGQueryTool, GenerateImageTool]:
        registry.register(tool_cls())


def _register_user_tools(registry):
    """扫描 skills/user/ 目录，注册用户自定义 Tool."""
    import importlib
    from pathlib import Path

    user_dir = Path("harness/skills/user")
    for py_file in user_dir.glob("*.py"):
        if py_file.name.startswith("_"):
            continue
        module = importlib.import_module(f"harness.skills.user.{py_file.stem}")
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (isinstance(attr, type)
                and hasattr(attr, "schema")
                and hasattr(attr, "execute")
                and attr.__name__ != "ToolProtocol"):
                registry.register(attr())
```

**文件:** `web/deps.py`

```python
"""FastAPI 依赖注入."""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from db.engine import get_db
from llm.client import LiteLLMClient


def get_llm(model: str = "gpt-4o") -> LiteLLMClient:
    """获取 LLM 客户端."""
    return LiteLLMClient(model=model)


def get_db_session() -> AsyncSession:
    """获取数据库 session."""
    return Depends(get_db)
```

---

### Task 6.2: 路由

**`web/routes/chat.py`** — 对话 API:

```python
"""对话 API — 发送消息、获取历史."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class ChatRequest(BaseModel):
    conversation_id: int | None = None
    message: str
    model: str = "gpt-4o"


@router.post("/chat")
async def send_message(req: ChatRequest, request: Request):
    """用户发送消息，Agent 执行并返回结果."""
    from harness.orchestrator import Orchestrator
    from harness.tool_registry import ToolRegistry
    from llm.client import LiteLLMClient

    llm = LiteLLMClient(model=req.model)
    registry: ToolRegistry = request.app.state.tool_registry

    orchestrator = Orchestrator(
        llm=llm, registry=registry,
        event_bus=getattr(request.app.state, "event_bus", None),
    )
    result = await orchestrator.execute(req.message)

    return {
        "content": result["summary"],
        "mode": result.get("mode", "multi"),
        "tokens": result.get("total_tokens", 0),
    }


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(conversation_id: int):
    return {"conversation_id": conversation_id, "messages": []}
```

**`web/routes/model.py`** — 模型管理 API:

```python
"""模型管理 API — 列出和切换 LLM 模型."""

from fastapi import APIRouter

router = APIRouter()

AVAILABLE_MODELS = [
    {"id": "gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
    {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
    {"id": "gemini/gemini-2.0-flash", "name": "Gemini 2.0 Flash", "provider": "Google"},
    {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat", "provider": "DeepSeek"},
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "provider": "Anthropic"},
]

_current_model = "gpt-4o"


@router.get("/models")
async def list_models():
    return {"models": AVAILABLE_MODELS, "current": _current_model}


@router.put("/models/active")
async def set_active_model(model_id: str):
    global _current_model
    _current_model = model_id
    return {"current": _current_model}
```

**`web/routes/agent.py`** — Agent 角色管理:

```python
"""Agent 管理 API — 列出内置角色."""

from fastapi import APIRouter
from prompt.roles import ROLES

router = APIRouter()


@router.get("/agents")
async def list_agents():
    result = [
        {"id": rid, "name": rid.capitalize(), "prompt_preview": p[:200]}
        for rid, p in ROLES.items()
    ]
    return {"agents": result}
```

**`web/routes/skill.py`** — Skill 管理:

```python
"""Skill 管理 API — 列出/重载 Skill."""

from fastapi import APIRouter, Request
from harness.skills.loader import discover_and_register

router = APIRouter()


@router.get("/skills")
async def list_skills(request: Request):
    skills = getattr(request.app.state, "skills", [])
    return {
        "skills": [
            {"name": s.name, "description": s.description, "source": s.source_file}
            for s in skills
        ]
    }


@router.post("/skills/reload")
async def reload_skills(request: Request):
    skills = discover_and_register()
    request.app.state.skills = skills
    return {"skills": [s.name for s in skills]}
```

**`web/routes/__init__.py`**:

```python
from web.routes.chat import router as chat_router
from web.routes.model import router as model_router
from web.routes.agent import router as agent_router
from web.routes.skill import router as skill_router

__all__ = ["chat_router", "model_router", "agent_router", "skill_router"]
```

---

### Task 6.3: WebSocket

**文件:** `web/ws.py`

```python
"""WebSocket — 实时推送 Agent 执行进度."""

from fastapi import WebSocket, WebSocketDisconnect
from amor.events.bus import EventBus
from amor.events.types import Event, EventType
import json


async def websocket_endpoint(websocket: WebSocket, conversation_id: int):
    await websocket.accept()

    # 创建事件总线，订阅所有事件并推送到前端
    bus = EventBus()

    async def forward_to_client(event: Event):
        await websocket.send_text(json.dumps({
            "type": event.type.value,
            "node_id": event.node_id,
            "error": event.error,
        }, ensure_ascii=False))

    for event_type in EventType:
        bus.subscribe(event_type, forward_to_client)

    # 把 bus 存到 app.state 供 Agent 使用
    websocket.app.state.event_bus = bus

    try:
        while True:
            await websocket.receive_text()  # 保活
    except WebSocketDisconnect:
        pass
```

---

### Task 6.4: 前端

**文件:** `web/static/index.html`

一个简单的 SPA 页面：对话界面 + 模型下拉 + Token/费用显示 + 任务状态进度条。用原生 HTML + CSS + 少量 JS 实现，不引入前端框架。

---

## Phase 7: 集成

### Task 7.1: docker-compose.yml

```yaml
version: "3.8"
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: amor
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  chromadb:
    image: chromadb/chroma
    ports:
      - "8001:8000"

volumes:
  pgdata:
```

---

### Task 7.2: 端到端启动

```bash
docker-compose up -d
alembic upgrade head
python -m uvicorn web.app:app --reload --port 8000
```

打开 `http://localhost:8000` → 输入任务 → Agent 执行 → 看到结果。

---

## 总览

```
Phase 1: 数据层          Task 1.1-1.3  (~1.5h)
Phase 2: Prompt 层       Task 2.1      (~20min)
Phase 3: Context 层      Task 3.1-3.6  (~1.5h)
Phase 4: Harness 层      Task 4.1-4.8  (~2.5h)
Phase 5: Loop 层         Task 5.1-5.2  (~30min)
Phase 6: Web UI          Task 6.1-6.4  (~2h)
Phase 7: 集成            Task 7.1-7.2  (~30min)

总计 ~8.5h
```

---

## 启动方式

### 1. 安装依赖

```bash
# Python
pip install -e ".[dev]"
pip install fastapi uvicorn litellm markitdown chromadb tavily-python mcp pyyaml httpx

# 前端
cd web
npm install
```

### 2. 配置 API Key

编辑项目根目录 `.env`：
```
DEEPSEEK_API_KEY=sk-xxx
TAVILY_API_KEY=tvly-xxx
```

### 3. 启动

**终端 1 — 后端：**
```bash
cd D:\LearnPython\Amor_agent
python -m uvicorn web.app:app --reload --port 8000
```

**终端 2 — 前端：**
```bash
cd D:\LearnPython\Amor_agent\web
npm run dev
```

浏览器打开 `http://localhost:5173`
