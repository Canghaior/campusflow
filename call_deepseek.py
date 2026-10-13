import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError


# 读取与当前脚本放在同一目录的 .env。
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path, encoding="utf-8-sig")

# 从环境变量读取密钥，不把密钥写进代码。
api_key = os.getenv("LLM_API_KEY", "").strip()
if not api_key or api_key == "replace_with_your_api_key":
    raise SystemExit("配置错误：请在项目 .env 中填写 LLM_API_KEY。")

try:
    with OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",
        timeout=30.0,
        max_retries=0,
    ) as client:
        response = client.chat.completions.create(
            model="deepseek-flash",
            messages=[
                {
                    "role": "system",
                    "content": "请用中文简短回答，不超过50字。",
                },
                {
                    "role": "user",
                    "content": "请用一句话解释：API 是什么？",
                },
            ],
            extra_body={"thinking": {"type": "disabled"}},
            max_tokens=128,
            stream=False,
        )

        if not response.choices:
            raise SystemExit("响应异常：没有收到候选回答。")

        choice = response.choices[0]
        reply = choice.message.content
        if not reply or not reply.strip():
            raise SystemExit("响应异常：模型返回了空文本。")

        print("模型：", response.model)
        print("结束原因：", choice.finish_reason)
        print("模型回复：", reply)

except APITimeoutError:
    raise SystemExit("请求超时：本次没有收到完整回复，请稍后再试。")

except APIConnectionError:
    raise SystemExit("连接失败：请检查网络或代理设置。")

except APIStatusError as error:
    raise SystemExit(
        f"服务返回错误：HTTP {error.status_code}。请把这个状态码发给导师排查。"
    )