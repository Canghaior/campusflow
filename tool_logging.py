import json
from time import perf_counter

from tool_dispatcher import dispatch_tool


def dispatch_tool_with_log(tool_name, arguments):
    # 记录起点；perf_counter 的差值用于测量一段操作的耗时。
    started = perf_counter()

    # 原调度入口负责白名单、参数校验和本地执行。
    result = dispatch_tool(tool_name, arguments)

    # 秒转为毫秒。这里只测调度耗时，不包含模型网络请求。
    elapsed_ms = (perf_counter() - started) * 1000

    # 区分“入口处理完成”和“业务结果成功”。
    if result["status"] == "rejected":
        business_status = "not_executed"
    else:
        data = result["result"]
        if data.get("found") is False or data.get("success") is False:
            business_status = "failed"
        else:
            business_status = "success"

    log_entry = {
        "event": "tool_dispatch",
        "tool_name": tool_name if isinstance(tool_name, str) else "<非字符串>",
        "dispatch_status": result["status"],
        "business_status": business_status,
        "elapsed_ms": round(elapsed_ms, 3),
    }

    # 每次处理打印一条日志，便于定位具体工具及状态。
    print("[工具日志]", json.dumps(log_entry, ensure_ascii=False))

    # 原结果直接返回，日志没有改变提供给循环/模型的数据。
    return result


if __name__ == "__main__":
    # 四个本地案例，不调用模型，也不读取密钥。
    cases = [
        {"name": "get_course_info", "arguments": {"course_id": "C001"}},
        {"name": "calculate_credit_total", "arguments": {"course_ids": ["C001", "C999"]}},
        {"name": "delete_course", "arguments": {"course_id": "C001"}},
        {"name": "get_course_info", "arguments": {"course_id": 123}},
    ]

    for case in cases:
        print("\n请求工具：", case["name"])
        result = dispatch_tool_with_log(case["name"], case["arguments"])
        print("原始执行结果：")
        print(json.dumps(result, ensure_ascii=False, indent=2))