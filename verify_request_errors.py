import os
import runpy
from pathlib import Path
from unittest.mock import patch

import httpx2
from openai import APIConnectionError, APITimeoutError


script_path = Path(__file__).resolve().parent / "parse_intent_live.py"


def check_case(name, simulated_error, expected_message):
    with (
        patch.dict(os.environ, {"LLM_API_KEY": "offline-test-key"}),
        patch("dotenv.load_dotenv"),
        patch(
            "builtins.input",
            return_value="帮我查本周五晚上3学分的专业课。",
        ),
        patch("openai.OpenAI") as mock_openai,
    ):
        # 用模拟客户端替代真实客户端。
        client = mock_openai.return_value.__enter__.return_value
        create = client.chat.completions.create

        # 一旦代码尝试请求，就抛出指定异常。
        create.side_effect = simulated_error

        try:
            runpy.run_path(str(script_path), run_name="__main__")
        except SystemExit as error:
            if str(error) != expected_message:
                raise AssertionError(
                    f"{name}提示不符：预期 {expected_message!r}，实际 {str(error)!r}"
                )
            create.assert_called_once()
            print(f"通过：{name} → {error}")
        else:
            raise AssertionError(f"{name}未按预期提示并退出。")


# 创建请求信息对象供异常使用；这里不发送网络请求。
request = httpx2.Request("POST", "https://api.deepseek.com/chat/completions")

check_case(
    "网络失败",
    APIConnectionError(request=request),
    "连接失败：请检查网络或代理设置。",
)
check_case(
    "请求超时",
    APITimeoutError(request=request),
    "请求超时：请稍后再试。",
)

print("全部通过：2 个模拟异常场景。")