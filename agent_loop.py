import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError

# 复用已有的模型请求函数和带白名单/参数校验的调度入口。
from call_tools_live import request_model
from tool_logging import dispatch_tool_with_log as dispatch_tool


def run_agent(client, messages: list, max_steps: int = 4) -> str:
    # max_steps 必须是正整数，限制模型请求轮数。
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError("max_steps 必须是大于0的整数。")

    # range 不包含右端点，因此 +1 让轮数依次为1、2、3、4。
    for step in range(1, max_steps + 1):
        print(f"\n第 {step}/{max_steps} 轮模型请求")

        # 每轮都允许选择工具，收到工具结果后还能继续提出下一次调用。
        response = request_model(client, messages, "auto")
        if not response.choices:
            raise SystemExit("响应异常：没有收到候选回答。")

        choice = response.choices[0]
        message = choice.message
        calls = message.tool_calls or []

        if not calls:
            # 正常回答意味着本次循环结束，返回文本给 main。
            if choice.finish_reason != "stop":
                raise SystemExit(f"回答未正常结束：{choice.finish_reason}")
            if not message.content or not message.content.strip():
                raise SystemExit("响应异常：模型回答为空。")
            return message.content

        if choice.finish_reason != "tool_calls":
            raise SystemExit(f"工具请求未正常结束：{choice.finish_reason}")

        # 最后一轮仍要工具，说明无法在预算内得到最终回答。
        # 此时直接停止，不继续执行新的工具。
        if step == max_steps:
            raise SystemExit(
                f"达到步数上限 {max_steps}，模型仍请求工具，本次停止。"
            )

        if len(calls) > 3:
            raise SystemExit("工具请求过多：每轮最多执行3个工具调用。")
        if any(call.type != "function" for call in calls):
            raise SystemExit("响应异常：本次只支持函数工具。")

        # 把模型的工具请求加入历史，保留每个调用的 id。
        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [call.model_dump() for call in calls],
        })

        for call in calls:
            print("模型选择工具：", call.function.name)
            print("原始参数文本：", call.function.arguments)

            try:
                arguments = json.loads(call.function.arguments)
            except json.JSONDecodeError as error:
                tool_result = {
                    "status": "rejected",
                    "error_type": "invalid_json",
                    "message": str(error),
                }
            else:
                # 未知工具或非法参数也会返回明确的拒绝结果。
                tool_result = dispatch_tool(call.function.name, arguments)

            print("本地执行结果：")
            print(json.dumps(tool_result, ensure_ascii=False, indent=2))

            # 工具结果通过对应 id 回传，下一轮模型能看到完整历史。
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(tool_result, ensure_ascii=False),
            })

        # 本轮工具处理结束，for 自动进入下一轮模型请求。


def main():
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
                "你是使用本地模拟课程库的助手。"
                "查询课程信息、上课时间或总学分时必须使用提供的工具。"
                "用户未给课程编号时先询问，不猜测编号。"
                "组合任务可以分多轮调用工具，收到结果后再决定下一步。"
                "必须区分入口执行完成和业务成功；失败时说明原因。"
                "完成用户要求后用中文汇总，不编造结果。"
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
            answer = run_agent(client, messages, max_steps=4)
            print("\n模型最终回答：", answer)
    except APITimeoutError:
        raise SystemExit("请求超时：请稍后再试。")
    except APIConnectionError:
        raise SystemExit("连接失败：请检查网络或代理设置。")
    except APIStatusError as error:
        raise SystemExit(f"服务返回错误：HTTP {error.status_code}。")


if __name__ == "__main__":
    main()