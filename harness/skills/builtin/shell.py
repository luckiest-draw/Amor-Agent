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