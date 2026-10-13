import json

from pydantic import ValidationError

# 注册的是带参数校验的执行入口。
from validate_course_tool import execute_get_course_info
from course_schedule_tool import execute_get_course_schedule
from credit_total_tool import execute_calculate_credit_total


# 工具名称 -> 执行函数。
# 函数名后面没有括号：这里只保存函数，不执行它。
TOOL_HANDLERS = {
    "get_course_info": execute_get_course_info,
    "get_course_schedule": execute_get_course_schedule,
    "calculate_credit_total": execute_calculate_credit_total,
}


def dispatch_tool(tool_name: str, arguments: dict) -> dict:
    # 类型提示本身不会检查输入，因此入口显式检查名称类型。
    if not isinstance(tool_name, str):
        return {
            "status": "rejected",
            "error_type": "invalid_tool_name",
            "message": "工具名称必须是字符串。",
        }

    # get 在名称不存在时返回 None，避免直接取字典键时报 KeyError。
    handler = TOOL_HANDLERS.get(tool_name)

    # 这个注册表也是白名单：只允许调用已登记的工具。
    if handler is None:
        return {
            "status": "rejected",
            "error_type": "unknown_tool",
            "message": f"未注册的工具：{tool_name}",
        }

    if not isinstance(arguments, dict):
        return {
            "status": "rejected",
            "error_type": "invalid_arguments",
            "message": "工具参数必须是字典。",
        }

    try:
        # 现在才调用函数。函数内部先校验参数，再执行业务操作。
        result = handler(arguments)
    except ValidationError as error:
        return {
            "status": "rejected",
            "error_type": "invalid_arguments",
            "message": str(error),
        }

    # completed 表示工具返回了结果；业务是否成功还需查看 result。
    return {
        "status": "completed",
        "tool_name": tool_name,
        "result": result,
    }


if __name__ == "__main__":
    requests = [
        {"name": "get_course_info", "arguments": {"course_id": "C001"}},
        {"name": "get_course_schedule", "arguments": {"course_id": "C002"}},
        {"name": "calculate_credit_total", "arguments": {"course_ids": ["C001", "C002"]}},
        {"name": "delete_course", "arguments": {"course_id": "C001"}},
        {"name": "get_course_info", "arguments": {"course_id": 123}},
        {"name": "calculate_credit_total", "arguments": {"course_ids": ["C001", "C999"]}},
    ]

    for request in requests:
        print("\n调用工具：", request["name"])
        result = dispatch_tool(request["name"], request["arguments"])
        print(json.dumps(result, ensure_ascii=False, indent=2))