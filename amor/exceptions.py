"""Amor 框架自定义异常体系.

所有异常继承 AmorError，可按粒度精确捕获：
    try:
        ...
    except LLMError:
        # 处理 LLM 相关错误
    except GraphError:
        # 处理图执行错误
"""

from __future__ import annotations
from typing import Any

from sympy.codegen.ast import none


class AmorError(RuntimeError):
    """Amor 框架所有异常的基类"""

# ── 配置异常 ─────────────────────────────────────

class ConfigurationError(AmorError):
    """配置相关错误"""

# ── 图引擎异常 ────────────────────────────────────

class GraphError(AmorError):
    """图引擎相关异常基类"""

class InvalidGraphError(GraphError):
    """图结构不合法 —— 缺少入口、孤立节点等"""

class NodeExecutionError(GraphError):
    """节点执行失败，携带节点上下文"""

    def __init__(
        self,
        node_id: str,
        step: int,
        cause: BaseException | None = None,
    ) -> None:
        super().__init__(f"Node '{node_id}' failed at step {step}")
        self.node_id = node_id
        self.step = step
        if cause is not None:
            self.__cause__ = cause


class MaxStepsExceededError(GraphError):
    """图执行超过最大步数限制"""

    def __init__(self,max_steps: int,current_steps: int) -> None :
        super().__init__(
            f"Graph exceeded max steps:{current_steps} > {max_steps}"
        )
        self.max_steps = max_steps
        self.current_steps = current_steps


# ── 协议层异常 ────────────────────────────────────
class ProtocolError(AmorError):
    """协议层异常基类"""

class LLMError(ProtocolError):
    """LLM调用失败"""

    def __init__(self, message: str,cause: BaseException | None = None) -> None:
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause


class ToolExecutionError(ProtocolError):
    """工具执行失败"""

    def __init__(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        cause: BaseException | None = None
    ) -> None:
        super().__init__(f"Tool '{tool_name}' execution failed with args:{arguments}")
        self.tool_name = tool_name
        self.arguments = arguments
        if cause is not None:
            self.__cause__ = cause


# ── DI 容器异常 ───────────────────────────────────
class DIContainerError(AmorError):
    """DI 容器异常基类"""

class BindingNotFoundError(DIContainerError):
    """请求的依赖类型未在容器中注册"""

    def __init__(self,protocol_type: str) -> None:
        super().__init__(
            f"No binding found for '{protocol_type}'"
            f"Register it with: container.bind({protocol_type},implementation"
        )
        self.protocol_type = protocol_type