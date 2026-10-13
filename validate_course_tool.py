import json
from typing import Annotated

from pydantic import BaseModel, StringConstraints, ValidationError

# 导入上一步的查询函数；course_tools.py 中的演示不会在导入时运行。
from course_tools import get_course_info


class CourseInfoArgs(BaseModel):
    # course_id 必填，必须是字符串。
    # 先清理首尾空白，再检查至少保留一个字符。
    course_id: Annotated[
        str,
        StringConstraints(
            strict=True,
            strip_whitespace=True,
            min_length=1,
        ),
    ]


def execute_get_course_info(arguments: dict) -> dict:
    # arguments 是原始参数字典，尚未信任其中的数据。
    checked = CourseInfoArgs.model_validate(arguments)

    # 只有上一行校验成功，才会执行课程查询。
    # checked.course_id 已经清理了首尾空白。
    return get_course_info(checked.course_id)


if __name__ == "__main__":
    # 用固定参数观察正常、未找到和校验失败三类结果。
    cases = [
        {"label": "正常编号", "arguments": {"course_id": "C001"}},
        {"label": "编号首尾有空格", "arguments": {"course_id": "  C002  "}},
        {"label": "不存在的编号", "arguments": {"course_id": "C999"}},
        {"label": "只有空格", "arguments": {"course_id": "   "}},
        {"label": "编号是整数", "arguments": {"course_id": 123}},
        {"label": "缺少编号字段", "arguments": {}},
    ]

    for case in cases:
        print("\n场景：", case["label"])

        try:
            result = execute_get_course_info(case["arguments"])
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except ValidationError as error:
            # 处理本轮参数错误，循环可以继续检查下一个场景。
            print("参数校验失败：", error)