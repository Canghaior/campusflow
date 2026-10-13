import json

from validate_course_tool import CourseInfoArgs
from credit_total_tool import CreditTotalArgs


# 这是准备发送给模型的工具说明，里面都是可序列化的数据。
# 工具名称必须与 tool_dispatcher.py 的 TOOL_HANDLERS 键一致。
TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_course_info",
            "description": "根据课程编号查询课程名称、学分和类别等信息。",
            # 导出参数规则字典，不是查询某一门课程。
            "parameters": CourseInfoArgs.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_course_schedule",
            "description": "根据课程编号查询每周上课的星期和时段。",
            "parameters": CourseInfoArgs.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_credit_total",
            "description": (
                "根据课程编号列表计算总学分。重复编号只计一次；"
                "任意课程不存在时计算失败，不返回部分总数。"
            ),
            "parameters": CreditTotalArgs.model_json_schema(),
        },
    },
]


if __name__ == "__main__":
    # 打印说明供学习观察，不调用模型，也不执行课程查询。
    print(json.dumps(TOOL_DEFINITIONS, ensure_ascii=False, indent=2))