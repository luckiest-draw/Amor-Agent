"""Tests for Amor configuration."""

import os
import pytest
from mcp.server.fastmcp.exceptions import ValidationError

from amor.config import AmorConfig


def test_config_defaults():
    """默认配置值"""
    config = AmorConfig()
    assert config.log_level == "INFO"
    assert config.max_graph_steps == 100
    assert config.llm_timeout_seconds == 60.0

def test_config_from_env(monkeypatch):
    """环境变量覆盖默认值"""
    monkeypatch.setenv("AMOR_LOG_LEVEL","DEBUG")
    monkeypatch.setenv("AMOR_MAX_GRAPH_STEPS","50")

    config = AmorConfig()
    assert config.log_level == "DEBUG"
    assert config.max_graph_steps == 50

def test_config_max_steps_must_be_positive():
    """max_graph_steps 必须 > 0"""
    config = AmorConfig(max_graph_steps=10)
    assert config.max_graph_steps == 10

    with pytest.raises(Exception):  #pydantic ValidationError
        AmorConfig(max_graph_steps=0)


def test_config_log_level_validation():
    """log_level 必须是有效值"""
    config = AmorConfig(log_level="ERROR")
    assert config.log_level == "ERROR"

    with pytest.raises(Exception):
        AmorConfig(log_level="INVALID")