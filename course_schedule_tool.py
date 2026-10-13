import json

from pydantic import ValidationError

# 复用已有的课程查询函数和课程编号参数规则。
from course_tools import get_course_info
from validate_course_tool import CourseInfoArgs


def get_course_schedule(course_id: str) -> dict:
    # 先查询课程记录，不再重复写一遍查找循环。
    info = get_course_info(course_id)

    # 找不到课程时，返回明确的“没有上课时间”结果。
    if not info["found"]:
        return {
            "found": False,
            "schedule": None,
        }

    # 已确认找到课程，取出该课程记录。
    course = info["course"]

    # 只返回这个工具需要的编号、星期和时段。
    return {
        "found": True,
        "schedule": {
            "course_id": course["course_id"],
            "weekday": course["weekday"],
            "period": course["period"],
        },
    }


def execute_get_course_schedule(arguments: dict) -> dict:
    # 上课时间查询也需要课程编号，因此复用同一套参数规则。
    checked = CourseInfoArgs.model_validate(arguments)
    return get_course_schedule(checked.course_id)


if __name__ == "__main__":
    cases = [
         {"label": "正常编号", "arguments": {"course_id": "C001"}},
        {"label": "不存在的编号", "arguments": {"course_id": "C999"}},
        {"label": "编号是整数", "arguments": {"course_id": 123}},
    ]

    for case in cases:
        print("\n场景：", case["label"])

        try:
            result = execute_get_course_schedule(case["arguments"])
            print(json.dumps(result, ensure_ascii=False, indent=2))
        except ValidationError as error:
            print("参数校验失败：", error)