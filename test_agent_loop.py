import json
import unittest
from contextlib import redirect_stdout
from copy import deepcopy
from io import StringIO
from unittest.mock import patch

from openai.types.chat import ChatCompletion

import agent_loop


def make_call(call_id, name, arguments):
    # 构造一条模拟工具请求，arguments 是参数 JSON 文本。
    return {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def make_reply(reason, content=None, calls=None):
    # 生成与 SDK 响应结构一致的对象，不发送 API 请求。
    message = {"role": "assistant", "content": content}
    if calls is not None:
        message["tool_calls"] = calls

    return ChatCompletion.model_validate({
        "id": "offline-response",
        "object": "chat.completion",
        "created": 0,
        "model": "deepseek-flash",
        "choices": [
            {"index": 0, "finish_reason": reason, "message": message},
        ],
    })


class TestAgentLoop(unittest.TestCase):
    def simulate(self, replies, max_steps=4):
        # replies 规定第1、2、3轮分别返回什么。
        pending = iter(replies)
        snapshots = []
        answer = None
        error_message = None

        def fake_request(client, messages, tool_choice):
            # 历史会持续变化，深复制保存“请求当时”的内容。
            snapshots.append(deepcopy(messages))
            return next(pending)

        messages = [
            {"role": "system", "content": "离线测试"},
            {"role": "user", "content": "查询模拟课程"},
        ]

        with (
            # 替换 agent_loop 实际使用的请求函数。
            patch("agent_loop.request_model", side_effect=fake_request) as model,
            # wraps 保留真实调度行为，同时记录调用次数。
            patch("agent_loop.dispatch_tool", wraps=agent_loop.dispatch_tool) as dispatch,
            # 暂时收集打印内容，避免干扰测试报告。
            redirect_stdout(StringIO()),
        ):
            try:
                # client 在模拟请求里不会使用，不创建真实客户端。
                answer = agent_loop.run_agent(object(), messages, max_steps)
            except SystemExit as error:
                error_message = str(error)

        return {
            "answer": answer,
            "error": error_message,
            "model": model,
            "dispatch": dispatch,
            "snapshots": snapshots,
        }

    def test_three_tools_and_history(self):
        # 第一轮两次查询，第二轮算学分，第三轮返回答案。
        replies = [
            make_reply("tool_calls", calls=[
                make_call("info", "get_course_info", '{"course_id":"C001"}'),
                make_call("time", "get_course_schedule", '{"course_id":"C002"}'),
            ]),
            make_reply("tool_calls", calls=[
                make_call("total", "calculate_credit_total", '{"course_ids":["C001","C002"]}'),
            ]),
            make_reply("stop", content="模拟汇总完成。"),
        ]
        result = self.simulate(replies)

        self.assertIsNone(result["error"])
        self.assertEqual(result["answer"], "模拟汇总完成。")
        self.assertEqual(result["model"].call_count, 3)
        self.assertEqual(result["dispatch"].call_count, 3)
        # 每轮都必须允许工具选择，不能提前切换为 none。
        self.assertTrue(all(item.args[2] == "auto" for item in result["model"].call_args_list))

        # 第三轮模型必须能看到前面三条工具结果及正确的调用ID。
        history = result["snapshots"][2]
        self.assertEqual(
            [item["role"] for item in history],
            ["system", "user", "assistant", "tool", "tool", "assistant", "tool"],
        )
        tools = [item for item in history if item["role"] == "tool"]
        self.assertEqual([item["tool_call_id"] for item in tools], ["info", "time", "total"])
        outputs = [json.loads(item["content"]) for item in tools]
        self.assertEqual(outputs[0]["result"]["course"]["credits"], 3)
        self.assertEqual(outputs[1]["result"]["schedule"]["period"], "晚上")
        self.assertEqual(outputs[2]["result"]["total_credits"], 5)

    def test_step_limit(self):
        # 模型连续四轮都要求工具，第四轮不能再执行新工具。
        replies = [
            make_reply("tool_calls", calls=[
                make_call(f"call_{step}", "get_course_info", '{"course_id":"C001"}'),
            ])
            for step in range(1, 5)
        ]
        result = self.simulate(replies)

        self.assertIsNone(result["answer"])
        self.assertIsNotNone(result["error"])
        self.assertIn("达到步数上限 4", result["error"])
        self.assertEqual(result["model"].call_count, 4)
        self.assertEqual(result["dispatch"].call_count, 3)

    def test_answer_on_last_step(self):
        # 第四轮直接回答，应正常结束，不误判为超出上限。
        replies = [
            make_reply("tool_calls", calls=[
                make_call(f"call_{step}", "get_course_info", '{"course_id":"C001"}'),
            ])
            for step in range(1, 4)
        ]
        replies.append(make_reply("stop", content="第四轮完成。"))
        result = self.simulate(replies)

        self.assertIsNone(result["error"])
        self.assertEqual(result["answer"], "第四轮完成。")
        self.assertEqual(result["model"].call_count, 4)

    def test_rejected_tools_then_recovery(self):
        # 未知工具和非法参数反馈给模型，下一轮可提出正确请求。
        replies = [
            make_reply("tool_calls", calls=[
                make_call("unknown", "delete_course", '{}'),
                make_call("bad", "get_course_info", '{"course_id":123}'),
            ]),
            make_reply("tool_calls", calls=[
                make_call("fixed", "get_course_info", '{"course_id":"C001"}'),
            ]),
            make_reply("stop", content="修正后完成。"),
        ]
        result = self.simulate(replies)

        self.assertIsNone(result["error"])
        self.assertEqual(result["answer"], "修正后完成。")
        feedback = result["snapshots"][1]
        self.assertEqual(json.loads(feedback[-2]["content"])["error_type"], "unknown_tool")
        self.assertEqual(json.loads(feedback[-1]["content"])["error_type"], "invalid_arguments")
        fixed = result["snapshots"][2][-1]
        self.assertTrue(json.loads(fixed["content"])["result"]["found"])

    def test_invalid_json_feedback(self):
        # JSON 解析失败时不进入调度，但错误仍要回传给模型。
        replies = [
            make_reply("tool_calls", calls=[
                make_call("broken", "get_course_info", '{"course_id":'),
            ]),
            make_reply("stop", content="参数格式错误。"),
        ]
        result = self.simulate(replies)

        self.assertIsNone(result["error"])
        result["dispatch"].assert_not_called()
        feedback = result["snapshots"][1][-1]
        self.assertEqual(feedback["tool_call_id"], "broken")
        self.assertEqual(json.loads(feedback["content"])["error_type"], "invalid_json")

    def test_truncated_response(self):
        # 响应被截断时，不能执行可能不完整的工具请求。
        replies = [
            make_reply("length", calls=[
                make_call("cut", "get_course_info", '{"course_id":"C001"}'),
            ]),
        ]
        result = self.simulate(replies)

        self.assertIsNotNone(result["error"])
        self.assertIn("工具请求未正常结束", result["error"])
        result["model"].assert_called_once()
        result["dispatch"].assert_not_called()


if __name__ == "__main__":
    unittest.main()