import json

# 模拟课程数据：列表中每个字典代表一门课程。
# 这些数据仅用于学习，不代表真实学校的课程安排。
COURSES = [
    {
        "course_id": "C001",
        "course_name": "Python 基础",
        "credits": 3,
        "course_category": "专业课",
        "weekday": "周三",
        "period": "下午",
    },
    {
        "course_id": "C002",
        "course_name": "校园安全",
        "credits": 2,
        "course_category": "通识课",
        "weekday": "周五",
        "period": "晚上",
    },
]


def get_course_info(course_id: str) -> dict:
    # 参数 course_id 是本次要查的课程编号。
    # 逐门查看课程，找到编号相同的课程就立即返回。
    for course in COURSES:
        if course["course_id"] == course_id:
            return {
                "found": True,
                # 返回一个字典副本，避免调用者直接修改原课程记录。
                "course": course.copy(),
            }

    # 只有查看完全部课程仍未找到，才会执行这里。
    # 没查到是正常的查询结果，用 False 和 None 表达。
    return {
        "found": False,
        "course": None,
    }


# 直接运行此文件时执行演示；以后被其他文件导入时不执行演示。
if __name__ == "__main__":
    result = get_course_info("C002")
    print("查询 C002：")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    result = get_course_info("C999")
    print("查询 C999：")
    print(json.dumps(result, ensure_ascii=False, indent=2))