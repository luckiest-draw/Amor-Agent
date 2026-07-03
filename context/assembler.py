"""上下文组装器 — 把零散信息拼成发给 LLM 的完整 messages."""

from amor.protocols.llm import Message
from amor.protocols.tool import ToolSchema
from context.memory_store import PostgresMemory

async def assemble_messages(
    task: str,
    system_prompt: str,
    role_prompt: str = "",
    file_paths: list[str] | None = None,
    rag_query_text: str | None = None,
    search_query: str | None = None,
    memory: PostgresMemory | None = None,
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

    # Skill Prompt 注入（Claude Code 风格）
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