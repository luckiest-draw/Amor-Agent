"""Skill 数据类 — 从 .md 文件解析出来的内部表示."""

from dataclasses import dataclass, field


@dataclass
class Skill:
    """一条 Skill = frontmatter 元数据 + Prompt 正文."""

    name: str = ""
    description: str = ""
    source_file: str = ""       # 来自哪个 .md 文件
    prompt: str = ""            # frontmatter 下面那段 Prompt
