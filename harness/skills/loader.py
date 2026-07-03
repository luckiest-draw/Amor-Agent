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

# 模块级变量：所有已加载的 Skill
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
    """解析一个 .md 文件，分离 frontmatter 和 Prompt 正文.

    ---
    name: xxx
    description: xxx
    ---
    Prompt 正文
    """
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
