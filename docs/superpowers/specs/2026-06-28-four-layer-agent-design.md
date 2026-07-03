# Amor Agent v3 — 四层通用多 Agent 系统设计文档

**日期**：2026-06-28
**版本**：v3 最终版
**状态**：待审核

---

## 1. 项目定位

一个**遵循四层 Agent 工程架构的通用多 Agent 系统**，带 Web UI。

用户在网页上输入任务 → 多个 AI Agent 分工协作 → 自动完成并展示结果。

---

## 2. 技术选型

| 分类 | 技术 | 原因 |
|---|---|---|
| Web | FastAPI + WebSocket | 异步、类型驱动、实时推送 |
| 数据库 | PostgreSQL + SQLAlchemy async | 企业标准、JSONB |
| 异步驱动 | asyncpg | PostgreSQL 最快驱动 |
| LLM | LiteLLM | 多模型统一 API + **Token计费** + 限速 |
| 文件解析 | MarkItDown | 所有格式 → Markdown |
| 向量库 | ChromaDB | 轻量、Python 原生 |
| 搜索 | Tavily | Agent 专用搜索 API |
| 图片生成 | DALL-E / Stable Diffusion API | 按需调用 |
| MCP | mcp (官方 SDK) | 标准协议 |

---

## 3. 四层架构

```
Web UI (FastAPI + WebSocket 实时推送)
────
Layer 4: Loop    控制器 + Checkpoint 持久化
Layer 3: Harness  Orchestrator(多Agent) · Runner · Planner · Skills · MCP · Verifier
Layer 2: Context  MarkItDown · Memory · ChromaDB RAG · Tavily · Assembler · Window
Layer 1: Prompt   SystemPrompt · Roles · FewShot
────
Infrastructure (amor/): 异常 · 日志 · 配置 · 协议 · DI · 事件
Data Layer: PostgreSQL + ChromaDB
```

---

## 4. 各层设计

### 4.1 Layer 1: Prompt Engineering

| 组件 | 文件 | 做什么 |
|---|---|---|
| 系统提示词 | `prompt/system.py` | Agent 通用身份定义 |
| 角色模板 | `prompt/roles.py` | 研究员/执行者/审核员/设计师 角色 Prompt |
| Few-shot | `prompt/templates.py` | 示例对话、CoT 模板 |

### 4.2 Layer 2: Context Engineering

| 组件 | 文件 | 技术 |
|---|---|---|
| 文件读取 | `context/reader.py` | MarkItDown（所有格式→Markdown） |
| 记忆存储 | `context/memory_store.py` | PostgreSQL（实现 MemoryProtocol） |
| RAG 检索 | `context/rag.py` | ChromaDB（embedding + 检索） |
| 网页搜索 | `context/web_search.py` | Tavily |
| 上下文组装 | `context/assembler.py` | 拼完整 messages |
| 窗口管理 | `context/window.py` | 摘要 + 裁剪 |

### 4.3 Layer 3: Harness Engineering

**多 Agent 编排**：

```
Orchestrator → 分析任务 → 分派给不同角色 Agent
    ├── 研究员 R1: 搜索 + 整理信息
    ├── 执行者 E1: 写文件 / 调 API
    ├── 审核员 V1: 检查结果质量
    └── 设计师 D1: 生成图片（可选）
```

**单 Agent 执行循环**：

```
while 未完成 and 步数 < 上限:
    Think → Act → Observe → Judge
```

**工具生态**（三层）：

```
MCP Tools（外部协议，自动包装）
User Skills（skills/user/ 丢进去就用）
Built-in Skills（read_file, write_file, run_shell, search_web, rag_query, generate_image）
```

**Skill 机制**：用户写一个 Python 类，标注 name + description + tools，丢进 `skills/user/`，启动时自动发现注册。

### 4.4 Layer 4: Loop Engineering

每步执行后保存 Checkpoint → PostgreSQL。挂了恢复，继续跑。WebSocket 实时推送进度。

---

## 5. Token 计量与计费

### 5.1 数据记录

每次 LLM 调用记录到 `agent_executions` 表：

```
prompt_tokens      — 输入 token 数
completion_tokens  — 输出 token 数
total_tokens       — 合计
cost               — 费用（LiteLLM 自动算）
model              — 用了哪个模型
```

### 5.2 统计维度

- **单次对话**：本次对话总 token + 总费用
- **按 Agent**：每个 Agent 角色各消耗多少
- **按模型**：OpenAI vs Gemini vs DeepSeek 各自用量
- **按时间**：今日 / 本周 / 本月

### 5.3 Web UI 展示

对话页面实时显示 Token 消耗 + 费用。设置页可配预算上限。

---

## 6. 数据层

### PostgreSQL

```
conversations     — 会话
messages          — 对话消息 (tool_calls JSONB)
memories          — 持久记忆 (key, value JSONB, importance)
tasks             — 任务 (title, status, plan JSONB)
task_steps        — 任务步骤 (agent_role, depends_on, status, result)
agents            — Agent 定义 (name, role, system_prompt, tools JSONB)
agent_executions  — 执行记录 (input, output, token用量, cost, 耗时, error)
checkpoints       — Loop 检查点 (task_id, state JSONB)
```

### ChromaDB

```
collection: documents (embedding + metadata + text)
```

---

## 7. 项目结构

```
amor_agent/
├── amor/                    # 基础设施（已有）
│   ├── exceptions.py, logging.py, config.py
│   ├── protocols/ (llm, tool, memory, planner)
│   ├── di/ (container, inject)
│   └── events/ (types, bus)
│
├── db/                      # 数据层
│   ├── engine.py, base.py
│   ├── models/ (conversation, message, memory, task, agent, checkpoint, execution)
│   └── migrations/
│
├── llm/
│   └── client.py            # LiteLLM 封装 + token 统计
│
├── prompt/                  # Layer 1
│   ├── system.py, roles.py, templates.py
│
├── context/                 # Layer 2
│   ├── reader.py, memory_store.py, rag.py, web_search.py, assembler.py, window.py
│
├── harness/                 # Layer 3
│   ├── orchestrator.py, runner.py, planner.py, tool_registry.py, verifier.py
│   ├── mcp/client.py
│   └── skills/
│       ├── loader.py
│       ├── builtin/ (file_ops, shell, search, image_gen)
│       └── user/ (.gitkeep)
│
├── loop/                    # Layer 4
│   ├── controller.py, state.py
│
├── web/                     # Web UI
│   ├── app.py, deps.py, ws.py
│   ├── routes/ (chat, agent, model, skill, stats)
│   └── static/index.html
│
├── docker-compose.yml       # PostgreSQL + ChromaDB + App
├── pyproject.toml
└── tests/
```

---

## 8. 数据流

```
用户 Web UI 输入任务
  → Prompt 层 加载角色模板
  → Context 层 注入 文件+记忆+RAG+搜索+历史
  → Harness 层 Orchestrator 分派 → Agent 执行 → Verifier 验证
  → Loop 层 判断完成/继续 → 持久化
  → WebSocket 推送进度 → UI 展示结果 + Token 消耗
```

---

## 9. 开发顺序

```
Phase 1: 基础设施   amor 清理 + db 建表 + llm LiteLLM 封装
Phase 2: Prompt 层  system · roles · templates
Phase 3: Context 层 reader · memory · rag · search · assembler · window
Phase 4: Harness 层 tool_registry → skills → mcp → planner → runner → orchestrator
Phase 5: Loop 层    state → controller
Phase 6: Web UI     FastAPI + WebSocket + 前端
Phase 7: 集成       docker-compose up 端到端跑通
```

## 10. v1 不做

- 用户登录/鉴权
- 本地模型推理
- 移动端
- 分布式
