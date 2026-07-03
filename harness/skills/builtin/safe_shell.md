---
name: safe_shell
description: 让 Agent 谨慎使用 Shell 命令
---

执行 Shell 命令前请确认:
1. 优先使用只读命令（ls, cat, grep, find）
2. 写操作（rm, mv, chmod）必须先告知用户你在做什么，等待确认
3. 不理解的命令不要执行，先搜索文档或使用 --help
4. 命令超时（60秒）视为异常，分析原因后再重试
