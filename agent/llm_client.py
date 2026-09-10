"""LLM API 封装 + 手写 Agent 循环（④ AI 层核心）

接入 DeepSeek（OpenAI 兼容接口），换模型只需改 config/settings.yaml，
业务代码零改动。

设计要点:
- Agent 的本质 = LLM + 工具调用循环：
  模型决定调什么工具 -> 我们执行 -> 结果喂回去 -> 直到模型不再要求调工具
- 循环终止条件: 模型不再返回 tool_calls
- 最大轮数上限: 防止模型无限循环（工程防御）
"""
import json
import os

from openai import OpenAI

from database.db import load_config
from utils.logger import get_logger

logger = get_logger("agent")

MAX_TURNS = 8


def get_client() -> OpenAI:
    """创建 DeepSeek 客户端（key 从环境变量读取，绝不硬编码）"""
    cfg = load_config()["llm"]
    key = os.environ.get(cfg["api_key_env"])
    if not key:
        raise RuntimeError(
            f"未找到 API key。请先到 platform.deepseek.com 创建 key，然后设置环境变量 "
            f"{cfg['api_key_env']}:\n"
            f"  CMD（永久生效）: setx {cfg['api_key_env']} \"sk-你的key\"  然后重开终端\n"
            f"  当前会话临时:    set {cfg['api_key_env']}=sk-你的key"
        )
    return OpenAI(api_key=key, base_url=cfg["base_url"])


def run_agent(system: str, tools: list, user_message: str, max_turns: int = MAX_TURNS) -> str:
    """手写 Agent 循环：模型决定工具 -> 执行 -> 结果喂回 -> 直到模型结束"""
    from agent.tools import execute_tool

    cfg = load_config()["llm"]
    client = get_client()
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message},
    ]

    for turn in range(max_turns):
        response = client.chat.completions.create(
            model=cfg["model"],
            messages=messages,
            tools=tools,
            max_tokens=4096,
        )
        msg = response.choices[0].message

        if not msg.tool_calls:  # 模型不再要求调工具 = 循环结束
            return msg.content or "（模型返回为空）"

        # 把 assistant 消息原样回填（OpenAI 协议要求 tool_calls 必须完整回传）
        messages.append({"role": "assistant", "content": msg.content,
                         "tool_calls": msg.tool_calls})
        for tc in msg.tool_calls:
            args = json.loads(tc.function.arguments or "{}")
            logger.info("🔧 Agent 调用工具: %s(%s)", tc.function.name, args)
            result = execute_tool(tc.function.name, args)
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})

    return "（达到最大工具调用轮数，Agent 提前终止）"
