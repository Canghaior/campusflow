import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError

from tool_definitions import TOOL_DEFINITIONS
from tool_dispatcher import dispatch_tool


def request_model(client, messages: list, tool_choice: str):
    # 第一次允许模型选择工具；第二次关闭工具选择，只生成最终回答。
    return client.chat.completions.create(
        model="deepseek-flash",
        messages=messages,
        tools=TOOL_DEFINITIONS,
        tool_choice=tool_choice,
        extra_body={"thinking": {"type": "disabled"}},
        max_tokens=1024,
        stream=False,
    )


def main():
    # 沿用项目已有配置，不在代码中填写密钥。
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path, encoding="utf-8-sig")
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key or api_key == "replace_with_your_api_key":
        raise SystemExit("配置错误：请在项目 .env 中填写 LLM_API_KEY。")

    user_request = input("请输入课程请求：").strip()
    if not user_request:
        raise SystemExit("输入为空：请输入课程请求后再运行。")

    messages = [
        {
            "role": "system",
            "content": (
                "你是课程查询助手，数据来自本地模拟课程库。"
                "查询课程信息、上课时间或总学分时使用提供的工具。"
                "用户必须明确提供课程编号；缺少编号时询问用户，不猜测。"
                "工具返回后，根据结果用中文回答，不编造课程或学分。"
                "如果工具拒绝请求或业务失败，说明原因，不当作查询成功。"
            ),
        },
        {"role": "user", "content": user_request},
    ]

    try:
        with OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=30.0,
            max_retries=0,
        ) as client:
            # 请求一：让模型决定是否需要工具，以及工具名称和参数。
            first = request_model(client, messages, "auto")
            if not first.choices:
                raise SystemExit("响应异常：没有收到候选回答。")

            choice = first.choices[0]
            message = choice.message
            calls = message.tool_calls or []

            if not calls:
                # 模型可能直接询问缺少的编号，这时没有工具需要执行。
                if choice.finish_reason != "stop" or not message.content or not message.content.strip():
                    raise SystemExit("响应异常：没有收到正常回答或工具调用。")
                print("模型回答：", message.content)
                return

            if choice.finish_reason != "tool_calls":
                raise SystemExit(f"工具请求未正常结束：{choice.finish_reason}")
            if len(calls) > 3:
                raise SystemExit("工具请求过多：本次最多执行3个工具调用。")
            if any(call.type != "function" for call in calls):
                raise SystemExit("响应异常：本次只支持函数工具。")

            # 先保存模型提出工具调用的消息，才能接着添加工具结果。
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [call.model_dump() for call in calls],
            })

            for call in calls:
                print("\n模型选择工具：", call.function.name)
                print("原始参数文本：", call.function.arguments)

                try:
                    # 工具参数是 JSON 字符串，先解析成 Python 数据。
                    arguments = json.loads(call.function.arguments)
                except json.JSONDecodeError as error:
                    tool_result = {
                        "status": "rejected",
                        "error_type": "invalid_json",
                        "message": str(error),
                    }
                else:
                    # 调度入口检查白名单和参数，再执行本地函数。
                    tool_result = dispatch_tool(call.function.name, arguments)

                print("本地执行结果：")
                print(json.dumps(tool_result, ensure_ascii=False, indent=2))

                # id 将这条结果与模型提出的那次工具调用对应起来。
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })

            # 请求二：发送包括工具结果在内的历史，让模型组织最终回答。
            final = request_model(client, messages, "none")
            if not final.choices:
                raise SystemExit("响应异常：没有收到最终回答。")

            final_choice = final.choices[0]
            if final_choice.finish_reason != "stop":
                raise SystemExit(f"最终回答未正常结束：{final_choice.finish_reason}")
            if final_choice.message.tool_calls:
                raise SystemExit("响应异常：最终回答阶段仍请求了工具。")
            if not final_choice.message.content or not final_choice.message.content.strip():
                raise SystemExit("响应异常：最终回答为空。")

            print("\n模型最终回答：", final_choice.message.content)

    except APITimeoutError:
        raise SystemExit("请求超时：请稍后再试。")
    except APIConnectionError:
        raise SystemExit("连接失败：请检查网络或代理设置。")
    except APIStatusError as error:
        raise SystemExit(f"服务返回错误：HTTP {error.status_code}。")


if __name__ == "__main__":
    main()