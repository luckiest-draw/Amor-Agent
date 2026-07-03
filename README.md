# Amor Agent

轻量但专业的四层 AI Agent 系统。遵循 **Prompt → Context → Harness → Loop** 四层 Agent 工程架构，带 Web UI。

![screenshot](docs/screenshot.png)

## 特性

- **多 Agent 协作** — Orchestrator 调度，研究员/执行者/审核员/设计师分工。Agent 自行决定是否委托子 Agent
- **RAG 知识检索** — MarkItDown 文件解析（PDF/Word/PPT/Excel）+ ChromaDB 向量检索
- **网页搜索** — Tavily 驱动，Agent 主动搜索实时信息
- **图片生成** — DALL-E API 集成
- **多模型切换** — LiteLLM 驱动，Web UI 一键切 OpenAI / Gemini / DeepSeek
- **自定义 Skill** — Markdown 文件即 Skill，丢进 `skills/user/` 就能用（兼容 Claude Code / Codex 格式）
- **MCP 协议** — 连接外部 MCP Server，自动映射为本地 ToolProtocol
- **中断审批** — 高危操作（rm -rf 等）弹出确认卡片，等人决策
- **文件操作** — read / write / edit / grep / glob / list_files
- **系统工具** — run_shell / get_time / webfetch
- **Token 统计** — 实时显示消耗量，自动计算费用
- **对话记忆** — 跨轮次上下文保持，历史对话可查

## 架构

```
┌──────────────────────────────────────────┐
│              Web UI (Vue 3)               │
├──────────────────────────────────────────┤
│  Layer 4: Loop  — 自主持续运行             │
│  Layer 3: Harness — 多 Agent 编排          │
│  Layer 2: Context — 文件+记忆+RAG+搜索      │
│  Layer 1: Prompt — 系统角色+模板            │
├──────────────────────────────────────────┤
│  Infrastructure: Exceptions / Log /        │
│  Config / Protocols / DI / Events          │
├──────────────────────────────────────────┤
│  Data: PostgreSQL + ChromaDB               │
└──────────────────────────────────────────┘
```

## 快速开始

### 1. 安装

```bash
git clone https://github.com/luckiest-draw/Amor-Agent.git
cd Amor-Agent

# 后端
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -e .
pip install fastapi uvicorn litellm sqlalchemy[asyncio] asyncpg pydantic-settings

# 前端
cd web && npm install && cd ..
```

### 2. 配置

编辑 `.env`：
```env
DEEPSEEK_API_KEY=sk-你的key
TAVILY_API_KEY=tvly-你的key
```

### 3. 启动

```bash
# 终端 1: 后端
python -m uvicorn web.app:app --reload --port 8000

# 终端 2: 前端
cd web && npm run dev
```

浏览器打开 `http://localhost:5173`

## 项目结构

```
amor_agent/
├── amor/             基础设施（异常、日志、配置、协议、DI、事件）
│   ├── protocols/     LLM / Tool / Memory / Planner 接口
│   ├── di/            依赖注入容器
│   └── events/        事件总线
├── prompt/           Layer 1: System Prompt · 角色模板 · Few-shot
├── context/          Layer 2: 文件解析器 · RAG · 搜索 · 记忆 · 上下文组装
├── harness/          Layer 3: Orchestrator · Runner · Planner · 工具注册 · MCP · Skill
├── loop/             Layer 4: 循环控制器 · 状态持久化
├── web/              FastAPI 后端 + Vue 3 前端
├── db/               PostgreSQL 模型（SQLAlchemy async）
├── llm/              LiteLLM 封装（多模型统一调用）
└── tests/
```

## 工具列表

| 类别 | 工具 | 说明 |
|------|------|------|
| 文件 | read_file, write_file, edit_file | 读写和精准修改 |
| 文件 | list_files, glob, grep | 查找和搜索 |
| 系统 | run_shell, get_time | 命令执行和时间 |
| 搜索 | web_search, webfetch | Tavily 搜索 + 网页抓取 |
| 知识 | rag_query | ChromaDB 向量检索 |
| 生成 | generate_image | DALL-E 图片生成 |
| 编排 | delegate | Agent 间任务委托 |

## License

MIT
