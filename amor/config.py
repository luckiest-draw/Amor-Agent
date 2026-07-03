"""Amor 框架配置系统.

配置优先级（从低到高）：
    1. 代码默认值
    2. .env 文件（项目根目录）
    3. AMOR_ 前缀环境变量
    4. 构造函数显式传参

使用：
    config = AmorConfig()
    print(config.max_graph_steps)  # 100
"""

from __future__ import annotations
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings,SettingsConfigDict

class AmorConfig(BaseSettings):
    """Amor 框架全局配置"""

    model_config = SettingsConfigDict(
        env_prefix="AMOR_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="forbid",
    )

    log_level: Literal["DEBUG","INFO","WARNING","ERROR"] = Field(
        default="INFO",
        description="日志级别",
    )
    max_graph_steps: int = Field(
        default= 100,
        gt=0,
        description="图执行最大步数，防止无限循环",
    )
    llm_timeout_seconds: float = Field(
        default= 60.0,
        gt= 0,
        description="LLM 调用超时(秒)",
    )

    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/amor",
        description="PostgreSQL 连接字符串",
    )