# Amor Agent

轻量但专业的四层 AI Agent 系统。遵循 **Prompt → Context → Harness → Loop** 四层 Agent 工程架构，带 Web UI。

## 特性

- **多 Agent 协作** — Orchestrator 调度，研究员/执行者/审核员/设计师分工
- **RAG 知识检索** — MarkItDown 文件解析 + ChromaDB 向量检索
- **网页搜索** — Tavily 驱动，Agent 主动搜索实时信息
- **图片生成** — DALL-E API 集成
- **MCP 协议** — 连接外部 MCP Server，自动映射为本地工具
- **自定义 Skill** — Markdown 文件即 Skill，丢进 `skills/user/` 就能用（兼容 Claude Code 格式）
- **多模型切换** — LiteLLM 驱动，Web UI 一键切 OpenAI / Gemini / DeepSeek
- **中断审批** — 高危操作（如 rm）弹出确认框，等人决策
- **Token 统计** — 实时显示消耗量
- **Web UI** — Vue 3 + Element Plus

## 架构

```
┌──────────────────────────┐
│        Web UI             │
├──────────────────────────┤
│  Loop: 自主持续运行        │
│  Harness: 多 Agent 编排    │
│  Context: 文件+记忆+RAG+搜索│
│  Prompt: 系统角色+模板      │
├──────────────────────────┤
│  Infrastructure: 异常|日志|配置|协议|DI|事件│
├──────────────────────────┤
│  Data: PostgreSQL + ChromaDB               │
└──────────────────────────┘
```

## 快速开始

### 1. 安装

```bash
git clone https://github.com/luckiest-draw/Amor-Agent.git
cd Amor-Agent
pip install -e .
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
├── amor/        基础设施（异常、日志、配置、协议、DI、事件）
├── prompt/      Layer 1: 系统提示词 + 角色模板
├── context/     Layer 2: 文件解析 + 记忆 + RAG + 搜索
├── harness/     Layer 3: 多 Agent 编排 + 工具 + MCP + Skill
├── loop/        Layer 4: 自主循环 + 状态持久化
├── web/         FastAPI 后端 + Vue 3 前端
├── db/          PostgreSQL 模型
├── llm/         LiteLLM 封装
└── tests/
```

## License

MIT
