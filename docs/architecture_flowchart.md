# Amor Agent 架构流程图

> 四层 AI Agent 系统完整流程解析

---

## 目录

1. [系统总览 — 四层架构](#1-系统总览--四层架构)
2. [请求完整生命周期](#2-请求完整生命周期)
3. [核心循环: Think → Act → Observe → Judge](#3-核心循环-think--act--observe--judge)
4. [上下文组装流程](#4-上下文组装流程)
5. [多 Agent 编排流程](#5-多-agent-编排流程)
6. [工具系统](#6-工具系统)
7. [事件系统 & WebSocket 实时推送](#7-事件系统--websocket-实时推送)
8. [数据库 ER 图](#8-数据库-er-图)
9. [完整实例演练](#9-完整实例演练)

---

## 1. 系统总览 — 四层架构

```mermaid
graph TB
    subgraph L4["🎨 Layer 4: 接入层"]
        WEB["FastAPI Web Server<br/>web/app.py"]
        WS["WebSocket<br/>web/ws.py"]
        ROUTES["REST API<br/>chat/agent/model/skill/knowledge"]
    end

    subgraph L3["⚙️ Layer 3: Agent 引擎"]
        ORCH["Orchestrator 编排器<br/>harness/orchestrator.py"]
        RUNNER["Agent Runner<br/>harness/runner.py"]
        PLANNER["LLM Planner<br/>harness/planner.py"]
        REGISTRY["Tool Registry<br/>harness/tool_registry.py"]
    end

    subgraph L2["🔧 Layer 2: 核心服务"]
        LLM["LiteLLM Client<br/>llm/client.py"]
        CTX["Context Assembler<br/>context/assembler.py"]
        RAG["RAG 引擎<br/>context/rag.py"]
        MEMORY["记忆存储<br/>context/memory_store.py"]
        READER["文件读取器<br/>context/reader.py"]
        SEARCH["网页搜索<br/>context/web_search.py"]
        WINDOW["上下文窗口<br/>context/window.py"]
    end

    subgraph L1["🏗️ Layer 1: 基础框架"]
        CFG["AmorConfig<br/>amor/config.py"]
        PROTO["协议层 (ABC)<br/>LLP/Tool/Memory/Planner"]
        EVENTS["EventBus 事件总线<br/>amor/events/"]
        EXC["异常体系<br/>amor/exceptions.py"]
        LOG["结构化日志<br/>amor/logging.py"]
        DB["PostgreSQL<br/>db/engine.py"]
    end

    WEB --> ORCH
    WS --> EVENTS
    ROUTES --> ORCH
    ORCH --> RUNNER
    ORCH --> PLANNER
    RUNNER --> LLM
    RUNNER --> CTX
    RUNNER --> REGISTRY
    CTX --> RAG
    CTX --> MEMORY
    CTX --> READER
    CTX --> SEARCH
    CTX --> WINDOW
    LLM --> PROTO
    REGISTRY --> PROTO
    MEMORY --> DB
    EVENTS --> WS
```

**层次关系:**
- **Layer 1 (基础框架):** 所有模块的基石 — 配置、协议、事件、异常、日志、数据库
- **Layer 2 (核心服务):** LLM 调用、上下文组装、RAG、记忆、文件解析
- **Layer 3 (Agent 引擎):** Agent 运行循环、多 Agent 编排、任务规划、工具注册
- **Layer 4 (接入层):** HTTP API、WebSocket、前端静态文件

---

## 2. 请求完整生命周期

```mermaid
sequenceDiagram
    actor User as 👤 用户
    participant Web as 🌐 FastAPI<br/>web/app.py
    participant Orch as 🎯 Orchestrator<br/>harness/orchestrator.py
    participant Runner as 🏃 Agent Runner<br/>harness/runner.py
    participant Ctx as 📋 Context Assembler<br/>context/assembler.py
    participant LLM as 🧠 LiteLLM Client<br/>llm/client.py
    participant ToolReg as 🔧 Tool Registry<br/>harness/tool_registry.py
    participant Event as 📡 EventBus
    participant DB as 🗄️ PostgreSQL

    User->>Web: POST /api/chat {message, model}
    Web->>Web: 获取/创建 conversation_id
    Web->>Web: 创建 LiteLLMClient(model)
    Web->>Orch: Orchestrator(llm, registry, event_bus)
    Web->>Orch: orchestrator.execute(task, history)

    Orch->>Runner: run_agent(config, task, llm, registry, event_bus)

    Note over Runner: ═══ Think→Act→Observe→Judge 循环开始 ═══

    Runner->>Ctx: assemble_messages(task, system_prompt, tools, history)
    Ctx->>Ctx: 1. 拼装 system prompt + role
    Ctx->>Ctx: 2. 注入 Skill prompts
    Ctx->>Ctx: 3. 列出可用工具
    Ctx->>Ctx: 4. 读文件内容 (如有)
    Ctx->>Ctx: 5. RAG 检索 (如有)
    Ctx->>Ctx: 6. 网页搜索 (如有)
    Ctx->>Ctx: 7. 加载记忆
    Ctx->>Ctx: 8. 拼接对话历史(最近20条)
    Ctx->>Ctx: 9. 追加用户任务
    Ctx-->>Runner: list[Message]

    loop Think→Act→Observe→Judge (max 30 steps)
        Runner->>Event: emit NODE_START
        Runner->>LLM: llm.chat(messages, tools)
        LLM->>LLM: LiteLLM → OpenAI/DeepSeek/Gemini/Claude API
        LLM-->>Runner: Thought(content, tool_calls?, usage)

        alt 无 tool_calls → 任务完成
            Runner->>Event: emit NODE_END
            Runner-->>Orch: AgentResult(status="success", output)
        else 有 tool_calls → 执行工具
            loop 每个 tool_call
                alt 高风险工具 (requires_approval=true)
                    Runner->>Event: emit INTERRUPT
                    Event-->>User: 等待审批
                    User-->>Runner: 允许/拒绝
                end
                Runner->>ToolReg: registry.execute(tool_name, args)
                ToolReg-->>Runner: 工具执行结果
                Runner->>Runner: messages.append(tool_result)
            end
            Runner->>Event: emit NODE_END
        end
    end

    Orch-->>Web: {task, summary, total_tokens}
    Web->>Web: _save_turn(conv_id, user_msg, agent_msg)
    Web-->>User: {conversation_id, content, tokens}

    Event-->>User: WebSocket 实时推送进度
```

---

## 3. 核心循环: Think → Act → Observe → Judge

这是整个系统的心脏 —— 单个 Agent 的执行循环。

```mermaid
flowchart TD
    START(["🚀 run_agent() 被调用"]) --> INIT["初始化 AgentResult<br/>获取工具 Schema 列表<br/>调用 assemble_messages()"]

    INIT --> LOOP{"step &lt; max_steps?<br/>(默认 30)"}

    LOOP -->|是| EMIT_START["📡 emit NODE_START 事件"]

    EMIT_START --> THINK["🧠 Think: llm.chat(messages, tools)<br/>LLM 分析任务 + 可用工具 → 决定下一步"]

    THINK --> CHECK_ERR{"LLM 调用<br/>成功?"}
    CHECK_ERR -->|失败| FAIL["status='failed'<br/>记录错误 → break"]
    CHECK_ERR -->|成功| RECORD["记录 token 用量<br/>assistant 消息加入 messages"]

    RECORD --> HAS_TOOLS{"thought.tool_calls<br/>不为空?"}

    HAS_TOOLS -->|否| DONE["✅ Judge: 模型认为任务完成<br/>status='success'<br/>emit NODE_END → return"]

    HAS_TOOLS -->|是| ACT_LOOP["🔧 Act: 遍历每个 tool_call"]

    ACT_LOOP --> RISK_CHECK{"工具风险等级?<br/>requires_approval?"}

    RISK_CHECK -->|"高风险 (critical/high)"| INTERRUPT["⛔ Interrupt 机制<br/>emit INTERRUPT 事件<br/>等待用户审批 (最多5分钟)"]

    INTERRUPT --> APPROVED{"用户审批?"}
    APPROVED -->|拒绝| SKIP["跳过此工具<br/>注入拒绝消息<br/>继续下一个 tool_call"]
    APPROVED -->|允许| EXEC["执行工具"]

    RISK_CHECK -->|"低风险 (none/low/medium)"| EXEC

    EXEC --> EXEC_TOOL["registry.execute(tool_name, args)<br/>调用工具 → 获取结果"]

    EXEC_TOOL --> OBSERVE["👁️ Observe: 工具结果作为 tool role 消息<br/>追加到 messages 列表<br/>记录到 result.steps"]

    OBSERVE --> ACT_LOOP

    ACT_LOOP -->|所有 tool_call 处理完| EMIT_END["📡 emit NODE_END 事件"]

    EMIT_END --> STEP_INC["step += 1"]
    STEP_INC --> MAX_CHECK{"step >= max_steps - 1?"}
    MAX_CHECK -->|是| MAX_FAIL["status='failed'<br/>超过最大步数限制"]
    MAX_CHECK -->|否| LOOP

    LOOP -->|否| MAX_FAIL

    DONE --> RETURN(["返回 AgentResult"])
    FAIL --> RETURN
    MAX_FAIL --> RETURN
```

**关键设计决策:**
- **不写死策略**: 模型自己判断是直接回答还是调工具，不强制 ReAct/PlanExecute 模式
- **工具+对话混合**: 每次 Think 都带完整工具列表，模型自主决策
- **中断机制**: 高危操作 (如 `run_shell`) 发射 INTERRUPT 事件，等人点"允许"

---

## 4. 上下文组装流程

```mermaid
flowchart TD
    START(["assemble_messages() 被调用"]) --> SYS["1️⃣ 构建系统消息<br/>system_prompt + role_prompt"]

    SYS --> SKILL{"有 Skill<br/>Prompt 注入?"}
    SKILL -->|是| SKILL_INJ["注入 Skill 行为规则<br/>get_system_prompt_extensions()"]
    SKILL -->|否| TOOLS

    SKILL_INJ --> TOOLS{"有工具<br/>Schema?"}
    TOOLS -->|是| TOOLS_INJ["追加工具列表<br/>每个工具的 name + description"]
    TOOLS -->|否| FILES

    TOOLS_INJ --> FILES{"有文件<br/>路径?"}

    FILES -->|是| READ_FILES["📄 读取文件内容<br/>read_file() 按类型路由解析器"]
    READ_FILES --> FILES_DETAIL["PDF/DOCX → LlamaParse<br/>XLSX/CSV → pandas → HTML表格<br/>PNG/JPG → GPT-4o Vision<br/>PPTX/HTML → MarkItDown<br/>MD/TXT → 直接读"]

    FILES -->|否| RAG_CHECK

    FILES_DETAIL --> RAG_CHECK{"有 RAG<br/>查询?"}

    RAG_CHECK -->|是| RAG_DO["🔍 RAG 检索<br/>BGE embedding → ChromaDB 向量检索<br/>返回 top_k 最相关片段"]

    RAG_CHECK -->|否| SEARCH_CHECK
    RAG_DO --> SEARCH_CHECK{"有网页<br/>搜索?"}

    SEARCH_CHECK -->|是| SEARCH_DO["🌐 Tavily Search API<br/>返回标题+URL+摘要"]
    SEARCH_CHECK -->|否| MEM_CHECK

    SEARCH_DO --> MEM_CHECK{"有记忆<br/>存储?"}

    MEM_CHECK -->|是| MEM_LOAD["🧠 加载记忆<br/>PostgresMemory.query()<br/>如: user_preferences"]
    MEM_CHECK -->|否| HIST_CHECK

    MEM_LOAD --> HIST_CHECK{"有对话<br/>历史?"}

    HIST_CHECK -->|是| HIST_TRIM["✂️ 裁剪历史<br/>window.trim_messages()<br/>保留最近20条 + system prompt"]
    HIST_CHECK -->|否| TASK

    HIST_TRIM --> TASK["9️⃣ 追加用户任务<br/>Message(role='user', content=task)"]

    TASK --> RETURN(["返回 list[Message] — 完整的 LLM 输入"])
```

---

## 5. 多 Agent 编排流程

```mermaid
flowchart TD
    START(["Orchestrator.execute(task)"]) --> CHECK{"task 复杂?<br/>需要多角色?"}

    CHECK -->|简单| SINGLE["单 Agent 模式<br/>直接 run_agent()<br/>模型自主决策"]

    CHECK -->|复杂| DECIDE["🎭 角色决策<br/>_decide_roles(task)<br/>LLM 判断需要哪些角色"]

    DECIDE --> ROLES["可用角色:<br/>🔬 researcher — 搜索/研究<br/>⚡ executor — 执行操作<br/>✅ reviewer — 审核检查<br/>🎨 designer — 图片设计"]

    ROLES --> PLAN["📋 任务规划<br/>planner.plan(task, context)<br/>LLM 拆成 3-7 个步骤"]

    PLAN --> GROUP["按依赖分组<br/>无依赖 → 并行<br/>有依赖 → 串行"]

    GROUP --> EXEC_LOOP["执行每个步骤"]

    EXEC_LOOP --> PICK["_pick_role(step, roles)<br/>LLM 选最合适的角色"]

    PICK --> INJECT["_collect_upstream_results()<br/>注入前置步骤的输出<br/>→ Agent 间通信"]

    INJECT --> RUN["run_agent(config, task+context)"]

    RUN --> REVIEW_CHECK{"有 reviewer<br/>角色?"}

    REVIEW_CHECK -->|是| REVIEW["🔍 _review_loop()<br/>审核员检查输出质量"]

    REVIEW --> VERDICT{"审核结果?"}
    VERDICT -->|"✅ pass"| NEXT
    VERDICT -->|"⚠️ reject"| RETRY["退回重做<br/>注入修改意见<br/>最多重试3次"]
    RETRY --> RUN

    REVIEW_CHECK -->|否| NEXT

    NEXT{"还有步骤?"} -->|是| EXEC_LOOP
    NEXT -->|否| SUMMARIZE["📊 汇总所有结果<br/>_summarize()"]

    SINGLE --> RETURN
    SUMMARIZE --> RETURN(["返回完整结果"])
```

**Agent 间通信机制:**
```
Step 1 (researcher): "搜索 Python 异步编程最佳实践"
  → 输出: "asyncio 核心概念: event loop, coroutine, task..."

Step 2 (executor, depends_on=[1]):
  → 上下文自动注入:
    "## 前置步骤的输出（供参考）
     ### [1] researcher 的输出
     asyncio 核心概念: event loop, coroutine, task..."
  → 基于研究结果执行操作
```

---

## 6. 工具系统

```mermaid
flowchart LR
    subgraph SOURCE["📦 工具来源"]
        BUILTIN["内置工具<br/>harness/skills/builtin/"]
        USER["用户工具<br/>harness/skills/user/"]
        MCP["MCP Server<br/>外部工具"]
    end

    subgraph REGISTRY["🔧 ToolRegistry"]
        REG["_tools: dict[name, ToolProtocol]"]
    end

    subgraph TOOLS["🛠️ 内置工具清单"]
        T1["read_file — 读取文件"]
        T2["write_file — 写入文件"]
        T3["list_files — 列出目录"]
        T4["run_shell — 执行命令"]
        T5["web_search — 网页搜索"]
        T6["rag_query — 知识库检索"]
        T7["generate_image — AI 生图"]
        T8["grep — 内容搜索"]
        T9["edit_file — 精准编辑"]
        T10["get_time — 获取时间"]
        T11["glob — 文件匹配"]
        T12["webfetch — 抓取网页"]
    end

    BUILTIN --> REG
    USER --> REG
    MCP -->|"_MCPToolWrapper"| REG
    REG --> TOOLS

    subgraph SCHEMA["📋 ToolSchema"]
        NAME["name: 工具名"]
        DESC["description: 用途描述"]
        PARAMS["parameters: JSON Schema"]
        RISK["risk_level: none|low|medium|high|critical"]
        APPROVAL["requires_approval: bool"]
    end

    REG --> SCHEMA
```

**工具风险等级与审批:**

| 风险等级 | 含义 | 是否需要审批 | 示例 |
|---------|------|------------|------|
| `none` | 只读操作 | ❌ | `read_file`, `grep`, `get_time` |
| `low` | 低风险读操作 | ❌ | `web_search`, `rag_query` |
| `medium` | 可能修改文件 | ❌/✅ | `write_file`, `edit_file` |
| `high` | 执行外部命令 | ✅ | `run_shell` |
| `critical` | 不可逆操作 | ✅ | `rm -rf`, `DROP TABLE` |

---

## 7. 事件系统 & WebSocket 实时推送

```mermaid
sequenceDiagram
    participant Runner as 🏃 Agent Runner
    participant Bus as 📡 EventBus
    participant WS as 🔌 WebSocket
    participant Frontend as 🖥️ 前端

    Runner->>Bus: emit(NODE_START, node_id="agent_think_0")
    Bus->>WS: forward_to_client(event)
    WS->>Frontend: {"type":"node_start","node_id":"agent_think_0"}

    Runner->>Runner: LLM 思考中...
    Runner->>Bus: emit(NODE_END, node_id="agent_think_0")
    Bus->>WS: forward_to_client(event)
    WS->>Frontend: {"type":"node_end","node_id":"agent_think_0"}

    Runner->>Runner: 执行工具...
    Runner->>Bus: emit(NODE_START, node_id="agent_step_0")

    alt 高风险工具
        Runner->>Bus: emit(INTERRUPT, tool_name="run_shell", risk_level="high")
        Bus->>WS: forward_to_client(event)
        WS->>Frontend: {"type":"interrupt","tool_name":"run_shell",...}
        Note over Frontend: 显示审批弹窗
        Frontend->>WS: 用户点击允许
        WS->>Runner: interrupt_handler.approve(request_id)
    end

    Runner->>Bus: emit(NODE_END)

    alt 发生错误
        Runner->>Bus: emit(ERROR, error="LLM 调用超时")
        Bus->>WS: forward_to_client(event)
        WS->>Frontend: {"type":"error","error":"LLM 调用超时"}
    end
```

**7 种标准事件类型:**

| 事件 | 触发时机 | 携带数据 |
|------|---------|---------|
| `NODE_START` | 节点开始执行 | node_id |
| `NODE_END` | 节点执行结束 | node_id |
| `EDGE_TRAVERSE` | 步骤间跳转 | node_id, state |
| `ERROR` | 发生错误 | node_id, error |
| `STREAM_TOKEN` | 流式输出 token | token 内容 |
| `INTERRUPT` | 高危操作暂停 | tool_name, tool_arguments, risk_level |
| `USER_RESPONSE` | 用户审批响应 | 允许/拒绝 |

---

## 8. 数据库 ER 图

```mermaid
erDiagram
    Conversation ||--o{ Message : contains
    Conversation ||--o{ Task : has
    Task ||--o{ TaskStep : breaks_down_to
    Task ||--o{ Checkpoint : snapshots
    TaskStep ||--o{ AgentExecution : executed_by
    Agent ||--o{ AgentExecution : runs
    Memory ||--o{ Conversation : "persists across"

    Conversation {
        int id PK
        string title
        string status
        datetime created_at
        datetime updated_at
    }

    Message {
        int id PK
        int conversation_id FK
        string role "user/assistant/system/tool"
        text content
        json tool_calls
        json token_usage
        float cost
        string model
        datetime created_at
    }

    Task {
        int id PK
        int conversation_id FK
        string title
        string description
        string status "pending/running/done/failed"
        json plan
        datetime created_at
        datetime updated_at
    }

    TaskStep {
        int id PK
        int task_id FK
        string agent_role
        string description
        string status
        json depends_on
        json result
        int retry_count
        datetime created_at
    }

    Agent {
        int id PK
        string name UK
        string role "researcher/executor/reviewer/designer"
        string system_prompt
        json tools
        datetime created_at
    }

    AgentExecution {
        int id PK
        int agent_id FK
        int task_step_id FK
        string status
        json input
        json output
        json tool_calls
        int prompt_tokens
        int completion_tokens
        int total_tokens
        float cost
        string model
        string error
        datetime started_at
        datetime finished_at
    }

    Checkpoint {
        int id PK
        int task_id FK
        json state "current_step + status + data"
        datetime created_at
    }

    Memory {
        int id PK
        string key UK "如 user_preferences"
        json value
        float importance
        datetime last_accessed
        datetime created_at
    }
```

---

## 9. 完整实例演练

### 场景: 用户问 "帮我分析 docs/ 目录下的 design.md，然后搜一下最新的 Python 3.13 异步特性，最后写一份对比报告"

下面逐步追踪整个流程:

```
═══════════════════════════════════════════════════════════════════
STEP 1: 用户请求到达
═══════════════════════════════════════════════════════════════════

POST /api/chat
{
  "message": "帮我分析 docs/ 目录下的 design.md，然后搜一下最新的
              Python 3.13 异步特性，最后写一份对比报告",
  "model": "deepseek/deepseek-v4-pro"
}

↓ web/routes/chat.py

conversation_id = 1 (新建)
history = []  (首次对话)
llm = LiteLLMClient(model="deepseek/deepseek-v4-pro")
orchestrator = Orchestrator(llm, registry)

═══════════════════════════════════════════════════════════════════
STEP 2: Orchestrator 分析任务
═══════════════════════════════════════════════════════════════════

orchestrator.execute(task) → 单 Agent 模式 (仿 Claude Code)

↓ harness/runner.py

AgentConfig(
    name="agent",
    system_prompt="你是一个 AI Agent。回答简洁直接...",
    model="deepseek/deepseek-v4-pro",
    max_steps=30
)

═══════════════════════════════════════════════════════════════════
STEP 3: 上下文组装
═══════════════════════════════════════════════════════════════════

assemble_messages(task, system_prompt, tool_schemas, history)

组装结果 (发给 LLM 的完整 messages):

[
  {
    role: "system",
    content: """
      你是一个 AI Agent。回答简洁直接，不要啰嗦。
      只有需要实时信息或执行操作时才调工具。

      ## 可用工具
      - read_file: 读取文件内容
      - write_file: 写入内容到文件
      - web_search: 搜索互联网获取最新信息
      - run_shell: 执行 Shell 命令并返回输出
      - grep: 在文件中搜索匹配的文本模式
      ... (共12个工具)
    """
  },
  {
    role: "user",
    content: "帮我分析 docs/ 目录下的 design.md，然后搜一下最新的
              Python 3.13 异步特性，最后写一份对比报告"
  }
]

═══════════════════════════════════════════════════════════════════
STEP 4: Think→Act→Observe→Judge 循环
═══════════════════════════════════════════════════════════════════

--- Round 1 ---

🧠 Think: llm.chat(messages, tools)
   → LLM 决定: "需要先读文件，再搜索"
   → Thought(
       content="我先读取 design.md 文件",
       tool_calls=[
         ToolCall(id="call_1", name="read_file",
                  arguments={"path": "docs/design.md"})
       ]
     )

🔧 Act: registry.execute("read_file", {"path": "docs/design.md"})
   → context/reader.py → 路由到 "plain" 解析器
   → 直接读取文本内容
   → 返回: "## Amor Agent 设计文档\n\n### 架构概述\n..."

👁️ Observe: 工具结果作为 tool 消息追加到 messages
   messages.append({
     role: "tool",
     content: "## Amor Agent 设计文档\n\n### 架构概述\n...",
     tool_call_id: "call_1"
   })

--- Round 2 ---

🧠 Think: llm.chat(messages, tools)
   → LLM 分析文件后决定搜索
   → Thought(
       content="文件已读完，现在搜索 Python 3.13 异步特性",
       tool_calls=[
         ToolCall(id="call_2", name="web_search",
                  arguments={"query": "Python 3.13 异步 asyncio 新特性"})
       ]
     )

🔧 Act: registry.execute("web_search", {"query": "Python 3.13..."})
   → context/web_search.py → Tavily API
   → 返回:
     """
     ### Python 3.13 新特性: 异步相关
     - asyncio.TaskGroup 改进
     - 事件循环性能提升 15%
     ...
     """

👁️ Observe: messages 追加搜索结果

--- Round 3 ---

🧠 Think: llm.chat(messages, tools)
   → LLM 判断: 信息已齐，可以写报告了
   → Thought(
       content="现在将分析结果写入对比报告",
       tool_calls=[
         ToolCall(id="call_3", name="write_file",
                  arguments={
                    "path": "comparison_report.md",
                    "content": "# Amor Agent vs Python 3.13 异步特性对比\n\n..."
                  })
       ]
     )

🔧 Act: registry.execute("write_file", {...})
   → 文件写入成功

--- Round 4 ---

🧠 Think: llm.chat(messages, tools)
   → Thought(
       content="✅ 完成！已读取 design.md，搜索 Python 3.13 异步特性，
                并生成对比报告 comparison_report.md。"
       tool_calls=null  ← 无工具调用！
     )

✅ Judge: thought.tool_calls 为空 → 任务完成
   → AgentResult(
       status="success",
       output="✅ 完成！已读取 design.md...",
       total_tokens=2847
     )

═══════════════════════════════════════════════════════════════════
STEP 5: 结果返回
═══════════════════════════════════════════════════════════════════

orchestrator.execute() 返回:
{
  "task": "帮我分析 docs/ 目录下的 design.md...",
  "mode": "auto",
  "summary": "✅ 完成！已读取 design.md，搜索 Python 3.13 异步特性...",
  "total_tokens": 2847
}

↓ web/routes/chat.py

_save_turn(conv_id=1, user_msg, agent_msg)
→ 内存存储 (生产环境换 PostgreSQL)

HTTP Response:
{
  "conversation_id": 1,
  "content": "✅ 完成！...",
  "mode": "auto",
  "tokens": 2847
}

═══════════════════════════════════════════════════════════════════
实时推送 (WebSocket 并行)
═══════════════════════════════════════════════════════════════════

WebSocket → 前端:
  {"type":"node_start","node_id":"agent_think_0"}
  {"type":"node_end","node_id":"agent_think_0"}
  {"type":"node_start","node_id":"agent_step_0"}
  {"type":"node_end","node_id":"agent_step_0"}
  {"type":"node_start","node_id":"agent_think_1"}
  {"type":"node_end","node_id":"agent_think_1"}
  ...
  {"type":"node_end","node_id":"agent_done"}
```

### 如果用户消息是 "帮我删掉 /etc/hosts"，会发生什么？

```mermaid
flowchart TD
    USER["用户: 帮我删掉 /etc/hosts"] --> THINK["LLM 决定调 run_shell"]
    THINK --> CHECK["Runner 检查 risk_level"]
    CHECK --> HIGH["run_shell: risk_level='high'<br/>requires_approval=true"]
    HIGH --> EMIT["emit INTERRUPT 事件"]
    EMIT --> FRONTEND["前端弹出审批框:<br/>⚠️ 工具: run_shell<br/>命令: rm /etc/hosts<br/>风险等级: high"]
    FRONTEND --> USER_CHOICE{"用户选择?"}
    USER_CHOICE -->|"❌ 拒绝"| REJECT["工具结果: [审批拒绝]<br/>Agent 尝试其他方案"]
    USER_CHOICE -->|"✅ 允许"| EXEC["执行命令 → 返回结果"]
```

---

## 文件索引

| 文件 | 行数 | 职责 |
|------|------|------|
| `amor/config.py` | 47 | Pydantic 配置系统，环境变量读取 |
| `amor/exceptions.py` | 102 | 7 种异常类型的分层体系 |
| `amor/logging.py` | 55 | 结构化日志 + 格式化器 |
| `amor/protocols/llm.py` | 56 | LLM 协议 (Message, Thought, ToolCall) |
| `amor/protocols/memory.py` | 45 | 记忆协议 (MemoryEntry) |
| `amor/protocols/planner.py` | 54 | 规划器协议 (Plan, PlanStep) |
| `amor/protocols/tool.py` | 48 | 工具协议 (ToolSchema, RiskLevel) |
| `amor/events/bus.py` | 37 | 发布/订阅事件总线 |
| `amor/events/types.py` | 40 | 7 种事件类型定义 |
| `llm/client.py` | 117 | LiteLLM 统一接口适配 |
| `context/assembler.py` | 93 | 上下文 9 层组装 |
| `context/reader.py` | 164 | 多格式文件解析器路由器 |
| `context/rag.py` | 87 | ChromaDB + BGE 向量检索 |
| `context/memory_store.py` | 55 | PostgreSQL 持久记忆 |
| `context/window.py` | 43 | Token 估算 + 上下文裁剪 |
| `context/web_search.py` | 18 | Tavily 搜索封装 |
| `harness/runner.py` | 239 | 核心 Think→Act→Observe→Judge 循环 |
| `harness/orchestrator.py` | 340 | 多 Agent 编排 + 审核循环 |
| `harness/planner.py` | 80 | LLM 任务规划器 |
| `harness/tool_registry.py` | 42 | 工具注册/查找/执行 |
| `harness/skills/loader.py` | 87 | .md Skill 文件自动发现 |
| `harness/mcp/client.py` | 87 | MCP 协议外部工具连接 |
| `loop/controller.py` | 47 | 任务循环 + 自动重试 |
| `loop/state.py` | 53 | 检查点保存/恢复 |
| `db/engine.py` | 27 | 异步 PostgreSQL 引擎 |
| `web/app.py` | 100 | FastAPI 启动 + 工具注册 |
| `web/routes/chat.py` | 90 | 对话 API (发送/历史) |
| `web/ws.py` | 32 | WebSocket 实时事件推送 |
