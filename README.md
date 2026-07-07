# Amor Agent

轻量但专业的四层 AI Agent 系统。遵循 **Prompt → Context → Harness → Loop** 四层 Agent 工程架构，带 Web UI。

![Python](https://img.shields.io/badge/Python-3.11+-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi)
![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vuedotjs)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql)
![License](https://img.shields.io/badge/License-MIT-green)

![screenshot](docs/screenshot.png)

## 架构总览

```mermaid
graph TB
    subgraph L4["🎨 接入层"]
        WEB["FastAPI<br/>REST + WebSocket"]
        UI["Vue 3 Web UI"]
    end

    subgraph L3["⚙️ Agent 引擎层"]
        ORCH["Orchestrator<br/>多 Agent 编排"]
        RUNNER["Agent Runner<br/>Think→Act→Observe→Judge"]
        PLANNER["LLM Planner<br/>任务拆解"]
        REGISTRY["Tool Registry<br/>工具注册中心"]
    end

    subgraph L2["🔧 核心服务层"]
        LLM["LiteLLM Client<br/>多模型统一调用"]
        CTX["Context Assembler<br/>上下文组装"]
        RAG["RAG 引擎<br/>ChromaDB 向量检索"]
        MEMORY["记忆存储<br/>PostgreSQL"]
        READER["文件解析器<br/>PDF/Word/Excel/图片"]
    end

    subgraph L1["🏗️ 基础设施层"]
        PROTO["协议层 ABC<br/>LLM/Tool/Memory/Planner"]
        EVENTS["EventBus<br/>发布/订阅事件总线"]
        DB["PostgreSQL + ChromaDB"]
        CFG["配置系统<br/>.env + 环境变量"]
    end

    UI --> WEB
    WEB --> ORCH
    ORCH --> RUNNER
    ORCH --> PLANNER
    RUNNER --> LLM
    RUNNER --> CTX
    RUNNER --> REGISTRY
    CTX --> RAG
    CTX --> MEMORY
    CTX --> READER
    LLM --> PROTO
    REGISTRY --> PROTO
    MEMORY --> DB
```

## 请求处理流程

```mermaid
sequenceDiagram
    actor User as 👤 用户
    participant Web as 🌐 FastAPI
    participant Orch as 🎯 Orchestrator
    participant Runner as 🏃 Agent Runner
    participant Ctx as 📋 Context Assembler
    participant LLM as 🧠 LLM
    participant Tool as 🔧 工具

    User->>Web: POST /api/chat
    Web->>Orch: execute(task)
    Orch->>Runner: run_agent(config, task)

    Runner->>Ctx: assemble_messages()
    Ctx->>Ctx: system prompt + 角色 + 工具列表
    Ctx->>Ctx: RAG 检索 + 网页搜索 + 文件内容
    Ctx->>Ctx: 记忆 + 对话历史
    Ctx-->>Runner: list[Message]

    loop Think → Act → Observe → Judge
        Runner->>LLM: chat(messages, tools)
        LLM-->>Runner: Thought (content + tool_calls?)

        alt 无 tool_calls: 任务完成
            Runner-->>Orch: 返回结果
        else 有 tool_calls: 执行工具
            Runner->>Tool: execute(name, args)
            Tool-->>Runner: 工具结果
            Runner->>Runner: 结果追加到 messages
        end
    end

    Orch-->>Web: {summary, tokens}
    Web-->>User: HTTP Response
```

## 核心循环：Think → Act → Observe → Judge

```mermaid
flowchart TD
    START(["🚀 收到任务"]) --> INIT["组装上下文<br/>assemble_messages()"]

    INIT --> LOOP{"step &lt; max_steps?<br/>(默认 30 步)"}
    LOOP -->|是| THINK["🧠 Think<br/>LLM 分析任务 + 可用工具<br/>决定: 直接回答 or 调工具"]

    THINK --> HAS_TOOLS{"需要调工具?"}

    HAS_TOOLS -->|否,直接回答| DONE["✅ 任务完成<br/>返回结果给用户"]
    HAS_TOOLS -->|是| RISK{"风险等级?"}

    RISK -->|"🔴 高危"| APPROVAL["⛔ 等待用户审批<br/>前端弹出确认卡片"]
    APPROVAL --> APPROVED{"用户决定?"}
    APPROVED -->|拒绝| SKIP["跳过该工具<br/>尝试其他方案"]
    APPROVED -->|允许| EXEC

    RISK -->|"🟢 安全"| EXEC["🔧 Act<br/>执行工具<br/>read_file / web_search / run_shell..."]

    EXEC --> OBSERVE["👁️ Observe<br/>工具结果注入上下文<br/>追加到 messages"]

    OBSERVE --> LOOP
    SKIP --> LOOP

    LOOP -->|否,超步数| FAIL["❌ 超步数限制<br/>返回错误"]

    style DONE fill:#2e7d32,color:#fff
    style FAIL fill:#c62828,color:#fff
    style APPROVAL fill:#e65100,color:#fff
```

## 多 Agent 协作

```mermaid
flowchart LR
    TASK["📝 用户任务"] --> ORCH["Orchestrator"]
    ORCH --> DECIDE["LLM 分析<br/>需要哪些角色?"]

    DECIDE --> ROLES["分配角色"]
    ROLES --> R1["🔬 Researcher<br/>搜索/研究"]
    ROLES --> R2["⚡ Executor<br/>写文件/调API"]
    ROLES --> R3["✅ Reviewer<br/>审核/检查"]
    ROLES --> R4["🎨 Designer<br/>图片/设计"]

    R1 -->|前置输出| R2
    R2 -->|提交审核| R3
    R3 -->|通过| DONE2["✅ 完成"]
    R3 -->|驳回(max 3次)| R2

    style DONE2 fill:#2e7d32,color:#fff
```

## 特性

- **多 Agent 协作** — Orchestrator 调度，研究员/执行者/审核员/设计师分工。Agent 自行决定是否委托子 Agent
- **RAG 知识检索** — MarkItDown 文件解析（PDF/Word/PPT/Excel）+ ChromaDB 向量检索
- **网页搜索** — Tavily 驱动，Agent 主动搜索实时信息
- **图片生成** — DALL-E API 集成
- **多模型切换** — LiteLLM 驱动，Web UI 一键切 OpenAI / Gemini / DeepSeek / Claude
- **自定义 Skill** — Markdown 文件即 Skill，丢进 `skills/user/` 就能用（兼容 Claude Code / Codex 格式）
- **MCP 协议** — 连接外部 MCP Server，自动映射为本地 ToolProtocol
- **中断审批** — 高危操作（rm -rf 等）弹出确认卡片，等人决策
- **文件操作** — read / write / edit / grep / glob / list_files
- **系统工具** — run_shell / get_time / webfetch
- **Token 统计** — 实时显示消耗量，自动计算费用
- **对话记忆** — 跨轮次上下文保持，历史对话可查
- **WebSocket 实时推送** — Agent 执行进度实时推送到前端
- **检查点恢复** — Loop 层状态持久化到 PostgreSQL，挂了能恢复

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | >= 3.11 | 3.11 以下无法运行 |
| Node.js | >= 18 | 前端构建 |
| PostgreSQL | 16 | 对话/任务/记忆持久化（可选，可用 Docker） |
| ChromaDB | - | 向量检索（可选，可用 Docker） |

## 快速开始

### 0. 启动依赖服务（Docker）

项目自带 `docker-compose.yml`，一键启动 PostgreSQL + ChromaDB：

```bash
docker compose up -d
```

> 不想用 Docker？自己装好 PostgreSQL 16 和 ChromaDB，修改 `.env` 里的 `AMOR_DATABASE_URL` 即可。

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

**完整环境变量：**

| 变量 | 必须 | 说明 |
|------|:--:|------|
| `DEEPSEEK_API_KEY` | ✅ | DeepSeek API 密钥 |
| `OPENAI_API_KEY` | - | OpenAI API 密钥（GPT-4o / DALL-E） |
| `TAVILY_API_KEY` | - | 网页搜索（[免费申请](https://tavily.com)） |
| `GEMINI_API_KEY` | - | Google Gemini API 密钥 |
| `LLAMA_CLOUD_API_KEY` | - | PDF/Word 解析（[免费申请](https://cloud.llamaindex.ai)） |
| `AMOR_DATABASE_URL` | - | PostgreSQL 连接串，默认 `postgresql+asyncpg://postgres:postgres@localhost:5432/amor` |
| `MCP_SERVERS` | - | 外部 MCP Server，格式 `npx:server1:/tmp,npx:server2` |
| `HF_HOME` | - | HuggingFace 模型缓存目录 |
| `HANLP_HOME` | - | HanLP 模型缓存目录 |

### 3. 启动

```bash
# 终端 1: 后端
python -m uvicorn web.app:app --reload --port 8000

# 终端 2: 前端
cd web && npm run dev
```

浏览器打开 `http://localhost:5173`

### 4. 验证

```bash
# 发送第一条消息
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好，介绍一下你自己", "model": "deepseek/deepseek-v4-pro"}'
```

返回：
```json
{
  "conversation_id": 1,
  "content": "你好！我是 Amor Agent，一个多功能 AI 助手……",
  "mode": "auto",
  "tokens": 156
}
```

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

## 详细文档

完整流程图、实例演练、数据库 ER 图 → [架构流程图](docs/architecture_flowchart.md)

## License

MIT
