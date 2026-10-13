import json
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints, ValidationError

from course_tools import get_course_info


# 为“合法课程编号”起一个类型名称，方便放进列表规则。
CourseId = Annotated[
    str,
    StringConstraints(strict=True, strip_whitespace=True, min_length=1),
]


class CreditTotalArgs(BaseModel):
    # 必须传入列表，列表至少有一个编号。
    # CourseId 的规则会分别检查列表里的每一个元素。
    course_ids: list[CourseId] = Field(strict=True, min_length=1)


def calculate_credit_total(course_ids: list[str]) -> dict:
    total_credits = 0
    counted_ids = []

    for course_id in course_ids:
        # 已经计算过的课程跳过，防止重复计入学分。
        if course_id in counted_ids:
            continue

        info = get_course_info(course_id)

        # 有任何一门课不存在，本次计算失败，不返回部分总数。
        if not info["found"]:
            return {
                "success": False,
                "total_credits": None,
                "error": f"课程不存在：{course_id}",
            }

        # 把当前课程学分加到累计值，再记录已计算的编号。
        total_credits += info["course"]["credits"]
        counted_ids.append(course_id)

    return {
        "success": True,
        "course_ids": counted_ids,
        "total_credits": total_credits,
    }


def execute_calculate_credit_total(arguments: dict) -> dict:
    # 先检查整个列表及每个编号，再开始查询和计算。
    checked = CreditTotalArgs.model_validate(arguments)
    return calculate_credit_total(checked.course_ids)


if __name__ == "__main__":
    cases = [
        {
            "label": "只计算校园安全",
            "arguments": {"course_ids": ["C002"]},
        },
        {
            "label": "包含重复课程",
            "arguments": {"course_ids": ["C001", "C001", "C002"]},
        },
        {
            "label": "包含不存在的课程",
            "arguments": {"course_ids": ["C001", "C999"]},
        },
        {
            "label": "空列表",
            "arguments": {"course_ids": []},
        },
        {
            "label": "列表里有整数",
            "arguments": {"course_ids": ["C001", 123]},
        },
        {
            "label": "列表里有纯空格",
            "arguments": {"course_ids": ["C001", "   "]},
        },
    ]

    for case in cases:
        print("\n场景：", case["label"])

        try:
            result = execute_calculate_credit_total(case["arguments"])
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except ValidationError as error:
            print("参数校验失败：", error)