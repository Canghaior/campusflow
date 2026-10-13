import json
import os
import runpy
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx2
from openai import APIConnectionError, APITimeoutError


SCRIPT_PATH = Path(__file__).resolve().parent / "parse_intent_live.py"
USER_REQUEST = "帮我查本周五晚上3学分的专业课。"
VALID_INTENT = {
    "intent": "search_courses",
    "time_range": "本周五晚上",
    "credits": 3,
    "course_category": "专业课",
    "requires_approval": False,
}


class TestIntentCLI(unittest.TestCase):
    def run_cli(self, reply=None, simulated_error=None, user_request=USER_REQUEST):
        if reply is None:
            reply = json.dumps(VALID_INTENT, ensure_ascii=False)

        output = StringIO()
        exit_message = None

        with (
            patch.dict(os.environ, {"LLM_API_KEY": "offline-test-key"}),
            patch("dotenv.load_dotenv"),
            patch("builtins.input", return_value=user_request),
            patch("openai.OpenAI") as mock_openai,
            redirect_stdout(output),
        ):
            client = mock_openai.return_value.__enter__.return_value
            create = client.chat.completions.create

            create.return_value = SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(content=reply),
                    )
                ]
            )
            create.side_effect = simulated_error

            try:
                runpy.run_path(str(SCRIPT_PATH), run_name="__main__")
            except SystemExit as error:
                exit_message = str(error)

        return output.getvalue(), exit_message, create

    def assert_failure(self, reply=None, simulated_error=None):
        output, message, create = self.run_cli(reply, simulated_error)
        self.assertEqual(output, "")
        self.assertIsNotNone(message)
        create.assert_called_once()
        return message

    def test_normal_response(self):
        output, message, create = self.run_cli()
        self.assertIsNone(message)
        self.assertEqual(json.loads(output), VALID_INTENT)
        create.assert_called_once()
        sent_request = create.call_args.kwargs["messages"][1]["content"]
        self.assertEqual(sent_request, USER_REQUEST)

    def test_empty_input(self):
        for value in ("", "   "):
            with self.subTest(user_request=value):
                output, message, create = self.run_cli(user_request=value)
                self.assertEqual(output, "")
                self.assertEqual(message, "输入为空：请输入课程查询后再运行。")
                create.assert_not_called()

    def test_missing_credits(self):
        data = VALID_INTENT.copy()
        del data["credits"]
        message = self.assert_failure(reply=json.dumps(data, ensure_ascii=False))
        self.assertIn("字段校验失败：", message)
        self.assertIn("credits", message)
        self.assertIn("type=missing", message)

    def test_invalid_credit_type(self):
        data = VALID_INTENT.copy()
        data["credits"] = "3"
        message = self.assert_failure(reply=json.dumps(data, ensure_ascii=False))
        self.assertIn("字段校验失败：", message)
        self.assertIn("credits", message)
        self.assertIn("type=int_type", message)

    def test_invalid_json(self):
        message = self.assert_failure(reply='{"intent": "search_courses",}')
        self.assertTrue(message.startswith("JSON 格式错误："))

    def test_connection_error(self):
        request = httpx2.Request("POST", "https://api.deepseek.com/chat/completions")
        message = self.assert_failure(
            simulated_error=APIConnectionError(request=request)
        )
        self.assertEqual(message, "连接失败：请检查网络或代理设置。")

    def test_timeout_error(self):
        request = httpx2.Request("POST", "https://api.deepseek.com/chat/completions")
        message = self.assert_failure(
            simulated_error=APITimeoutError(request=request)
        )
        self.assertEqual(message, "请求超时：请稍后再试。")


if __name__ == "__main__":
    unittest.main()