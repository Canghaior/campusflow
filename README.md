# CampusFlow：课程意图解析与原生工具调用 Agent

CampusFlow 是一个学习 AI Agent 和 LLM 应用开发的项目。

当前包含两个阶段的原型：

- W1：将自然语言课程查询解析为结构化意图，并通过 Pydantic 校验。
- W2：由模型选择工具，本地 Python 校验并执行，将结果回传模型，支持多轮继续和终止。

代码基于导师参考示例完成保存、运行和学习，独立设计与实现能力仍在练习。

## 运行环境

已验证环境为 Windows PowerShell、Python 3.13.5。

依赖版本记录在 `requirements.txt`。

## 首次准备环境

在项目根目录打开 PowerShell：

```powershell
# 创建项目虚拟环境。
python -m venv .venv

# 使用项目环境的 Python 安装依赖。
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

已有可用的 `.venv` 时，无需重复创建。

## 配置 DeepSeek 密钥

在项目根目录创建 `.env`，填写：

```dotenv
LLM_API_KEY=replace_with_your_api_key
```

将占位符替换为自己的 DeepSeek API Key。

程序读取该配置，不在代码中保存真实密钥。
`.env` 已被 Git 忽略；仓库只保留不含真实密钥的 `.env.example`。

非空交互请求会调用真实模型，并按服务商用量计费。
自动测试使用模拟模型回复，不产生模型用量。

## W1：课程查询意图解析

```powershell
# 运行交互式意图解析。
.\.venv\Scripts\python.exe -X utf8 .\parse_intent_live.py
```

示例输入：

```text
帮我查本周五晚上3学分的专业课。
```

预期输出：

```json
{
  "intent": "search_courses",
  "time_range": "本周五晚上",
  "credits": 3,
  "course_category": "专业课",
  "requires_approval": false
}
```

当前字段规则：

| 字段 | 规则 |
| --- | --- |
| intent | 当前查询练习固定为 search_courses |
| time_range | 字符串，清理首尾空白后不能为空 |
| credits | 严格整数，且大于 0 |
| course_category | 通识课或专业课 |
| requires_approval | 严格布尔值；当前查询设为 false |

时间描述仍是文本，尚未转换为具体日期。

空输入不发送模型请求。程序对无效 JSON、字段校验失败、连接失败和超时给出提示。

## W2：原生多工具 Agent

```powershell
# 运行多轮工具调用入口。
.\.venv\Scripts\python.exe -X utf8 .\agent_loop.py
```

`-X utf8` 开启 Python UTF-8 模式。

看到“请输入课程请求”后，每次输入一条请求。

### 本地模拟课程数据

| 编号 | 名称 | 学分 | 类别 | 上课时间 |
| --- | --- | --- | --- | --- |
| C001 | Python 基础 | 3 | 专业课 | 周三下午 |
| C002 | 校园安全 | 2 | 通识课 | 周五晚上 |

### 示例请求与预期结果

| 请求 | 预期数据 |
| --- | --- |
| 查询 C001 的课程名称、学分和类别 | Python 基础、3 学分、专业课 |
| 查询 C001 的上课时间 | 周三下午 |
| 计算 C001 和 C002 的总学分 | 5 学分 |
| 查询 C001 和 C002 的课程信息、上课时间，并计算总学分 | 两门课程的信息和时间，总学分 5 |

模型选择的工具顺序和最终措辞可能不同。

### 工具及执行规则

| 工具 | 用途 |
| --- | --- |
| get_course_info | 根据编号查询课程信息 |
| get_course_schedule | 根据编号查询上课星期和时间段 |
| calculate_credit_total | 根据编号列表计算总学分 |

模型只提出工具名称和参数，实际执行的是本地 Python 程序。

程序检查工具白名单、解析参数 JSON，并使用 Pydantic 校验参数。
未知工具或非法参数被拒绝，拒绝原因作为工具结果回传模型。

每轮执行结果加入消息历史，下一轮模型根据结果决定继续调用工具还是回答。

总学分计算中，重复编号只计一次。
任意课程不存在时，计算失败，不返回部分总数。

### 终止与日志

- `max_steps=4` 限制模型请求轮数。
- 每轮最多处理三个工具调用。
- 第 4 轮给出正常回答时，可以成功结束。
- 第 4 轮仍请求工具时，Python 直接提示停止，不执行这批工具，也不发送第 5 轮请求。
- 网络失败、超时或响应截断等情况按程序规则停止并提示。

工具日志记录名称、调度状态、业务状态和本地调度耗时。

`dispatch_status=completed` 表示调度处理完成，不保证业务成功。

`business_status` 的含义：

- `success`：业务成功。
- `failed`：业务失败，例如课程不存在。
- `not_executed`：请求被拒绝，业务没有执行。

`elapsed_ms` 不包含模型网络请求耗时。

## 自动测试

### W1 测试

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest -v test_intent_cli
```

七个测试方法覆盖正常回复、空输入、缺失字段、非法类型、无效 JSON、连接失败和超时。

正常结果显示 `Ran 7 tests` 和 `OK`。

### W2 循环测试

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest -v test_agent_loop
```

六个测试方法覆盖：

1. 三个工具的执行、消息历史和调用 ID。
2. 步数耗尽时停止新工具执行。
3. 最后一轮正常回答。
4. 未知工具和非法参数反馈后修正。
5. 非法 JSON 的错误回传。
6. 截断响应不执行工具。

正常结果显示 `Ran 6 tests` 和 `OK`。

W1 七项和 W2 六项测试已分别运行通过。

测试模拟模型回复或异常，W2 保留真实本地工具执行。
这些测试不验证真实模型始终选择正确工具，也不测量真实网络故障或模型延迟。

## 主要文件

| 文件 | 用途 |
| --- | --- |
| parse_intent_live.py | W1 交互式意图解析 |
| test_intent_cli.py | W1 自动测试 |
| course_tools.py | 模拟课程数据与课程信息查询 |
| validate_course_tool.py | 课程编号参数校验 |
| course_schedule_tool.py | 上课时间查询 |
| credit_total_tool.py | 总学分计算 |
| tool_dispatcher.py | 工具白名单与调度入口 |
| tool_definitions.py | 提供给模型的工具说明和参数规则 |
| call_tools_live.py | 单批工具调用与结果回传练习 |
| agent_loop.py | 多轮工具调用入口 |
| tool_logging.py | 本地工具调度日志 |
| test_agent_loop.py | W2 循环自动测试 |
| requirements.txt | 依赖版本清单 |

## 当前限制

- 课程数据来自本地模拟记录，尚未接入真实课程系统或数据库。
- 尚未实现校园知识库检索、审批、申请提交和会话持久化。
- 参数校验通过不保证模型理解或工具选择正确。
- 当前循环没有记录 ReAct 论文中的显式推理轨迹，不能称为完整论文复现。

## 学习笔记

- [W1：结构化输出](notes/w1-structured-output.md)
- [W2：工具调用、Agent Loop 与 ReAct](notes/w2-agent-loop.md)