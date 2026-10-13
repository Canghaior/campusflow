import json
from typing import Literal
from pydantic import BaseModel, ValidationError


class PeriodInput(BaseModel):
    weekday: Literal["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    period: Literal["上午", "下午", "晚上"]
    course_type: Literal["必修课", "选修课"]


try:
    with open("examples/request.json", encoding="utf-8") as file:
        data = json.load(file)

    checked = PeriodInput.model_validate(data)
    output = checked.model_dump()
    print(json.dumps(output, ensure_ascii=False, indent=2))

except json.JSONDecodeError as error:
    print("JSON 格式错误：", error)

except ValidationError as error:
    print("校验失败：", error)