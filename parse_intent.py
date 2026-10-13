import json
from typing import Annotated, Literal
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


mock_response = """
{
  "intent": "search_courses",
  "time_range": "下周三下午",
  "credits": 2,
  "course_category": "通识课",
  "requires_approval": false
}
"""


try:
    data = json.loads(mock_response)
    checked = UserIntent.model_validate(data)
    output = checked.model_dump()
    print(json.dumps(output, ensure_ascii=False, indent=2))

except json.JSONDecodeError as error:
    print("JSON 格式错误：", error)

except ValidationError as error:
    print("校验失败：", error)