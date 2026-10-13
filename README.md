# CampusFlow：课程查询意图解析原型

CampusFlow 是一个学习 AI Agent 和 LLM 应用开发的项目。

当前 W1 原型支持：在终端输入课程查询请求，调用 DeepSeek 提取结构化意图，再通过 Pydantic 校验并输出 JSON。

## 当前功能

- 在终端输入课程查询。

- 调用 DeepSeek 的 `deepseek-flash` 模型，使用非思考模式。

- 要求模型返回 JSON。

- 校验必填字段、字段类型和允许值。

- 空输入时提示退出，不发送模型请求。

- 对无效 JSON、字段校验失败、连接失败和超时给出提示。

- 提供 7 个使用模拟回复或异常的自动测试。

当前只解析查询意图，尚未实现课程数据库查询、申请提交或完整 Agent 工作流。

## 已验证环境

- Windows PowerShell

- Python 3.13.5

- 包版本记录在 `requirements.txt`

## 首次准备新环境

在项目根目录打开 PowerShell，确认已经安装 Python。

```powershell

# 创建项目虚拟环境。

python -m venv .venv

# 使用项目环境的 Python，按清单安装依赖。

.\.venv\Scripts\python.exe -m pip install -r requirements.txt

```

如果项目已经有可用的 `.venv`，无需重复创建。

## 配置 DeepSeek 密钥

在项目根目录打开或创建 `.env`：

```powershell

notepad .\.env

```

填写：

```dotenv

LLM_API_KEY=replace_with_your_api_key

```

把等号右侧的占位符替换为自己的真实 DeepSeek API Key。

程序通过 `python-dotenv` 将配置载入环境变量，再通过 `os.getenv()` 读取密钥。

`.env` 已被 Git 忽略，不应提交真实密钥。

`.env.example` 保留占位符，用于展示配置格式。

## 运行课程意图解析

```powershell

.\.venv\Scripts\python.exe .\parse_intent_live.py

```

看到输入提示后，输入：

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

每次运行处理一条查询。非空查询会调用真实模型，并按服务商用量计费。

## 字段规则

| 字段 | 当前规则 |
| --- | --- |
| intent | 当前查询练习固定为 search_courses |
| time_range | 字符串；清理首尾空白后不能为空 |
| credits | 严格整数，且大于 0 |
| course_category | 通识课或专业课 |
| requires_approval | 严格布尔值；当前只查询，设为 false |

这些规则用于当前学习原型。

时间描述保留为文本，尚未转换成具体日期或检查课表。

## 运行自动测试

```powershell

.\.venv\Scripts\python.exe -m unittest -v test_intent_cli

```

当前 7 个测试方法覆盖：

1. 正常回复及发送的用户请求。

2. 空输入和纯空格输入不触发请求。

3. 缺少必填学分字段。

4. 学分类型错误。

5. 无效 JSON。

6. 连接失败异常。

7. 超时异常。

正常结果会显示每项 `ok`，最后显示 `Ran 7 tests` 和 `OK`。

测试用模拟客户端替换真实客户端，不读取真实密钥，不产生模型用量。

这些测试检查本地流程与异常分支，不验证真实模型的提取准确率、实际断网或超时时间。

## 主要文件

| 文件 | 用途 |
| --- | --- |
| parse_intent_live.py | 交互式真实模型意图解析 |
| test_intent_cli.py | 完整七场景自动测试 |
| call_deepseek.py | 首次模型请求练习 |
| parse_intent.py | 手写模拟响应校验练习 |
| verify_request_errors.py | 连接与超时模拟检查练习 |
| requirements.txt | 依赖及版本清单 |
| .env.example | 不含真实密钥的配置模板 |

## 当前限制

- 当前演示面向时间、学分和课程类别明确的课程查询。

- Schema 校验确认字段符合规则，不能保证模型理解一定正确。

- 尚未实现课程信息检索、数据库、审批或申请提交。


