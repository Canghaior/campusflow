import argparse
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, APIConnectionError, APIStatusError, APITimeoutError

from rag_prepare_answer import build_answer_messages
from rag_retrieve import load_index, retrieve_chunks


def request_answer(client, messages: list[dict]) -> str:
    """只发起一次回答请求，不使用工具循环。"""
    response = client.chat.completions.create(
        model="deepseek-flash",
        messages=messages,
        extra_body={"thinking": {"type": "disabled"}},
        max_tokens=512,
        stream=False,
    )

    if not response.choices:
        raise ValueError("没有收到候选回答。")

    choice = response.choices[0]

    # 达到输出上限等情况可能造成回答截断，不能当作完整结果。
    if choice.finish_reason != "stop":
        raise ValueError(f"回答未正常结束：{choice.finish_reason}")

    answer = choice.message.content
    if not isinstance(answer, str) or not answer.strip():
        raise ValueError("模型返回了空回答。")

    return answer.strip()


def check_citation_ids(answer: str, evidence: list[dict]) -> set[str]:
    """检查标准 [S编号] 引用是否属于本次证据，不判断事实是否正确。"""
    allowed = {
        f"[{item['citation_id']}]"
        for item in evidence
    }

    # 捕获 [S1] 等形式，也让 [S999] 等不存在的编号被发现。
    used = set(re.findall(r"\[S[^\]\r\n]*\]", answer))
    unknown = used - allowed

    if unknown:
        raise ValueError(
            "回答引用了本次不存在的来源：" + "、".join(sorted(unknown))
        )

    return used


def main() -> None:
    parser = argparse.ArgumentParser(
        description="根据 CampusFlow 模拟资料回答并展示来源"
    )
    parser.add_argument("question", help="需要回答的问题")
    parser.add_argument("--top-k", type=int, default=2, help="最多提供几个候选块")
    args = parser.parse_args()

    try:
        index = load_index()
        results = retrieve_chunks(index, args.question, args.top_k)
        messages = build_answer_messages(args.question, results)
    except FileNotFoundError:
        raise SystemExit("准备失败：索引文件不存在，请先构建索引。")
    except UnicodeDecodeError:
        raise SystemExit("准备失败：索引文件不是有效的 UTF-8 文本。")
    except (OSError, ValueError) as error:
        raise SystemExit(f"准备失败：{error}")

    # 提前返回，后面的配置读取和模型请求都不会执行。
    if not messages:
        print("未检索到候选片段，当前资料无法确认这个问题。")
        print("本次未调用模型。")
        return

    # 从实际发给模型的消息中取得来源，避免重新编号造成不一致。
    evidence = json.loads(messages[1]["content"])["evidence"]

    # 沿用既有本地配置；不打印密钥或配置文件内容。
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path, encoding="utf-8-sig")
    api_key = os.getenv("LLM_API_KEY", "").strip()
    if not api_key or api_key == "replace_with_your_api_key":
        raise SystemExit("配置错误：项目尚未配置有效的 LLM_API_KEY。")

    try:
        with OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
            timeout=30.0,
            max_retries=0,
        ) as client:
            print("正在发起一次模型请求……")
            answer = request_answer(client, messages)

        used = check_citation_ids(answer, evidence)
    except APITimeoutError:
        raise SystemExit("请求超时：本次未收到完整回答，没有自动重试。")
    except APIConnectionError:
        raise SystemExit("连接失败：请检查网络或代理设置。")
    except APIStatusError as error:
        # 只展示状态码，避免把服务端原始错误内容直接打印出来。
        raise SystemExit(f"服务返回错误：HTTP {error.status_code}。")
    except ValueError as error:
        raise SystemExit(f"回答检查失败：{error}")

    print("\n模型回答：")
    print(answer)

    if used:
        print("\n引用编号检查通过；结论是否有依据仍需核对正文。")
    else:
        # 全部无法确认的回答可能没有引用，留给人工判断。
        print("\n未检测到标准 [S编号] 引用。")
        print("请检查：若回答包含资料中的事实结论，应补有依据的引用。")

    print("\n本次提供的证据来源：")
    for item in evidence:
        label = f"[{item['citation_id']}]"
        state = "回答已引用" if label in used else "未检测到引用"
        print(f"{label} {item['filename']}，{item['section']}（{state}）")
        print(f"来源路径：{item['source']}")
        print(f"块编号：{item['chunk_id']}")


if __name__ == "__main__":
    main()