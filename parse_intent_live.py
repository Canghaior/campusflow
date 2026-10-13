import json
import os
from pathlib import Path
from typing import Annotated, Literal

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError
from pydantic import BaseModel, Field, StringConstraints, ValidationError


class UserIntent(BaseModel):
    intent: Literal["search_courses"]
    time_range: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1),
    ]
    credits: int = Field(strict=True, gt=0)
    course_category: Literal["通识课", "专业课"]
    requires_approval: bool = Field(strict=True)


env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(env_path, encoding="utf-8-sig")
api_key = os.getenv("LLM_API_KEY", "").strip()

if not api_key or api_key == "replace_with_your_api_key":
    raise SystemExit("配置错误：请在项目 .env 中填写 LLM_API_KEY。")

system_prompt = """
你负责从课程查询请求中提取信息，只返回一个 JSON 对象。
不要输出解释文字或 Markdown 代码块。

字段要求：
- intent：本次课程查询练习固定为 "search_courses"。
- time_range：保留用户提供的时间描述，不能是空字符串。
- credits：用户要求的学分，必须是大于 0 的整数，不能加引号。
- course_category：只能是 "通识课" 或 "专业课"。
- requires_approval：本次只查询课程，不提交申请，固定为 false。
未明确提供的时间、学分或课程类别用 null，禁止猜测。

示例输入：帮我查下周一上午3学分的专业课。
示例 JSON 输出：
{
  "intent": "search_courses",
  "time_range": "下周一上午",
  "credits": 3,
  "course_category": "专业课",
  "requires_approval": false
}
"""

user_request = input("请输入课程查询：").strip()
if not user_request:
    raise SystemExit("输入为空：请输入课程查询后再运行。")

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
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_request},
            ],
            response_format={"type": "json_object"},
            extra_body={"thinking": {"type": "disabled"}},
            max_tokens=512,
            stream=False,
        )

        if not response.choices:
            raise SystemExit("响应异常：没有收到候选回答。")

        choice = response.choices[0]
        if choice.finish_reason != "stop":
            raise SystemExit(
                f"响应未正常结束：{choice.finish_reason}，本次不进行字段校验。"
            )

        reply = choice.message.content
        if not reply or not reply.strip():
            raise SystemExit("响应异常：模型返回了空文本。")

        data = json.loads(reply)
        checked = UserIntent.model_validate(data)
        output = checked.model_dump()
        print(json.dumps(output, ensure_ascii=False, indent=2))

except json.JSONDecodeError as error:
    raise SystemExit(f"JSON 格式错误：{error}")

except ValidationError as error:
    raise SystemExit(f"字段校验失败：{error}")

except APITimeoutError:
    raise SystemExit("请求超时：请稍后再试。")

except APIConnectionError:
    raise SystemExit("连接失败：请检查网络或代理设置。")

except APIStatusError as error:
    raise SystemExit(f"服务返回错误：HTTP {error.status_code}。")