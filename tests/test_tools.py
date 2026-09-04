"""Agent 工具集测试：覆盖参数校验与兜底路径（不依赖 LLM/数据库）"""
from agent.tools import TOOL_DEFS, execute_tool


def test_tool_defs_shape():
    assert len(TOOL_DEFS) == 3
    for t in TOOL_DEFS:
        assert t["type"] == "function"
        assert "parameters" in t["function"]


def test_query_metric_rejects_unknown_metric():
    out = execute_tool("query_metric", {"metric": "not_exist"})
    assert "未知指标" in out


def test_unknown_tool_returns_text():
    assert execute_tool("no_such_tool", {}) == "未知工具: no_such_tool"


def test_tool_errors_are_caught():
    """工具内全兜底：参数类型错误也返回文本而非抛出"""
    out = execute_tool("query_hot_products", {"top_n": "abc"})
    assert out.startswith("工具执行失败")
