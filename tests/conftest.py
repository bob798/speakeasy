"""
conftest.py — 全局 pytest 配置

测试分类：
  unit  — 不需要运行中的服务器，使用 TestClient / mock
  e2e   — 需要运行中的服务器（uvicorn app），使用 Playwright

运行方式：
  pytest tests/ -v                         # 仅运行 unit 测试
  pytest tests/ -v -m e2e --base-url http://localhost:8000   # 仅运行 e2e
  pytest tests/ -v -m "unit or e2e"        # 全部
"""
import pytest
import requests

BASE_URL = "http://localhost:8000"


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: 需要 live server 的端到端测试")
    config.addinivalue_line("markers", "unit: 不需要 live server 的单元/集成测试")


def pytest_collection_modifyitems(config, items):
    """e2e 测试文件自动打 e2e 标记，其余自动打 unit 标记"""
    for item in items:
        if "e2e" in item.fspath.basename:
            item.add_marker(pytest.mark.e2e)
        else:
            item.add_marker(pytest.mark.unit)


def pytest_runtest_setup(item):
    """e2e 测试运行前检查服务器是否在线，不在线则 skip"""
    if "e2e" in item.fspath.basename:
        try:
            requests.get(BASE_URL, timeout=2)
        except Exception:
            pytest.skip(f"e2e 测试需要服务器在线：{BASE_URL}")
